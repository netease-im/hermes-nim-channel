#!/usr/bin/env node
import process from "node:process";
import readline from "node:readline";

import {
  buildNimConstructorOptions,
  buildConversationId,
  addBatchMetadata,
  addProcessingQuickComment,
  collectReadReceiptBatches,
  canFallbackMissingReply,
  clearBridgeRuntimeState,
  createStreamChunkParams,
  applyBridgeConnectionStatus,
  InboundBatchEmitter,
  inboundBatchKey,
  isP2pApplicantAllowed,
  isBridgeRuntimeConnected,
  normalizeTarget,
  normalizeConnectionStatus,
  normalizeSendResult,
  parseBridgeConfig,
  ReplyMessageCache,
  StreamSessionRegistry,
  TopicReplyContextRegistry,
  sendMediaMaybeTopicReply,
  sendEditReplacementMessage,
  sendStatefulStreamChunk,
  sendTextReplyMessage,
  sendTopicStreamChunk,
  shouldDispatchInboundMessage,
  splitMessageIntoChunks,
  toInboundMessage,
} from "./src/config.mjs";
import { createMediaMessage, normalizeMediaKind } from "./src/media.mjs";
import {
  isQChatTargetAllowed,
  normalizeQChatTarget,
  QChatReplyCache,
  sendQChatText,
} from "./src/qchat.mjs";
import { createQChatRuntime } from "./src/qchat-runtime.mjs";
import {
  decodeJsonl,
  errorResponse,
  eventMessage,
  okResponse,
  writeMessage,
} from "./src/protocol.mjs";

let runtime = null;
let qchatRuntime = null;
let friendRuntime = null;
let connectionRuntime = null;

function writeStderr(args) {
  const text = args
    .map((value) => {
      if (typeof value === "string") {
        return value;
      }
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    })
    .join(" ");
  process.stderr.write(`${text}\n`);
}

console.log = (...args) => writeStderr(args);
console.info = (...args) => writeStderr(args);
console.warn = (...args) => writeStderr(args);
console.error = (...args) => writeStderr(args);

function emit(message) {
  writeMessage(process.stdout, message);
}

async function cleanupRuntime(targetRuntime = runtime) {
  if (connectionRuntime) {
    try {
      connectionRuntime.stop();
    } catch {}
    connectionRuntime = null;
  }
  if (friendRuntime) {
    try {
      await friendRuntime.stop();
    } catch {}
    friendRuntime = null;
  }
  if (qchatRuntime) {
    try {
      await qchatRuntime.stop();
    } catch {}
    qchatRuntime = null;
  }
  if (!targetRuntime) {
    return;
  }

  try {
    targetRuntime.inboundBatcher?.stop();
  } catch {}
  clearBridgeRuntimeState(targetRuntime);
  if (Array.isArray(targetRuntime.quickCommentCleanups)) {
    for (const item of targetRuntime.quickCommentCleanups.splice(0)) {
      try {
        clearTimeout(item.timeout);
      } catch {}
      try {
        await item.cleanup();
      } catch {}
    }
  }

  try {
    await targetRuntime.loginService.logout();
  } catch {}

  try {
    await targetRuntime.nim.destroy?.();
  } catch {}

  if (runtime === targetRuntime) {
    runtime = null;
  }
}

function setupConnectionRuntime(loginService) {
  if (!loginService?.on) {
    return null;
  }

  const emitConnection = (payload) => {
    if (runtime) {
      applyBridgeConnectionStatus(runtime, payload);
    }
    emit(eventMessage("connection", payload));
  };
  const loginStatusHandler = (status) => {
    const payload = normalizeConnectionStatus("login", status);
    console.info(`[nim] login status changed — status: ${payload.status}, raw: ${JSON.stringify(status)}`);
    emitConnection(payload);
  };
  const kickedOfflineHandler = (detail) => {
    const payload = normalizeConnectionStatus("kickout", detail);
    console.warn(`[nim] kicked offline — reason: ${payload.reason}`);
    emitConnection(payload);
  };
  const disconnectedHandler = (error) => {
    const payload = normalizeConnectionStatus("disconnected", error);
    console.warn(`[nim] disconnected — reason: ${payload.reason}`);
    emitConnection(payload);
  };

  loginService.on("onLoginStatus", loginStatusHandler);
  loginService.on("onKickedOffline", kickedOfflineHandler);
  loginService.on("onDisconnected", disconnectedHandler);

  return {
    stop: () => {
      try {
        loginService.off?.("onLoginStatus", loginStatusHandler);
      } catch {}
      try {
        loginService.off?.("onKickedOffline", kickedOfflineHandler);
      } catch {}
      try {
        loginService.off?.("onDisconnected", disconnectedHandler);
      } catch {}
    },
  };
}

function setupFriendRuntime(nim, config) {
  const friendService = nim?.V2NIMFriendService;
  if (!friendService?.on) {
    console.warn("[nim] friend service is unavailable; friend auto-accept disabled");
    return null;
  }
  if (typeof friendService.acceptAddApplication !== "function") {
    console.warn("[nim] friend accept API is unavailable; friend auto-accept disabled");
    return null;
  }

  const p2pConfig = config?.p2p ?? {};
  const policy = String(p2pConfig.policy ?? "open").trim() || "open";
  const allowFrom = Array.isArray(p2pConfig.allowFrom) ? p2pConfig.allowFrom : [];

  const friendApplicationHandler = async (application) => {
    const applicantId = String(
      application?.applicantAccountId ??
        application?.applicantAccid ??
        application?.fromAccountId ??
        application?.fromAccid ??
        "",
    ).trim();
    if (!applicantId) {
      console.warn("[nim] friend application ignored — missing applicant id");
      return;
    }
    if (!isP2pApplicantAllowed({ policy, allowFrom, applicantId })) {
      console.info(`[nim] friend application ignored — applicant: ${applicantId}, policy: ${policy}`);
      return;
    }
    try {
      await friendService.acceptAddApplication(application);
      console.info(`[nim] friend application auto-accepted — applicant: ${applicantId}`);
    } catch (error) {
      console.warn(
        `[nim] friend application accept failed — applicant: ${applicantId}, error: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  };

  friendService.on("onFriendAddApplication", friendApplicationHandler);
  console.info(`[nim] friend auto-accept listener registered — policy: ${policy}`);

  return {
    stop: () => {
      try {
        friendService.off?.("onFriendAddApplication", friendApplicationHandler);
      } catch {}
    },
  };
}

async function handleConnect(id, params) {
  await cleanupRuntime();

  const config = parseBridgeConfig(params?.config ?? {});
  const mod = await import("@yxim/nim-bot");
  const NIM = mod.default ?? mod;
  const constructorOptions = buildNimConstructorOptions(config);
  const nim = new NIM(
    {
      appkey: config.credentials.appKey,
      apiVersion: "v2",
      debugLevel: config.debug ? "debug" : "off",
    },
    Object.keys(constructorOptions).length > 0 ? constructorOptions : undefined,
  );

  const loginService = nim.V2NIMLoginService;
  const messageService = nim.V2NIMMessageService;
  const messageCreator = nim.V2NIMMessageCreator;
  const replyCache = new ReplyMessageCache();
  const streamSessions = new StreamSessionRegistry();
  const topicContexts = new TopicReplyContextRegistry();
  const qchatReplyCache = new QChatReplyCache();
  const quickCommentCleanups = [];
  const inboundBatcher = new InboundBatchEmitter({
    debounceMs: config.inboundDebounceMs,
    emitBatch: async (items, batchKey, batchId) => {
      const batchSize = items.length;
      for (let index = 0; index < items.length; index += 1) {
        const item = items[index];
        const payload = addBatchMetadata(item.payload, {
          batchId,
          batchKey,
          batchIndex: index,
          batchSize,
        });
        emit(eventMessage("message", payload));
      }
    },
  });

  if (!loginService || !messageService || !messageCreator) {
    throw new Error("NIM SDK V2 services are unavailable");
  }

  messageService.on("onReceiveMessages", (messages = []) => {
    sendReadReceipts(messageService, messages);
    void (async () => {
      try {
        let skippedNonOnline = 0;
        for (const message of messages) {
          if (!shouldDispatchInboundMessage(message)) {
            skippedNonOnline += 1;
            continue;
          }
          replyCache.add(message);
          const payload = await toInboundMessage(message, config.credentials.account, nim);
          if (payload.topic_refer) {
            topicContexts.add({
              accountId: config.credentials.account,
              targetId: payload.sender_id,
              topic: payload.topic_refer,
              originalMessage: message,
            });
          }
          const quickComment = await addProcessingQuickComment({
            nim,
            message,
            config,
            trackCleanup: (cleanup) => quickCommentCleanups.push(cleanup),
          });
          const batchKey = inboundBatchKey(payload);
          inboundBatcher.enqueue(batchKey, {
            payload: {
              ...payload,
              quick_comment: quickComment,
            },
          });
        }
        if (skippedNonOnline > 0) {
          console.log(`[nim] skipped ${skippedNonOnline} non-online inbound messages for dispatch`);
        }
      } catch (error) {
        console.error(
          `[nim] inbound message handling failed — error: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
    })();
  });

  const pendingRuntime = {
    nim,
    loginService,
    messageService,
    messageCreator,
    replyCache,
    streamSessions,
    topicContexts,
    qchatReplyCache,
    inboundBatcher,
    quickCommentCleanups,
    connectionStatus: "connecting",
    connectionReason: "login",
    config,
  };
  const aiBot = config.legacyLogin ? 0 : 2;
  console.info(
    `[nim] login started — account: ${config.credentials.account}, aiBot: ${aiBot} (legacyLogin: ${config.legacyLogin})`,
  );
  try {
    qchatRuntime = createQChatRuntime(nim, config, qchatReplyCache, {
      emitMessage: (payload) => emit(eventMessage("message", payload)),
    });
    await loginService.login(config.credentials.account, config.credentials.token, { aiBot });
  } catch (error) {
    await cleanupRuntime(pendingRuntime);
    throw error;
  }
  console.info(`[nim] login successful — account: ${config.credentials.account}, aiBot: ${aiBot}`);
  runtime = pendingRuntime;
  runtime.connectionStatus = "connected";
  connectionRuntime = setupConnectionRuntime(loginService);
  friendRuntime = setupFriendRuntime(nim, config);
  await qchatRuntime?.activate?.();

  emit(
    okResponse(id, {
      connected: true,
      account: config.credentials.account,
    }),
  );
}

function sendReadReceipts(messageService, messages) {
  const { p2p, teamBatches, skipped } = collectReadReceiptBatches(messages);
  if (skipped > 0) {
    console.log(`[nim] skipped ${skipped} non-online messages for read receipt`);
  }

  for (const message of p2p) {
    if (typeof messageService.sendP2PMessageReceipt !== "function") {
      console.warn("[nim] send p2p read receipt skipped — SDK method unavailable");
      break;
    }
    try {
      Promise.resolve(messageService.sendP2PMessageReceipt(message)).catch((error) => {
        console.warn(
          `[nim] send p2p read receipt failed — error: ${error instanceof Error ? error.message : String(error)}`,
        );
      });
    } catch (error) {
      console.warn(
        `[nim] send p2p read receipt failed — error: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }

  if (typeof messageService.sendTeamMessageReceipts !== "function") {
    if (teamBatches.length > 0) {
      console.warn("[nim] send team read receipts skipped — SDK method unavailable");
    }
    return;
  }
  for (const batch of teamBatches) {
    if (batch.length === 0) {
      continue;
    }
    try {
      Promise.resolve(messageService.sendTeamMessageReceipts(batch)).catch((error) => {
        console.warn(
          `[nim] send team read receipts failed — error: ${error instanceof Error ? error.message : String(error)}`,
        );
      });
    } catch (error) {
      console.warn(
        `[nim] send team read receipts failed — error: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }
}

async function handleDisconnect(id) {
  await cleanupRuntime();
  emit(okResponse(id, { connected: false }));
}

async function handleHealth(id) {
  emit(
    okResponse(id, {
      connected: isBridgeRuntimeConnected(runtime),
      account: runtime?.config?.credentials?.account ?? null,
      connection_status: runtime?.connectionStatus ?? "disconnected",
      connection_reason: runtime?.connectionReason ?? "",
    }),
  );
}

function textSendOptions() {
  return {
    antispamConfig: {
      antispamEnabled: Boolean(runtime?.config?.antispamEnabled),
    },
  };
}

async function sendCreatedMessage(message, conversationId) {
  if (!isBridgeRuntimeConnected(runtime)) {
    throw new Error("bridge is not connected");
  }
  if (!message) {
    throw new Error("failed to create message");
  }

  const { messageService } = runtime;
  if (!isBridgeRuntimeConnected(runtime)) {
    throw new Error("bridge is not connected");
  }

  const result = await new Promise((resolve, reject) => {
    let settled = false;
    const clientMessageId = message.messageClientId;

    const listener = (sentMessage) => {
      if (sentMessage?.messageClientId !== clientMessageId || settled) {
        return;
      }
      if (sentMessage?.sendingState === 3) {
        return;
      }

      settled = true;
      messageService.off?.("onSendMessage", listener);
      const errorCode = sentMessage?.messageStatus?.errorCode;
      const failed =
        sentMessage?.sendingState === 2 ||
        (sentMessage?.sendingState === 1 && errorCode !== 200);

      if (failed) {
        reject(
          new Error(
            sentMessage?.messageStatus?.errorDesc ?? `send failed (${errorCode ?? "unknown"})`,
          ),
        );
        return;
      }

      resolve({
        message_id: String(sentMessage?.messageServerId ?? ""),
        client_message_id: String(sentMessage?.messageClientId ?? ""),
      });
    };

    messageService.on("onSendMessage", listener);
    messageService
      .sendMessage(message, conversationId, textSendOptions())
      .catch((error) => {
        if (settled) {
          return;
        }
        settled = true;
        messageService.off?.("onSendMessage", listener);
        reject(error);
      });

    setTimeout(() => {
      if (settled) {
        return;
      }
      settled = true;
      messageService.off?.("onSendMessage", listener);
      reject(new Error("send_message timed out"));
    }, 30000);
  });

  return result;
}

function responseFromChunkResults(results) {
  const last = results[results.length - 1] ?? {};
  return {
    message_id: String(last.message_id ?? ""),
    client_message_id: String(last.client_message_id ?? ""),
    chunks: results,
    chunk_count: results.length,
  };
}

async function resolveReplyOriginalMessage(replyTo) {
  const originalMessage = runtime.replyCache.get(replyTo);
  if (originalMessage) {
    console.info(`[nim] reply target cache hit — replyTo: ${replyTo}`);
    return originalMessage;
  }

  const messageRefer = runtime.replyCache.getRefer(replyTo);
  if (!messageRefer || typeof runtime.messageService?.getMessageListByRefers !== "function") {
    console.warn(`[nim] reply target cache miss — replyTo: ${replyTo}, refer: ${messageRefer ? "available" : "missing"}`);
    return null;
  }

  try {
    const messages = await runtime.messageService.getMessageListByRefers([messageRefer]);
    const fetched = Array.isArray(messages) ? messages[0] : null;
    if (fetched) {
      runtime.replyCache.add(fetched);
      console.info(`[nim] reply target fetched by refer — replyTo: ${replyTo}`);
      return fetched;
    }
  } catch (error) {
    console.warn(
      `[nim] reply target fetch failed — replyTo: ${replyTo}, error: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  return null;
}

function resolveOutboundTopicContext(target, params) {
  const topicId = Number(params?.topic_id ?? params?.topicId ?? target?.topicId);
  const replyTo = String(params?.reply_to ?? "").trim();
  const context = runtime.topicContexts.resolve({
    accountId: runtime.config.credentials.account,
    targetId: target.id,
    topicId,
    replyTo,
  });
  return {
    context,
    topicId: Number.isFinite(topicId) && topicId > 0 ? topicId : null,
    replyTo,
  };
}

function matchesRequestedTopic(originalMessage, topicId) {
  if (!topicId) {
    return true;
  }
  return Number(originalMessage?.topicRefer?.topicId) === Number(topicId);
}

async function handleSendMessage(id, params) {
  if (!isBridgeRuntimeConnected(runtime)) {
    throw new Error("bridge is not connected");
  }

  const target = normalizeTarget(params?.chat_id, params?.session_type);
  const conversationId = buildConversationId(
    runtime.nim,
    target.id,
    target.sessionType,
  );
  const chunks = splitMessageIntoChunks(params?.text ?? "", runtime.config?.textChunkLimit);
  const topicResolution = resolveOutboundTopicContext(target, params);
  let originalMessage = topicResolution.context?.originalMessage
    ?? (topicResolution.replyTo ? await resolveReplyOriginalMessage(topicResolution.replyTo) : null);
  if (!topicResolution.context && !matchesRequestedTopic(originalMessage, topicResolution.topicId)) {
    originalMessage = null;
  }
  if (!originalMessage && !canFallbackMissingReply({
    replyTo: topicResolution.replyTo,
    topicId: topicResolution.topicId,
  })) {
    throw new Error(`reply target not found: ${topicResolution.replyTo}`);
  }
  const fallbackMetadata = {
    ...(topicResolution.topicId && !topicResolution.context ? { topic_fallback: true } : {}),
    ...(topicResolution.replyTo && !originalMessage ? { reply_fallback: true } : {}),
  };

  if (originalMessage) {
    const results = [];
    for (const chunk of chunks) {
      const message = runtime.messageCreator.createTextMessage(chunk);
      if (!message) {
        throw new Error("failed to create text message");
      }
      const sendResult = await sendTextReplyMessage({
        nim: runtime.nim,
        messageService: runtime.messageService,
        message,
        originalMessage,
        options: textSendOptions(),
      });
      results.push(normalizeSendResult(sendResult));
    }
    emit(okResponse(id, { ...responseFromChunkResults(results), ...fallbackMetadata }));
    return;
  }

  const results = [];
  for (const chunk of chunks) {
    const message = runtime.messageCreator.createTextMessage(chunk);
    if (!message) {
      throw new Error("failed to create text message");
    }
    results.push(await sendCreatedMessage(message, conversationId));
  }

  emit(okResponse(id, { ...responseFromChunkResults(results), ...fallbackMetadata }));
}

async function handleSendStreamMessage(id, params) {
  if (!isBridgeRuntimeConnected(runtime)) {
    throw new Error("bridge is not connected");
  }

  const target = normalizeTarget(params?.chat_id, params?.session_type);
  const conversationId = buildConversationId(runtime.nim, target.id, target.sessionType);
  const text = String(params?.text ?? "");
  const chunkIndex = Number(params?.chunk_index ?? params?.chunkIndex ?? 0);
  const rawComplete = params?.is_complete ?? params?.isComplete ?? true;
  const isComplete = typeof rawComplete === "boolean"
    ? rawComplete
    : !["0", "false", "no", "off"].includes(String(rawComplete).trim().toLowerCase());
  const streamChunkParams = createStreamChunkParams({ text, chunkIndex, isComplete });
  const topicResolution = resolveOutboundTopicContext(target, params);
  const streamId = String(params?.stream_id ?? params?.streamId ?? "").trim();
  let originalMessage = topicResolution.context?.originalMessage
    ?? (topicResolution.replyTo ? await resolveReplyOriginalMessage(topicResolution.replyTo) : null);
  if (!topicResolution.context && !matchesRequestedTopic(originalMessage, topicResolution.topicId)) {
    originalMessage = null;
  }

  if (topicResolution.topicId) {
    if (!originalMessage) {
      const message = runtime.messageCreator.createTextMessage(text);
      if (!message) {
        throw new Error("failed to create Topic stream fallback message");
      }
      const fallbackResult = await sendCreatedMessage(message, conversationId);
      emit(okResponse(id, {
        ...fallbackResult,
        stream_id: streamId,
        stream_fallback: true,
        topic_fallback: true,
      }));
      return;
    }
    const topicResult = await sendTopicStreamChunk({
      nim: runtime.nim,
      messageCreator: runtime.messageCreator,
      text,
      originalMessage,
      options: textSendOptions(),
    });
    emit(okResponse(id, {
      ...topicResult,
      stream_id: streamId,
      topic_stream_chunked: true,
    }));
    return;
  }

  if (!originalMessage && !canFallbackMissingReply({
    replyTo: topicResolution.replyTo,
    topicId: topicResolution.topicId,
  })) {
    throw new Error(`reply target not found: ${topicResolution.replyTo}`);
  }
  const streamKey = runtime.streamSessions.key({
    streamId,
    accountId: runtime.config.credentials.account,
    targetId: target.id,
    sessionType: target.sessionType,
    replyTo: topicResolution.replyTo,
    topicId: topicResolution.topicId,
  });
  const sent = await sendStatefulStreamChunk({
    registry: runtime.streamSessions,
    key: streamKey,
    messageCreator: runtime.messageCreator,
    messageService: runtime.messageService,
    text,
    conversationId,
    originalMessage,
    options: textSendOptions(),
    streamChunkParams,
    isComplete,
    sendOrdinary: (message) => sendCreatedMessage(message, conversationId),
  });
  const result = sent.mode === "fallback"
    ? { ...sent.result, stream_fallback: true }
    : normalizeSendResult(sent.result);
  emit(okResponse(id, {
    ...result,
    stream_id: streamId || streamKey,
    ...(topicResolution.topicId && !topicResolution.context ? { topic_fallback: true } : {}),
    ...(topicResolution.replyTo && !originalMessage ? { reply_fallback: true } : {}),
  }));
}

async function handleEditMessage(id, params) {
  if (!isBridgeRuntimeConnected(runtime)) {
    throw new Error("bridge is not connected");
  }
  const target = normalizeTarget(params?.chat_id, params?.session_type);
  const conversationId = buildConversationId(runtime.nim, target.id, target.sessionType);
  const result = await sendEditReplacementMessage({
    messageCreator: runtime.messageCreator,
    text: params?.text ?? params?.new_text ?? "",
    messageId: params?.message_id,
    sendCreated: (message) => sendCreatedMessage(message, conversationId),
  });
  emit(okResponse(id, result));
}

async function handleSendQChatMessage(id, params) {
  if (!isBridgeRuntimeConnected(runtime)) {
    throw new Error("bridge is not connected");
  }
  if (!runtime.nim?.qchatMsg) {
    throw new Error("qchat messaging is unavailable");
  }

  const target = normalizeQChatTarget(params?.chat_id ?? params?.target_id ?? "");
  const qchatConfig = runtime.config?.qchat ?? {};
  const policy = String(qchatConfig.policy ?? "open").trim() || "open";
  const allowFrom = Array.isArray(qchatConfig.allowFrom) ? qchatConfig.allowFrom : [];
  if (
    !isQChatTargetAllowed({
      policy,
      allowFrom,
      serverId: target.serverId,
      channelId: target.channelId,
    })
  ) {
    throw new Error("qchat send blocked by policy");
  }

  const replyTo = String(params?.reply_to ?? "").trim();
  const originalMessage = replyTo ? runtime.qchatReplyCache.get(replyTo) : null;
  const sent = await sendQChatText({
    qchatMsg: runtime.nim.qchatMsg,
    target,
    text: params?.text,
    originalMessage,
  });
  const response = sent.response;

  emit(
    okResponse(id, {
      message_id: String(response?.message?.msgIdServer ?? response?.msgIdServer ?? ""),
      client_message_id: String(response?.message?.msgIdClient ?? response?.msgIdClient ?? ""),
      ...(replyTo && sent.mode !== "reply" ? { reply_fallback: true } : {}),
    }),
  );
}

async function handleSendMedia(id, params) {
  if (!isBridgeRuntimeConnected(runtime)) {
    throw new Error("bridge is not connected");
  }

  const target = normalizeTarget(params?.chat_id, params?.session_type);
  const conversationId = buildConversationId(
    runtime.nim,
    target.id,
    target.sessionType,
  );
  const mediaKind = normalizeMediaKind(params?.media_kind);
  const filePath = String(params?.file_path ?? "").trim();

  if (!filePath) {
    throw new Error("file_path is required");
  }

  const message = await createMediaMessage(
    runtime.messageCreator,
    mediaKind,
    filePath,
  );

  if (!message) {
    throw new Error(`failed to create ${mediaKind} message`);
  }

  const topicResolution = resolveOutboundTopicContext(target, params);
  let originalMessage = topicResolution.context?.originalMessage
    ?? (topicResolution.replyTo ? await resolveReplyOriginalMessage(topicResolution.replyTo) : null);
  if (!topicResolution.context && !matchesRequestedTopic(originalMessage, topicResolution.topicId)) {
    originalMessage = null;
  }
  const mediaSend = await sendMediaMaybeTopicReply({
    nim: runtime.nim,
    message,
    originalMessage,
    options: textSendOptions(),
    sendOrdinary: () => sendCreatedMessage(message, conversationId),
  });
  const result = mediaSend.usedTopicReply
    ? normalizeSendResult(mediaSend.result)
    : mediaSend.result;
  emit(okResponse(id, {
    ...result,
    ...(topicResolution.topicId && !topicResolution.context ? { topic_fallback: true } : {}),
    ...(topicResolution.replyTo && !originalMessage ? { reply_fallback: true } : {}),
  }));
}

async function handleRequest(message) {
  const id = String(message?.id ?? "");
  const method = message?.method;

  try {
    if (method === "connect") {
      await handleConnect(id, message?.params);
      return;
    }
    if (method === "disconnect") {
      await handleDisconnect(id);
      return;
    }
    if (method === "health") {
      await handleHealth(id);
      return;
    }
    if (method === "send_message") {
      await handleSendMessage(id, message?.params);
      return;
    }
    if (method === "send_stream_message") {
      await handleSendStreamMessage(id, message?.params);
      return;
    }
    if (method === "edit_message") {
      await handleEditMessage(id, message?.params);
      return;
    }
    if (method === "send_qchat_message") {
      await handleSendQChatMessage(id, message?.params);
      return;
    }
    if (method === "send_media") {
      await handleSendMedia(id, message?.params);
      return;
    }
    throw new Error(`unsupported method: ${method}`);
  } catch (error) {
    emit(errorResponse(id, error instanceof Error ? error.message : String(error)));
  }
}

const rl = readline.createInterface({
  input: process.stdin,
  crlfDelay: Infinity,
});

rl.on("line", async (line) => {
  try {
    const message = decodeJsonl(line);
    if (message?.type !== "request") {
      return;
    }
    await handleRequest(message);
  } catch (error) {
    emit(
      errorResponse(
        "",
        error instanceof Error ? error.message : String(error),
      ),
    );
  }
});

process.on("SIGINT", async () => {
  await cleanupRuntime();
  process.exit(0);
});

process.on("SIGTERM", async () => {
  await cleanupRuntime();
  process.exit(0);
});

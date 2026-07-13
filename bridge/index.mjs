#!/usr/bin/env node
import process from "node:process";
import readline from "node:readline";

import {
  buildNimConstructorOptions,
  buildConversationId,
  isP2pApplicantAllowed,
  normalizeTarget,
  parseBridgeConfig,
  toInboundMessage,
} from "./src/config.mjs";
import { createMediaMessage, normalizeMediaKind } from "./src/media.mjs";
import {
  deriveQChatServerIds,
  isQChatTargetAllowed,
  normalizeQChatMessage,
  normalizeQChatSystemNotification,
  normalizeQChatTarget,
} from "./src/qchat.mjs";
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

async function cleanupRuntime() {
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
  if (!runtime) {
    return;
  }

  try {
    await runtime.loginService.logout();
  } catch {}

  try {
    await runtime.nim.destroy?.();
  } catch {}

  runtime = null;
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

async function discoverJoinedQChatServers(nim) {
  const serverIds = [];
  let timestamp = 0;
  const pageLimit = 100;

  for (let page = 0; page < 20; page += 1) {
    const resp = await nim.qchatServer.getServersByPage({
      timestamp,
      limit: pageLimit,
    });

    const servers = resp.datas ?? [];
    if (servers.length === 0) {
      break;
    }

    for (const server of servers) {
      if (server?.serverId) {
        serverIds.push(String(server.serverId));
      }
    }

    const hasMore = resp.listQueryTag?.hasMore ?? servers.length >= pageLimit;
    if (!hasMore) {
      break;
    }

    const lastServer = servers[servers.length - 1];
    if (lastServer?.createTime) {
      timestamp = lastServer.createTime;
      continue;
    }
    break;
  }

  return [...new Set(serverIds)];
}

async function setupQChatRuntime(nim, config) {
  if (!nim?.qchatMsg || !nim?.qchatServer) {
    console.warn("[qchat] qchat APIs are unavailable on this SDK instance");
    return null;
  }

  const qchatConfig = config?.qchat ?? {};
  const policy = String(qchatConfig.policy ?? "open").trim() || "open";
  const allowFrom = Array.isArray(qchatConfig.allowFrom) ? qchatConfig.allowFrom : [];
  const isEffectivelyDisabled = policy === "disabled" || (policy === "allowlist" && allowFrom.length === 0);
  if (isEffectivelyDisabled) {
    console.info(
      `[qchat] disabled — policy: ${policy}, allowFrom count: ${allowFrom.length}`,
    );
    return null;
  }

  const subscribedServerIds = new Set();
  const logPrefix = "[qchat]";

  const subscribeServer = async (serverId) => {
    if (!serverId || subscribedServerIds.has(serverId)) {
      return;
    }
    const resp = await nim.qchatServer.subscribeAllChannel({
      type: 1,
      serverIds: [serverId],
    });
    const failed = resp.failServerIds ?? [];
    if (failed.includes(serverId)) {
      console.warn(`${logPrefix} subscribe failed — server: ${serverId}`);
      return;
    }
    subscribedServerIds.add(serverId);
    console.info(`${logPrefix} subscribed — server: ${serverId}`);
  };

  const refreshSubscriptions = async () => {
    const serverIds = policy === "allowlist" ? deriveQChatServerIds(allowFrom) : await discoverJoinedQChatServers(nim);
    if (serverIds.length === 0) {
      console.info(`${logPrefix} no servers to subscribe`);
      return;
    }
    const resp = await nim.qchatServer.subscribeAllChannel({
      type: 1,
      serverIds,
    });
    const failed = new Set(resp.failServerIds ?? []);
    for (const serverId of serverIds) {
      if (!failed.has(serverId)) {
        subscribedServerIds.add(serverId);
      }
    }
    if (failed.size > 0) {
      console.warn(`${logPrefix} subscribe failed — servers: ${[...failed].join(", ")}`);
    }
  };

  const messageHandler = (message) => {
    const normalized = normalizeQChatMessage(message, config.credentials.account);
    if (!normalized) {
      return;
    }
    emit(eventMessage("message", normalized));
  };

  const systemNotificationHandler = async (notification) => {
    const normalized = normalizeQChatSystemNotification(notification);
    if (normalized.type === "serverMemberInvite") {
      const serverId =
        normalized.serverId ??
        normalized.server_id ??
        normalized.attach?.serverInfo?.serverId;
      const inviterAccid = normalized.fromAccount ?? normalized.from_accid;
      const requestId = normalized.attach?.requestId;
      if (!serverId || !inviterAccid || !requestId) {
        return;
      }
      if (policy === "disabled") {
        return;
      }
      if (policy === "allowlist") {
        const allowedServerIds = new Set(deriveQChatServerIds(allowFrom));
        if (!allowedServerIds.has(serverId)) {
          return;
        }
      }
      try {
        await nim.qchatServer.acceptServerInvite({
          serverId,
          accid: inviterAccid,
          recordInfo: { requestId },
        });
      } catch (error) {
        console.warn(
          `${logPrefix} invite accept failed — server: ${serverId}, error: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
      return;
    }

    if (normalized.type === "serverMemberInviteDone") {
      const serverId = normalized.serverId ?? normalized.server_id;
      if (!serverId || subscribedServerIds.has(serverId)) {
        return;
      }
      try {
        await subscribeServer(serverId);
      } catch (error) {
        console.warn(
          `${logPrefix} subscribe after invite failed — server: ${serverId}, error: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
    }
  };

  nim.qchatMsg.on("message", messageHandler);
  nim.qchatMsg.on("systemNotification", systemNotificationHandler);

  try {
    await refreshSubscriptions();
  } catch (error) {
    console.warn(
      `${logPrefix} initial subscription failed — error: ${error instanceof Error ? error.message : String(error)}`,
    );
  }

  return {
    stop: async () => {
      try {
        nim.qchatMsg.off?.("message", messageHandler);
      } catch {}
      try {
        nim.qchatMsg.off?.("systemNotification", systemNotificationHandler);
      } catch {}
      if (subscribedServerIds.size > 0) {
        try {
          await nim.qchatServer.subscribeAllChannel({
            type: 1,
            serverIds: [],
          });
        } catch {}
      }
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

  if (!loginService || !messageService || !messageCreator) {
    throw new Error("NIM SDK V2 services are unavailable");
  }

  messageService.on("onReceiveMessages", (messages = []) => {
    void (async () => {
      try {
        for (const message of messages) {
          emit(
            eventMessage(
              "message",
              await toInboundMessage(message, config.credentials.account, nim),
            ),
          );
        }
      } catch (error) {
        console.error(
          `[nim] inbound message handling failed — error: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
    })();
  });

  await loginService.login(config.credentials.account, config.credentials.token, {
    aiBot: 2,
  });

  runtime = {
    nim,
    loginService,
    messageService,
    messageCreator,
    config,
  };
  friendRuntime = setupFriendRuntime(nim, config);
  qchatRuntime = await setupQChatRuntime(nim, config);

  emit(
    okResponse(id, {
      connected: true,
      account: config.credentials.account,
    }),
  );
}

async function handleDisconnect(id) {
  await cleanupRuntime();
  emit(okResponse(id, { connected: false }));
}

async function handleHealth(id) {
  emit(
    okResponse(id, {
      connected: Boolean(runtime),
      account: runtime?.config?.credentials?.account ?? null,
    }),
  );
}

async function sendCreatedMessage(message, conversationId) {
  if (!runtime) {
    throw new Error("bridge is not connected");
  }
  if (!message) {
    throw new Error("failed to create message");
  }

  const { messageService } = runtime;
  if (!runtime) {
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
      .sendMessage(message, conversationId, {})
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

async function handleSendMessage(id, params) {
  if (!runtime) {
    throw new Error("bridge is not connected");
  }

  const target = normalizeTarget(params?.chat_id, params?.session_type);
  const conversationId = buildConversationId(
    runtime.nim,
    target.id,
    target.sessionType,
  );
  const message = runtime.messageCreator.createTextMessage(String(params?.text ?? ""));

  if (!message) {
    throw new Error("failed to create text message");
  }

  const result = await sendCreatedMessage(message, conversationId);

  emit(okResponse(id, result));
}

async function handleSendQChatMessage(id, params) {
  if (!runtime) {
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

  const response = await runtime.nim.qchatMsg.sendMessage({
    serverId: target.serverId,
    channelId: target.channelId,
    type: "text",
    body: String(params?.text ?? ""),
  });

  emit(
    okResponse(id, {
      message_id: String(response?.message?.msgIdServer ?? response?.msgIdServer ?? ""),
      client_message_id: String(response?.message?.msgIdClient ?? response?.msgIdClient ?? ""),
    }),
  );
}

async function handleSendMedia(id, params) {
  if (!runtime) {
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

  const result = await sendCreatedMessage(message, conversationId);
  emit(okResponse(id, result));
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

import test from "node:test";
import assert from "node:assert/strict";

import {
  buildNimConstructorOptions,
  addBatchMetadata,
  addProcessingQuickComment,
  isP2pApplicantAllowed,
  collectReadReceiptBatches,
  createStreamChunkParams,
  deriveMessageRefer,
  InboundBatchEmitter,
  inboundBatchKey,
  normalizeTarget,
  normalizeConnectionStatus,
  normalizeTopicInfo,
  normalizeTopicRefer,
  parseBridgeConfig,
  ReplyMessageCache,
  resolveQuickCommentIndex,
  resolveTopicInfo,
  resolveTopicReplyContext,
  resolveTeamName,
  sendEditReplacementMessage,
  sendMediaMaybeTopicReply,
  sendStreamTextMessage,
  sendTextReplyMessage,
  splitMessageIntoChunks,
  toInboundMessage,
} from "../src/config.mjs";
import {
  coerceAudioMetadata,
  coerceVideoMetadata,
  normalizeMediaKind,
} from "../src/media.mjs";
import {
  decodeJsonl,
  encodeJsonl,
  eventMessage,
  okResponse,
} from "../src/protocol.mjs";

test("protocol encodes and decodes JSONL", () => {
  const encoded = encodeJsonl(okResponse("1", { connected: true }));
  const decoded = decodeJsonl(encoded);
  assert.equal(decoded.id, "1");
  assert.equal(decoded.result.connected, true);
});

test("config parser accepts shorthand credentials", () => {
  const parsed = parseBridgeConfig({
    nim_token: "app|bot|secret",
  });
  assert.equal(parsed.credentials.appKey, "app");
  assert.equal(parsed.credentials.account, "bot");
});

test("config parser accepts text chunk limit", () => {
  const parsed = parseBridgeConfig({
    nim_token: "app|bot|secret",
    text_chunk_limit: 1234,
    legacy_login: "true",
    antispam_enabled: "false",
  });
  assert.equal(parsed.textChunkLimit, 1234);
  assert.equal(parsed.legacyLogin, true);
  assert.equal(parsed.antispamEnabled, false);
});

test("config parser accepts inbound batching and quick comment controls", () => {
  const parsed = parseBridgeConfig({
    nim_token: "app|bot|secret",
    inbound_debounce_ms: 250,
    quick_comment: {
      enabled: "true",
      index: 72,
      ttl_ms: 5000,
    },
  });
  assert.equal(parsed.inboundDebounceMs, 250);
  assert.deepEqual(parsed.quickComment, {
    enabled: true,
    index: 72,
    ttlMs: 5000,
  });
});

test("private deployment config builds SDK constructor options", () => {
  const parsed = parseBridgeConfig({
    nim_token: "app|bot|secret",
    advanced: {
      weblbsUrl: "https://lbs.example.com",
      link_web: "wss://link.example.com",
      nos_uploader: "https://upload.example.com",
      nos_downloader_v2: "https://download.example.com/{object}",
      nosSsl: true,
      nos_accelerate: "https://cdn.example.com/{object}",
      nos_accelerate_host: "cdn.example.com",
    },
  });
  const options = buildNimConstructorOptions(parsed);
  assert.deepEqual(options.privateConf, {
    weblbsUrl: "https://lbs.example.com",
    link_web: "wss://link.example.com",
    nos_uploader: "https://upload.example.com",
    nos_downloader_v2: "https://download.example.com/{object}",
    nosSsl: true,
    nos_accelerate: "https://cdn.example.com/{object}",
    nos_accelerate_host: "cdn.example.com",
  });
  assert.deepEqual(options.V2NIMLoginServiceConfig, {
    lbsUrls: ["https://lbs.example.com"],
    linkUrl: "wss://link.example.com",
  });
});

test("private deployment config ignores blank endpoints and parses boolean strings", () => {
  const parsed = parseBridgeConfig({
    nim_token: "app|bot|secret",
    advanced: {
      weblbsUrl: "   ",
      link_web: "wss://link.example.com  ",
      nosSsl: "false",
      nos_accelerate_host: "   ",
    },
  });
  const options = buildNimConstructorOptions(parsed);
  assert.deepEqual(options.privateConf, {
    link_web: "wss://link.example.com",
    nosSsl: false,
  });
  assert.deepEqual(options.V2NIMLoginServiceConfig, {
    linkUrl: "wss://link.example.com",
  });
});

test("bridge config parses p2p policy controls", () => {
  const parsed = parseBridgeConfig({
    nim_token: "app|bot|secret",
    p2p: {
      policy: "allowlist",
      allowFrom: ["Alice", "bob"],
    },
  });
  assert.deepEqual(parsed.p2p, {
    policy: "allowlist",
    allowFrom: ["Alice", "bob"],
  });
});

test("p2p applicant policy supports open allowlist and disabled modes", () => {
  assert.equal(isP2pApplicantAllowed({ policy: "open", applicantId: "alice" }), true);
  assert.equal(
    isP2pApplicantAllowed({
      policy: "allowlist",
      allowFrom: ["Alice"],
      applicantId: "alice",
    }),
    true,
  );
  assert.equal(
    isP2pApplicantAllowed({
      policy: "allowlist",
      allowFrom: ["bob"],
      applicantId: "alice",
    }),
    false,
  );
  assert.equal(isP2pApplicantAllowed({ policy: "disabled", applicantId: "alice" }), false);
  assert.equal(isP2pApplicantAllowed({ policy: "open", applicantId: "" }), false);
});

test("connection status normalization maps SDK lifecycle callbacks", () => {
  assert.deepEqual(normalizeConnectionStatus("login", 1), {
    status: "connected",
    reason: "login",
  });
  assert.deepEqual(normalizeConnectionStatus("login", 0), {
    status: "logout",
    reason: "login_status",
  });
  assert.deepEqual(normalizeConnectionStatus("kickout", { reasonDesc: "other login" }), {
    status: "kickout",
    reason: "other login",
  });
  assert.deepEqual(normalizeConnectionStatus("disconnected", new Error("network")), {
    status: "disconnected",
    reason: "network",
  });
});

test("read receipt batches include only online p2p and team messages", () => {
  const messages = [
    { conversationId: "0|1|alice", messageSource: 1, id: "p2p-online" },
    { conversationId: "0|1|bob", messageSource: 2, id: "p2p-offline" },
    { conversationId: "0|2|team-a", messageSource: 1, id: "team-online" },
    { conversationId: "0|3|super-a", messageSource: 1, id: "super-online" },
    { conversationId: "0|2|team-b", messageSource: 3, id: "team-history" },
  ];
  const batches = collectReadReceiptBatches(messages, 50);
  assert.deepEqual(
    batches.p2p.map((message) => message.id),
    ["p2p-online"],
  );
  assert.deepEqual(
    batches.teamBatches.map((batch) => batch.map((message) => message.id)),
    [["team-online", "super-online"]],
  );
});

test("team read receipt batches are bounded", () => {
  const messages = Array.from({ length: 51 }, (_, index) => ({
    conversationId: `0|2|team-${index}`,
    messageSource: 1,
    id: `team-${index}`,
  }));
  const batches = collectReadReceiptBatches(messages, 50);
  assert.equal(batches.p2p.length, 0);
  assert.equal(batches.teamBatches.length, 2);
  assert.equal(batches.teamBatches[0].length, 50);
  assert.equal(batches.teamBatches[1].length, 1);
});

test("reply message cache indexes server and client message ids", () => {
  const cache = new ReplyMessageCache(10);
  const message = {
    messageServerId: "server-1",
    messageClientId: "client-1",
    text: "hello",
  };
  cache.add(message);
  assert.equal(cache.get("server-1"), message);
  assert.equal(cache.get("client-1"), message);
  assert.equal(cache.get("missing"), null);
});

test("reply message cache is bounded and ignores empty ids", () => {
  const cache = new ReplyMessageCache(2);
  cache.add({ messageServerId: "", messageClientId: "" });
  assert.equal(cache.get(""), null);

  const first = { messageServerId: "server-1" };
  const second = { messageServerId: "server-2" };
  const third = { messageServerId: "server-3" };
  cache.add(first);
  cache.add(second);
  cache.add(third);
  assert.equal(cache.get("server-1"), null);
  assert.equal(cache.get("server-2"), second);
  assert.equal(cache.get("server-3"), third);
});

test("text chunking prefers newline and space boundaries", () => {
  assert.deepEqual(splitMessageIntoChunks("short", 10), ["short"]);
  assert.deepEqual(splitMessageIntoChunks("alpha\nbeta gamma", 8), ["alpha", "beta", "gamma"]);
  assert.deepEqual(splitMessageIntoChunks("abcdef", 3), ["abc", "def"]);
});

test("target normalization preserves team routing", () => {
  assert.deepEqual(normalizeTarget("team:123"), {
    id: "123",
    sessionType: "team",
  });
  assert.deepEqual(normalizeTarget("user:alice"), {
    id: "alice",
    sessionType: "p2p",
  });
});

test("media kind normalization accepts supported kinds", () => {
  assert.equal(normalizeMediaKind("image"), "image");
  assert.equal(normalizeMediaKind(" video "), "video");
  assert.throws(() => normalizeMediaKind("sticker"));
});

test("audio metadata coercion requires a positive duration", () => {
  assert.deepEqual(coerceAudioMetadata({ format: { duration: "3.2" } }), {
    duration: 3,
  });
  assert.throws(() => coerceAudioMetadata({ format: { duration: "0" } }));
});

test("video metadata coercion requires duration and dimensions", () => {
  assert.deepEqual(
    coerceVideoMetadata({
      format: { duration: "9.8" },
      streams: [{ codec_type: "video", width: 1280, height: 720 }],
    }),
    {
      duration: 10,
      width: 1280,
      height: 720,
    },
  );
  assert.throws(() =>
    coerceVideoMetadata({
      format: { duration: "9.8" },
      streams: [{ codec_type: "video", width: 0, height: 720 }],
    }),
  );
});

test("inbound conversion extracts mention metadata", async () => {
  const payload = await toInboundMessage(
    {
      conversationId: "0|2|team-1",
      senderId: "alice",
      receiverId: "team-1",
      messageType: 0,
      messageClientId: "client-1",
      messageServerId: "server-1",
      text: "hello",
      pushConfig: {
        forcePushAccountIds: ["bot"],
      },
    },
    "bot",
  );
  assert.equal(payload.session_type, "team");
  assert.equal(payload.mentioned, true);
  assert.equal(eventMessage("message", payload).event, "message");
});

test("inbound team conversion resolves conversation name", async () => {
  const calls = [];
  const nim = {
    V2NIMTeamService: {
      async getTeamInfo(teamId, teamType) {
        calls.push([teamId, teamType]);
        return { name: "Engineering" };
      },
    },
  };
  const payload = await toInboundMessage(
    {
      conversationId: "0|2|team-2",
      senderId: "alice",
      receiverId: "team-2",
      messageType: 0,
      messageClientId: "client-team-name",
      text: "hello",
    },
    "bot",
    nim,
  );
  assert.equal(payload.conversation_name, "Engineering");
  assert.deepEqual(calls, [["team-2", 1]]);
});

test("inbound conversion preserves thread and topic metadata", async () => {
  const payload = await toInboundMessage(
    {
      conversationId: "0|1|alice",
      senderId: "alice",
      receiverId: "bot",
      messageType: 0,
      messageClientId: "client-topic",
      text: "topic hello",
      topicRefer: {
        topicId: "42",
        conversationId: "0|1|alice",
        createTime: "123456",
      },
      threadReply: {
        messageClientId: "root-client",
      },
    },
    "bot",
  );
  assert.deepEqual(payload.topic_refer, {
    topicId: 42,
    conversationId: "0|1|alice",
    createTime: 123456,
  });
  assert.deepEqual(payload.thread_reply, {
    messageClientId: "root-client",
  });
});

test("inbound conversion enriches topic info when sdk can resolve it", async () => {
  const nim = {
    V2NIMTopicService: {
      async getTopicByRefer(refer) {
        return {
          ...refer,
          topicName: "Incident Review",
          messageClientId: "topic-root",
        };
      },
    },
  };
  const payload = await toInboundMessage(
    {
      conversationId: "0|1|alice",
      senderId: "alice",
      receiverId: "bot",
      messageType: 0,
      messageClientId: "client-topic-info",
      text: "topic hello",
      topicRefer: {
        topicId: 43,
        conversationId: "0|1|alice",
        createTime: 123457,
      },
    },
    "bot",
    nim,
  );
  assert.equal(payload.topic_name, "Incident Review");
  assert.deepEqual(payload.topic_info, {
    topicId: 43,
    conversationId: "0|1|alice",
    createTime: 123457,
    topicName: "Incident Review",
    messageClientId: "topic-root",
  });
});

test("topic refer normalization rejects incomplete values", () => {
  assert.equal(normalizeTopicRefer(null), null);
  assert.equal(normalizeTopicRefer({ topicId: 0, conversationId: "0|1|a", createTime: 1 }), null);
  assert.equal(normalizeTopicRefer({ topicId: 1, conversationId: "", createTime: 1 }), null);
  assert.equal(normalizeTopicRefer({ topicId: 1, conversationId: "0|1|a", createTime: 0 }), null);
});

test("topic info normalization and resolver fall back to refer", async () => {
  assert.equal(normalizeTopicInfo({ topicId: 0 }), null);
  assert.deepEqual(
    normalizeTopicInfo(
      {
        topicName: "Topic Name",
      },
      {
        topicId: 11,
        conversationId: "0|1|alice",
        createTime: 222,
      },
    ),
    {
      topicId: 11,
      conversationId: "0|1|alice",
      createTime: 222,
      topicName: "Topic Name",
    },
  );
  const resolved = await resolveTopicInfo({}, {
    topicId: 12,
    conversationId: "0|1|alice",
    createTime: 333,
  });
  assert.deepEqual(resolved, {
    topicId: 12,
    conversationId: "0|1|alice",
    createTime: 333,
  });
});

test("batch metadata helper annotates payloads", () => {
  assert.deepEqual(
    addBatchMetadata(
      { text: "hello" },
      {
        batchId: "batch-1",
        batchKey: "p2p:alice",
        batchIndex: 1,
        batchSize: 2,
      },
    ),
    {
      text: "hello",
      batch_id: "batch-1",
      batch_key: "p2p:alice",
      batch_index: 1,
      batch_size: 2,
    },
  );
});

test("inbound batch emitter groups same-key messages and preserves order", async () => {
  const emitted = [];
  const batcher = new InboundBatchEmitter({
    debounceMs: 1000,
    emitBatch: async (items, batchKey, batchId) => {
      emitted.push({ items, batchKey, batchId });
    },
  });
  batcher.enqueue("p2p:alice", { id: "a" });
  batcher.enqueue("p2p:alice", { id: "b" });
  batcher.enqueue("p2p:bob", { id: "c" });
  assert.equal(emitted.length, 0);
  batcher.stop();
  assert.equal(emitted.length, 2);
  assert.deepEqual(emitted[0].items.map((item) => item.id), ["a", "b"]);
  assert.equal(emitted[0].batchKey, "p2p:alice");
  assert.equal(emitted[1].batchKey, "p2p:bob");
  assert.notEqual(emitted[0].batchId, emitted[1].batchId);
});

test("inbound batch key separates p2p senders", () => {
  assert.equal(
    inboundBatchKey({
      session_type: "p2p",
      sender_id: "alice",
      target_id: "bot",
    }),
    "p2p:alice",
  );
  assert.equal(
    inboundBatchKey({
      session_type: "p2p",
      sender_id: "bob",
      target_id: "bot",
    }),
    "p2p:bob",
  );
  assert.equal(
    inboundBatchKey({
      session_type: "team",
      sender_id: "alice",
      target_id: "team-1",
    }),
    "team:team-1",
  );
});

test("quick comment helpers normalize index and derive message refer", () => {
  assert.equal(resolveQuickCommentIndex("72"), 72);
  assert.equal(resolveQuickCommentIndex("bad"), 71);
  assert.deepEqual(
    deriveMessageRefer({
      senderId: "alice",
      receiverId: "bot",
      messageClientId: "client-1",
      messageServerId: "server-1",
      conversationId: "0|1|alice",
      createTime: 123,
      conversationType: 1,
    }),
    {
      senderId: "alice",
      receiverId: "bot",
      messageClientId: "client-1",
      messageServerId: "server-1",
      conversationId: "0|1|alice",
      createTime: 123,
      conversationType: 1,
    },
  );
  assert.equal(deriveMessageRefer({ senderId: "alice" }), null);
});

test("quick comment helper adds metadata and schedules cleanup", async () => {
  const calls = [];
  let scheduled = null;
  const tracked = [];
  const message = {
    senderId: "alice",
    receiverId: "bot",
    messageClientId: "client-1",
    messageServerId: "server-1",
    conversationId: "0|1|alice",
    createTime: 123,
    conversationType: 1,
  };
  const nim = {
    V2NIMMessageService: {
      async addQuickComment(...args) {
        calls.push(["add", ...args]);
      },
      async removeQuickComment(...args) {
        calls.push(["remove", ...args]);
      },
    },
  };
  const quickComment = await addProcessingQuickComment({
    nim,
    message,
    config: {
      quickComment: {
        enabled: true,
        index: 72,
        ttlMs: 5000,
      },
    },
    setTimer(callback, ttlMs) {
      scheduled = { callback, ttlMs };
      return { unref() {} };
    },
    trackCleanup(cleanup) {
      tracked.push(cleanup);
    },
  });
  assert.deepEqual(quickComment, {
    index: 72,
    message_id: "server-1",
    cleanup_ttl_ms: 5000,
  });
  assert.equal(calls[0][0], "add");
  assert.equal(calls[0][1], message);
  assert.equal(calls[0][2], 72);
  assert.deepEqual(calls[0][4], { pushEnabled: false, needBadge: false });
  assert.equal(scheduled.ttlMs, 5000);
  assert.equal(tracked.length, 1);
  assert.equal(tracked[0].timeout.unref instanceof Function, true);
  await scheduled.callback();
  assert.equal(calls[1][0], "remove");
  assert.equal(calls[1][2], 72);
});

test("topic reply context requires topic service and valid topic refer", () => {
  const replyTopicMessage = async () => ({ message: { messageServerId: "server-topic" } });
  const nim = {
    V2NIMTopicService: {
      replyTopicMessage,
    },
  };
  const originalMessage = {
    topicRefer: {
      topicId: "7",
      conversationId: "0|1|alice",
      createTime: "12345",
    },
  };
  const context = resolveTopicReplyContext(nim, originalMessage);
  assert.deepEqual(context?.topic, {
    topicId: 7,
    conversationId: "0|1|alice",
    createTime: 12345,
  });
  assert.equal(context?.topicService.replyTopicMessage, replyTopicMessage);
});

test("topic reply context falls back when sdk service or topic refer is unavailable", () => {
  assert.equal(
    resolveTopicReplyContext(
      {
        V2NIMTopicService: {
          async replyTopicMessage() {},
        },
      },
      {
        topicRefer: {
          topicId: 0,
          conversationId: "0|1|alice",
          createTime: 1,
        },
      },
    ),
    null,
  );
  assert.equal(
    resolveTopicReplyContext(
      {},
      {
        topicRefer: {
          topicId: 1,
          conversationId: "0|1|alice",
          createTime: 1,
        },
      },
    ),
    null,
  );
});

test("text reply sender uses topic service with receiver binding when available", async () => {
  const calls = [];
  const topicService = {
    async replyTopicMessage(message, originalMessage, topic, options) {
      assert.equal(this, topicService);
      calls.push({ message, originalMessage, topic, options });
      return { message: { messageServerId: "server-topic" } };
    },
  };
  const message = { messageClientId: "client-reply" };
  const originalMessage = {
    topicRefer: {
      topicId: 9,
      conversationId: "0|1|alice",
      createTime: 12345,
    },
  };
  const result = await sendTextReplyMessage({
    nim: { V2NIMTopicService: topicService },
    messageService: {
      async replyMessage() {
        throw new Error("fallback should not be called");
      },
    },
    message,
    originalMessage,
    options: { antispamConfig: { antispamEnabled: true } },
  });

  assert.equal(result.message.messageServerId, "server-topic");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].message, message);
  assert.equal(calls[0].originalMessage, originalMessage);
  assert.deepEqual(calls[0].topic, {
    topicId: 9,
    conversationId: "0|1|alice",
    createTime: 12345,
  });
});

test("text reply sender falls back to replyMessage when topic service is unavailable", async () => {
  const calls = [];
  const message = { messageClientId: "client-reply" };
  const originalMessage = {
    topicRefer: {
      topicId: 9,
      conversationId: "0|1|alice",
      createTime: 12345,
    },
  };
  const result = await sendTextReplyMessage({
    nim: {},
    messageService: {
      async replyMessage(replyMessage, replyOriginalMessage, options) {
        calls.push({ replyMessage, replyOriginalMessage, options });
        return { message: { messageServerId: "server-fallback" } };
      },
    },
    message,
    originalMessage,
    options: { antispamConfig: { antispamEnabled: false } },
  });

  assert.equal(result.message.messageServerId, "server-fallback");
  assert.deepEqual(calls, [
    {
      replyMessage: message,
      replyOriginalMessage: originalMessage,
      options: { antispamConfig: { antispamEnabled: false } },
    },
  ]);
});

test("media sender uses topic service with receiver binding when available", async () => {
  const calls = [];
  const topicService = {
    async replyTopicMessage(message, originalMessage, topic, options) {
      assert.equal(this, topicService);
      calls.push({ message, originalMessage, topic, options });
      return { message: { messageServerId: "server-media-topic" } };
    },
  };
  const message = { messageClientId: "client-media" };
  const originalMessage = {
    topicRefer: {
      topicId: 10,
      conversationId: "0|1|alice",
      createTime: 12345,
    },
  };

  const sent = await sendMediaMaybeTopicReply({
    nim: { V2NIMTopicService: topicService },
    message,
    originalMessage,
    options: { antispamConfig: { antispamEnabled: true } },
    async sendOrdinary() {
      throw new Error("ordinary media send should not be called");
    },
  });

  assert.equal(sent.usedTopicReply, true);
  assert.equal(sent.result.message.messageServerId, "server-media-topic");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].message, message);
  assert.equal(calls[0].originalMessage, originalMessage);
  assert.deepEqual(calls[0].topic, {
    topicId: 10,
    conversationId: "0|1|alice",
    createTime: 12345,
  });
});

test("media sender falls back to ordinary send when topic context is unavailable", async () => {
  let ordinaryCalls = 0;
  const sent = await sendMediaMaybeTopicReply({
    nim: {},
    message: { messageClientId: "client-media" },
    originalMessage: {
      topicRefer: {
        topicId: 10,
        conversationId: "0|1|alice",
        createTime: 12345,
      },
    },
    options: {},
    async sendOrdinary() {
      ordinaryCalls += 1;
      return {
        message_id: "server-ordinary",
        client_message_id: "client-media",
      };
    },
  });

  assert.equal(sent.usedTopicReply, false);
  assert.deepEqual(sent.result, {
    message_id: "server-ordinary",
    client_message_id: "client-media",
  });
  assert.equal(ordinaryCalls, 1);
});

test("stream sender selects reply stream stream and fallback modes", async () => {
  const message = { messageClientId: "stream-client" };
  const originalMessage = { messageClientId: "original-client" };
  const streamChunkParams = createStreamChunkParams({
    text: "chunk",
    chunkIndex: 2,
    isComplete: false,
  });
  assert.deepEqual(streamChunkParams, {
    text: "chunk",
    index: 2,
    finish: 0,
  });

  const replyCalls = [];
  const replySent = await sendStreamTextMessage({
    messageService: {
      async replyStreamMessage(...args) {
        replyCalls.push(args);
        return { messageServerId: "reply-stream-server" };
      },
    },
    message,
    conversationId: "0|1|alice",
    originalMessage,
    options: { antispamConfig: { antispamEnabled: true } },
    streamChunkParams,
    async sendOrdinary() {
      throw new Error("ordinary send should not be called");
    },
  });
  assert.equal(replySent.mode, "reply_stream");
  assert.equal(replySent.result.messageServerId, "reply-stream-server");
  assert.deepEqual(replyCalls[0], [
    message,
    originalMessage,
    { antispamConfig: { antispamEnabled: true } },
    streamChunkParams,
  ]);

  const streamCalls = [];
  const streamSent = await sendStreamTextMessage({
    messageService: {
      async sendStreamMessage(...args) {
        streamCalls.push(args);
        return { messageServerId: "stream-server" };
      },
    },
    message,
    conversationId: "0|1|alice",
    originalMessage: null,
    options: {},
    streamChunkParams,
    async sendOrdinary() {
      throw new Error("ordinary send should not be called");
    },
  });
  assert.equal(streamSent.mode, "stream");
  assert.equal(streamCalls[0][1], "0|1|alice");

  const fallbackSent = await sendStreamTextMessage({
    messageService: {},
    message,
    conversationId: "0|1|alice",
    originalMessage: null,
    options: {},
    streamChunkParams,
    async sendOrdinary() {
      return { message_id: "fallback-server" };
    },
  });
  assert.deepEqual(fallbackSent, {
    mode: "fallback",
    result: { message_id: "fallback-server" },
  });
});

test("edit facade creates replacement text message", async () => {
  const created = [];
  const response = await sendEditReplacementMessage({
    messageCreator: {
      createTextMessage(text) {
        return { text, messageClientId: "edit-client" };
      },
    },
    text: "replacement",
    messageId: "old-message",
    async sendCreated(message) {
      created.push(message);
      return { message_id: "new-message" };
    },
  });
  assert.deepEqual(created, [{ text: "replacement", messageClientId: "edit-client" }]);
  assert.deepEqual(response, {
    message_id: "new-message",
    edited_message_id: "old-message",
  });
});

test("team name resolver falls back to team id", async () => {
  const name = await resolveTeamName(
    {
      V2NIMTeamService: {
        async getTeamInfo() {
          throw new Error("unavailable");
        },
      },
    },
    "team-fallback",
    "superTeam",
  );
  assert.equal(name, "team-fallback");
});

test("inbound media conversion preserves attachment metadata and placeholder text", async () => {
  const payload = await toInboundMessage(
    {
      conversationId: "0|1|alice",
      senderId: "alice",
      receiverId: "bot",
      messageType: 1,
      messageClientId: "client-2",
      attachment: {
        url: "https://example.com/a.png",
        name: "a.png",
        size: 1234,
        w: 320,
        h: 240,
        sceneName: "image.scene",
      },
    },
    "bot",
  );
  assert.equal(payload.message_type, "image");
  assert.equal(payload.text, "[Image] https://example.com/a.png");
  assert.equal(payload.attachment?.url, "https://example.com/a.png");
  assert.equal(payload.attachment?.width, 320);
  assert.equal(payload.attachment?.scene_name, "image.scene");
});

test("audio inbound messages are transcribed before dispatch", async () => {
  const calls = [];
  const nim = {
    V2NIMMessageService: {
      async voiceToText(params) {
        calls.push(params);
        return "transcribed audio";
      },
    },
  };

  const payload = await toInboundMessage(
    {
      conversationId: "0|1|alice",
      senderId: "alice",
      receiverId: "bot",
      messageType: 2,
      messageClientId: "client-3",
      attachment: {
        url: "https://example.com/v.aac",
        name: "voice.aac",
        dur: 12,
        sceneName: "voice.scene",
      },
    },
    "bot",
    nim,
  );

  assert.equal(payload.message_type, "audio");
  assert.equal(payload.text, "transcribed audio");
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0], {
    voiceUrl: "https://example.com/v.aac",
    duration: 12,
    sceneName: "voice.scene",
    mimeType: "aac",
    sampleRate: "16000",
  });
});

test("audio transcription falls back to the placeholder when SDK fails", async () => {
  const nim = {
    V2NIMMessageService: {
      async voiceToText() {
        throw new Error("transcribe failed");
      },
    },
  };

  const payload = await toInboundMessage(
    {
      conversationId: "0|1|alice",
      senderId: "alice",
      receiverId: "bot",
      messageType: 2,
      text: "",
      attachment: {
        url: "https://example.com/v.aac",
        dur: 12,
      },
    },
    "bot",
    nim,
  );

  assert.equal(payload.text, "[Audio] https://example.com/v.aac");
});

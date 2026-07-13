import test from "node:test";
import assert from "node:assert/strict";

import {
  buildNimConstructorOptions,
  isP2pApplicantAllowed,
  collectReadReceiptBatches,
  normalizeTarget,
  parseBridgeConfig,
  ReplyMessageCache,
  resolveTeamName,
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

import test from "node:test";
import assert from "node:assert/strict";

import {
  buildNimConstructorOptions,
  isP2pApplicantAllowed,
  normalizeTarget,
  parseBridgeConfig,
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

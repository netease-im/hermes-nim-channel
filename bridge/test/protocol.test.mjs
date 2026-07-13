import test from "node:test";
import assert from "node:assert/strict";

import {
  buildConversationId,
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

test("inbound conversion extracts mention metadata", () => {
  const payload = toInboundMessage(
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

test("inbound media conversion preserves attachment metadata and placeholder text", () => {
  const payload = toInboundMessage(
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
      },
    },
    "bot",
  );
  assert.equal(payload.message_type, "image");
  assert.equal(payload.text, "[Image] https://example.com/a.png");
  assert.equal(payload.attachment?.url, "https://example.com/a.png");
  assert.equal(payload.attachment?.width, 320);
});

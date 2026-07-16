import test from "node:test";
import assert from "node:assert/strict";

import { parseBridgeConfig } from "../src/config.mjs";
import {
  createQChatChannelInfoResolver,
  deriveQChatServerIds,
  enrichQChatMessageWithChannelInfo,
  isQChatAllowed,
  isQChatTargetAllowed,
  normalizeQChatMessage,
  normalizeQChatTarget,
  QChatReplyCache,
  registerQChatPassiveListeners,
  sendQChatText,
} from "../src/qchat.mjs";

test("bridge config parses qchat policy controls", () => {
  const parsed = parseBridgeConfig({
    nim_token: "app|bot|secret",
    qchat_policy: "allowlist",
    qchat_allow_from: ["server-a|channel-a"],
  });
  assert.equal(parsed.qchat.policy, "allowlist");
  assert.deepEqual(parsed.qchat.allowFrom, ["server-a|channel-a"]);
});

test("qchat target normalization accepts Hermes prefixes", () => {
  assert.deepEqual(normalizeQChatTarget("qchat:server-a:channel-b"), {
    serverId: "server-a",
    channelId: "channel-b",
  });
  assert.deepEqual(normalizeQChatTarget("nim:qchat:server-a:channel-b"), {
    serverId: "server-a",
    channelId: "channel-b",
  });
});

test("qchat allowlist matching uses server channel and sender scope", () => {
  assert.equal(
    isQChatAllowed({
      policy: "allowlist",
      allowFrom: ["server-a|channel-b|bot"],
      serverId: "server-a",
      channelId: "channel-b",
      senderAccid: "bot",
    }),
    true,
  );
  assert.equal(
    isQChatAllowed({
      policy: "allowlist",
      allowFrom: ["server-a|channel-b|bot"],
      serverId: "server-a",
      channelId: "channel-x",
      senderAccid: "bot",
    }),
    false,
  );
});

test("qchat outbound target policy blocks disabled and unmatched targets", () => {
  assert.equal(
    isQChatTargetAllowed({
      policy: "disabled",
      allowFrom: ["server-a|channel-b"],
      serverId: "server-a",
      channelId: "channel-b",
    }),
    false,
  );
  assert.equal(
    isQChatTargetAllowed({
      policy: "allowlist",
      allowFrom: ["server-a|channel-b|alice"],
      serverId: "server-a",
      channelId: "channel-b",
    }),
    true,
  );
  assert.equal(
    isQChatTargetAllowed({
      policy: "allowlist",
      allowFrom: ["server-a|channel-b"],
      serverId: "server-a",
      channelId: "channel-x",
    }),
    false,
  );
});

test("qchat inbound normalization preserves mention metadata", () => {
  const payload = normalizeQChatMessage(
    {
      message: {
        serverId: "server-a",
        channelId: "channel-b",
        fromAccount: "alice",
        fromNick: "Alice",
        body: "hello",
        msgIdServer: "msg-1",
        mentionAccids: ["bot"],
        mentionAll: false,
      },
    },
    "bot",
  );
  assert.equal(payload.session_type, "qchat");
  assert.equal(payload.target_id, "server-a:channel-b");
  assert.equal(payload.mentioned, true);
  assert.equal(payload.from_self, false);
});

test("qchat channel info resolver supports sdk result arrays", async () => {
  const calls = [];
  const resolver = createQChatChannelInfoResolver({
    qchatChannel: {
      async getChannels(params) {
        calls.push(params);
        return [
          {
            serverId: "server-a",
            channelId: "channel-b",
            name: "General",
            topic: "Daily work",
          },
        ];
      },
    },
  });
  const info = await resolver("server-a", "channel-b");
  assert.equal(info.name, "General");
  assert.equal(info.topic, "Daily work");
  const cached = await resolver("server-a", "channel-b");
  assert.equal(cached, info);
  assert.equal(calls.length, 1);
});

test("qchat channel info enrichment fills missing name and topic", async () => {
  const payload = normalizeQChatMessage(
    {
      message: {
        serverId: "server-a",
        channelId: "channel-b",
        fromAccount: "alice",
        body: "hello",
        msgIdServer: "msg-2",
        mentionAccids: ["bot"],
      },
    },
    "bot",
  );
  const enriched = await enrichQChatMessageWithChannelInfo(payload, async () => ({
    name: "General",
    topic: "Daily work",
  }));
  assert.equal(enriched.conversation_name, "General");
  assert.equal(enriched.channel_topic, "Daily work");
});

test("qchat allowlist server ids are derived from allowFrom entries", () => {
  assert.deepEqual(
    deriveQChatServerIds(["server-a|channel-b", "server-a|channel-c", "server-b"]),
    ["server-a", "server-b"],
  );
});

test("qchat reply cache indexes server and client ids and stays bounded", () => {
  const cache = new QChatReplyCache(2);
  const first = { msgIdServer: "server-1", msgIdClient: "client-1" };
  const second = { msgIdServer: "server-2" };
  cache.add(first);
  cache.add(second);
  assert.equal(cache.get("server-1"), null);
  assert.equal(cache.get("client-1"), first);
  assert.equal(cache.get("server-2"), second);
});

test("qchat sender uses native reply context and ordinary fallback", async () => {
  const calls = [];
  const qchatMsg = {
    async replyMessage(params) {
      calls.push(["reply", params]);
      return { message: { msgIdServer: "reply-1" } };
    },
    async sendMessage(params) {
      calls.push(["send", params]);
      return { message: { msgIdServer: "send-1" } };
    },
  };
  const target = { serverId: "server-a", channelId: "channel-b" };
  const originalMessage = { msgIdServer: "source-1" };
  const replied = await sendQChatText({ qchatMsg, target, text: "hello", originalMessage });
  const fallback = await sendQChatText({ qchatMsg, target, text: "fallback" });
  assert.equal(replied.mode, "reply");
  assert.equal(calls[0][1].replyMessage, originalMessage);
  assert.equal(fallback.mode, "send");
  assert.equal(calls[1][1].body, "fallback");
});

test("qchat passive listeners register immediately and detach together", () => {
  const calls = [];
  const qchatMsg = {
    on(event, handler) {
      calls.push(["on", event, handler]);
    },
    off(event, handler) {
      calls.push(["off", event, handler]);
    },
  };
  const onMessage = () => {};
  const onSystemNotification = () => {};
  const runtime = registerQChatPassiveListeners(qchatMsg, { onMessage, onSystemNotification });
  assert.deepEqual(calls.slice(0, 2).map((call) => call.slice(0, 2)), [
    ["on", "message"],
    ["on", "systemNotification"],
  ]);
  runtime.stop();
  assert.deepEqual(calls.slice(2).map((call) => call.slice(0, 2)), [
    ["off", "message"],
    ["off", "systemNotification"],
  ]);
});

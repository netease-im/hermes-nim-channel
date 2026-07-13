import test from "node:test";
import assert from "node:assert/strict";

import { parseBridgeConfig } from "../src/config.mjs";
import {
  deriveQChatServerIds,
  isQChatAllowed,
  isQChatTargetAllowed,
  normalizeQChatMessage,
  normalizeQChatTarget,
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

test("qchat allowlist server ids are derived from allowFrom entries", () => {
  assert.deepEqual(
    deriveQChatServerIds(["server-a|channel-b", "server-a|channel-c", "server-b"]),
    ["server-a", "server-b"],
  );
});

import test from "node:test";
import assert from "node:assert/strict";

import { QChatReplyCache } from "../src/qchat.mjs";
import { createQChatRuntime, discoverJoinedQChatServers } from "../src/qchat-runtime.mjs";

function fakeLogger() {
  return { info() {}, warn() {} };
}

function createFakeQChat() {
  const handlers = new Map();
  const calls = [];
  return {
    handlers,
    calls,
    nim: {
      qchatMsg: {
        on(event, handler) {
          calls.push(["listen", event]);
          handlers.set(event, handler);
        },
        off(event) {
          calls.push(["unlisten", event]);
          handlers.delete(event);
        },
      },
      qchatServer: {
        async getServersByPage(params) {
          calls.push(["discover", params]);
          return { datas: [{ serverId: "server-a", createTime: 1 }], listQueryTag: { hasMore: false } };
        },
        async subscribeAllChannel(params) {
          calls.push(["subscribe", params]);
          return { failServerIds: [] };
        },
        async acceptServerInvite(params) {
          calls.push(["accept", params]);
        },
      },
      qchatChannel: {
        async getChannels() {
          return [];
        },
      },
    },
  };
}

test("QChat runtime registers passive listeners before authenticated activation", async () => {
  const fake = createFakeQChat();
  const runtime = createQChatRuntime(
    fake.nim,
    { credentials: { account: "bot" }, qchat: { policy: "open", allowFrom: [] } },
    new QChatReplyCache(),
    { logger: fakeLogger() },
  );
  assert.ok(runtime);
  assert.deepEqual(fake.calls, [["listen", "message"], ["listen", "systemNotification"]]);

  await runtime.activate();
  assert.deepEqual(fake.calls.slice(2).map((call) => call[0]), ["discover", "subscribe"]);
  await runtime.stop();
  assert.deepEqual(fake.calls.slice(-3).map((call) => call[0]), ["unlisten", "unlisten", "subscribe"]);
});

test("QChat runtime accepts allowed invites and subscribes after invite completion", async () => {
  const fake = createFakeQChat();
  const runtime = createQChatRuntime(
    fake.nim,
    { credentials: { account: "bot" }, qchat: { policy: "allowlist", allowFrom: ["server-a|channel-a"] } },
    new QChatReplyCache(),
    { logger: fakeLogger() },
  );
  const notify = fake.handlers.get("systemNotification");
  await notify({
    type: "serverMemberInvite",
    serverId: "server-a",
    fromAccount: "owner",
    attach: { requestId: "request-1" },
  });
  await notify({ type: "serverMemberInviteDone", serverId: "server-a" });
  await notify({ type: "serverMemberInviteDone", serverId: "server-b" });

  const accept = fake.calls.find((call) => call[0] === "accept");
  assert.deepEqual(accept[1], {
    serverId: "server-a",
    accid: "owner",
    recordInfo: { requestId: "request-1" },
  });
  const subscribe = fake.calls.find((call) => call[0] === "subscribe");
  assert.deepEqual(subscribe[1], { type: 1, serverIds: ["server-a"] });
  assert.equal(fake.calls.filter((call) => call[0] === "subscribe").length, 1);
  await runtime.stop();
});

test("QChat joined-server discovery de-duplicates paged results", async () => {
  let page = 0;
  const ids = await discoverJoinedQChatServers({
    qchatServer: {
      async getServersByPage() {
        page += 1;
        return page === 1
          ? { datas: [{ serverId: "a", createTime: 1 }, { serverId: "a", createTime: 2 }], listQueryTag: { hasMore: true } }
          : { datas: [{ serverId: "b", createTime: 3 }], listQueryTag: { hasMore: false } };
      },
    },
  });
  assert.deepEqual(ids, ["a", "b"]);
});

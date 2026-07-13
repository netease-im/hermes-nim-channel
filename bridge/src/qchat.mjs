const QCHAT_PREFIXES = ["nim:qchat:", "qchat:"];

export function normalizeQChatTarget(chatId) {
  const raw = String(chatId ?? "").trim();
  if (!raw) {
    throw new Error("chat_id is required");
  }

  let normalized = raw;
  for (const prefix of QCHAT_PREFIXES) {
    if (normalized.toLowerCase().startsWith(prefix)) {
      normalized = normalized.slice(prefix.length);
      break;
    }
  }

  const parts = normalized.split(":", 2);
  if (parts.length !== 2 || !parts[0] || !parts[1]) {
    throw new Error(`invalid QChat target: ${chatId}`);
  }

  return {
    serverId: parts[0].trim(),
    channelId: parts[1].trim(),
  };
}

export function deriveQChatServerIds(allowFrom = []) {
  const serverIds = new Set();
  for (const entry of allowFrom) {
    const [serverId] = String(entry ?? "").split("|", 1);
    const normalized = serverId.trim();
    if (normalized) {
      serverIds.add(normalized);
    }
  }
  return [...serverIds];
}

export function isQChatAllowed({ policy, allowFrom = [], serverId, channelId, senderAccid }) {
  const normalizedPolicy = String(policy ?? "").trim().toLowerCase();
  if (normalizedPolicy === "disabled") {
    return false;
  }
  if (normalizedPolicy === "open") {
    return true;
  }
  if (!allowFrom.length) {
    return false;
  }

  const nServer = String(serverId ?? "").trim().toLowerCase();
  const nChannel = String(channelId ?? "").trim().toLowerCase();
  const nSender = String(senderAccid ?? "").trim().toLowerCase();

  return allowFrom.some((entry) => {
    const parts = String(entry ?? "").split("|");
    const entryServer = (parts[0] ?? "").trim().toLowerCase();
    const entryChannel = (parts[1] ?? "").trim().toLowerCase();
    const entrySender = (parts[2] ?? "").trim().toLowerCase();

    if (!entryServer || entryServer !== nServer) {
      return false;
    }
    if (entryChannel && entryChannel !== nChannel) {
      return false;
    }
    if (entrySender && entrySender !== nSender) {
      return false;
    }
    return true;
  });
}

function normalizeMessageType(message) {
  const type = message?.type ?? (typeof message?.msg_type === "string" ? message.msg_type : undefined);
  const legacyType = typeof message?.msg_type === "number" ? message.msg_type : undefined;
  if (type && type !== "text") {
    return null;
  }
  if (legacyType !== undefined && legacyType !== 0) {
    return null;
  }
  return "text";
}

export function normalizeQChatMessage(message, botAccount) {
  const msg = message?.message ?? message ?? {};
  if (!msg || typeof msg !== "object") {
    return null;
  }

  const messageType = normalizeMessageType(msg);
  if (!messageType) {
    return null;
  }

  const serverId = String(msg.serverId ?? msg.server_id ?? "").trim();
  const channelId = String(msg.channelId ?? msg.channel_id ?? "").trim();
  const senderAccid = String(msg.fromAccount ?? msg.from_accid ?? "").trim();
  const text = String(msg.body ?? msg.msg_body ?? "").trim();
  if (!serverId || !channelId || !senderAccid || !text) {
    return null;
  }

  const mentionAccids = Array.isArray(msg.mentionAccids ?? msg.mention_accids)
    ? (msg.mentionAccids ?? msg.mention_accids)
    : [];
  const mentionAll = (msg.mentionAll ?? msg.mention_all) === true;
  const mentioned = mentionAll || mentionAccids.includes(botAccount);

  return {
    message_id: String(msg.msgIdServer ?? msg.msg_server_id ?? `${Date.now()}`),
    client_message_id: String(msg.msg_server_id ?? msg.msgIdServer ?? ""),
    session_type: "qchat",
    sender_id: senderAccid,
    sender_name: msg.fromNick ?? msg.from_nick ?? null,
    target_id: `${serverId}:${channelId}`,
    server_id: serverId,
    channel_id: channelId,
    conversation_name: msg.channelName ?? msg.channel_name ?? null,
    text,
    message_type: messageType,
    force_push_account_ids: mentionAccids,
    mention_accids: mentionAccids,
    mentioned,
    mention_all: mentionAll,
    from_self: senderAccid === String(botAccount ?? ""),
    raw: msg,
  };
}

export function normalizeQChatSystemNotification(notification) {
  const raw = notification?.notification ?? notification ?? {};
  const serverId =
    raw.serverId ??
    raw.server_id ??
    raw.attach?.serverInfo?.serverId ??
    null;
  const type =
    raw.type ??
    (typeof raw.msg_type === "string" ? raw.msg_type : undefined);
  const legacyType =
    typeof raw.msg_type === "number" ? raw.msg_type : undefined;

  const normalizedType =
    type ??
    (legacyType === 1
      ? "serverMemberInvite"
      : legacyType === 8
        ? "serverMemberInviteDone"
        : undefined);

  return {
    ...raw,
    serverId,
    server_id: serverId,
    type: normalizedType,
    msg_type: normalizedType,
  };
}

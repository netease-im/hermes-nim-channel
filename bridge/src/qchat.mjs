const QCHAT_PREFIXES = ["nim:qchat:", "qchat:"];

export function registerQChatPassiveListeners(qchatMsg, { onMessage, onSystemNotification }) {
  if (typeof qchatMsg?.on !== "function") {
    throw new Error("qchat event API is unavailable");
  }
  qchatMsg.on("message", onMessage);
  qchatMsg.on("systemNotification", onSystemNotification);
  return {
    stop() {
      qchatMsg.off?.("message", onMessage);
      qchatMsg.off?.("systemNotification", onSystemNotification);
    },
  };
}

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

export function isQChatTargetAllowed({ policy, allowFrom = [], serverId, channelId }) {
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

  return allowFrom.some((entry) => {
    const parts = String(entry ?? "").split("|");
    const entryServer = (parts[0] ?? "").trim().toLowerCase();
    const entryChannel = (parts[1] ?? "").trim().toLowerCase();

    if (!entryServer || entryServer !== nServer) {
      return false;
    }
    if (entryChannel && entryChannel !== nChannel) {
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
    client_message_id: String(msg.msgIdClient ?? msg.msg_client_id ?? ""),
    session_type: "qchat",
    sender_id: senderAccid,
    sender_name: msg.fromNick ?? msg.from_nick ?? null,
    target_id: `${serverId}:${channelId}`,
    server_id: serverId,
    channel_id: channelId,
    conversation_name: msg.channelName ?? msg.channel_name ?? null,
    channel_topic: msg.channelTopic ?? msg.channel_topic ?? null,
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

export function createQChatChannelInfoResolver(nim, ttlMs = 60 * 60 * 1000) {
  const cache = new Map();
  const timestamps = new Map();

  return async function resolveQChatChannelInfo(serverId, channelId) {
    const normalizedChannelId = String(channelId ?? "").trim();
    if (!normalizedChannelId || !nim?.qchatChannel?.getChannels) {
      return null;
    }

    const now = Date.now();
    const cached = cache.get(normalizedChannelId);
    const cachedAt = timestamps.get(normalizedChannelId) ?? 0;
    if (cached && now - cachedAt < ttlMs) {
      return cached;
    }

    try {
      const result = await nim.qchatChannel.getChannels({
        channelIds: [normalizedChannelId],
      });
      const channels = Array.isArray(result) ? result : Array.isArray(result?.datas) ? result.datas : [];
      const channelInfo = channels[0] ?? null;
      if (!channelInfo) {
        return null;
      }
      const normalized = {
        serverId: String(channelInfo.serverId ?? serverId ?? "").trim() || null,
        channelId: String(channelInfo.channelId ?? channelInfo.id ?? normalizedChannelId).trim(),
        name: String(channelInfo.name ?? channelInfo.channelName ?? "").trim() || null,
        topic: String(channelInfo.topic ?? channelInfo.channelTopic ?? "").trim() || null,
        raw: channelInfo,
      };
      cache.set(normalizedChannelId, normalized);
      timestamps.set(normalizedChannelId, now);
      return normalized;
    } catch {
      return null;
    }
  };
}

export async function enrichQChatMessageWithChannelInfo(payload, resolveChannelInfo) {
  if (!payload || typeof payload !== "object" || typeof resolveChannelInfo !== "function") {
    return payload;
  }
  const channelInfo = await resolveChannelInfo(payload.server_id, payload.channel_id);
  if (!channelInfo) {
    return payload;
  }
  return {
    ...payload,
    conversation_name: payload.conversation_name ?? channelInfo.name,
    channel_topic: payload.channel_topic ?? channelInfo.topic,
    channel_info: channelInfo,
  };
}

export class QChatReplyCache {
  constructor(limit = 500) {
    this.limit = Math.max(1, Number(limit) || 500);
    this.entries = new Map();
  }

  add(message) {
    const raw = message?.message ?? message;
    const keys = [raw?.msgIdServer, raw?.msg_server_id, raw?.msgIdClient, raw?.msg_client_id]
      .map((value) => String(value ?? "").trim())
      .filter(Boolean);
    for (const key of keys) {
      this.entries.delete(key);
      this.entries.set(key, raw);
    }
    while (this.entries.size > this.limit) {
      this.entries.delete(this.entries.keys().next().value);
    }
  }

  get(messageId) {
    const key = String(messageId ?? "").trim();
    return key ? this.entries.get(key) ?? null : null;
  }

  clear() {
    this.entries.clear();
  }
}

export async function sendQChatText({ qchatMsg, target, text, originalMessage = null }) {
  const payload = {
    serverId: target.serverId,
    channelId: target.channelId,
    type: "text",
    body: String(text ?? ""),
  };
  if (originalMessage && typeof qchatMsg?.replyMessage === "function") {
    return {
      mode: "reply",
      response: await qchatMsg.replyMessage({ ...payload, replyMessage: originalMessage }),
    };
  }
  if (typeof qchatMsg?.sendMessage !== "function") {
    throw new Error("qchat sendMessage is unavailable");
  }
  return {
    mode: originalMessage ? "reply_fallback" : "send",
    response: await qchatMsg.sendMessage(payload),
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

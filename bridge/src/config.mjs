function parseNimToken(value) {
  const raw = String(value ?? "").trim();
  if (!raw) {
    return null;
  }
  const parts = raw.includes("|") ? raw.split("|", 3) : raw.split("-", 3);
  if (parts.length !== 3 || parts.some((part) => !part)) {
    return null;
  }
  return {
    appKey: parts[0],
    account: parts[1],
    token: parts[2],
  };
}

export function parseBridgeConfig(raw) {
  const credentials = raw?.credentials ?? {};
  const shorthand = parseNimToken(raw?.nim_token ?? raw?.nimToken);
  const resolved = shorthand ?? {
    appKey: String(credentials.app_key ?? credentials.appKey ?? ""),
    account: String(credentials.account ?? ""),
    token: String(credentials.token ?? ""),
  };

  if (!resolved.appKey || !resolved.account || !resolved.token) {
    throw new Error("bridge credentials are incomplete");
  }

  return {
    credentials: resolved,
    debug: Boolean(raw?.debug),
    mediaMaxMb: Number(raw?.media_max_mb ?? raw?.mediaMaxMb ?? 30),
    homeChannel: raw?.home_channel ?? raw?.homeChannel ?? null,
    qchat: {
      policy: String(raw?.qchat?.policy ?? raw?.qchat_policy ?? raw?.qchatPolicy ?? "open").trim() || "open",
      allowFrom: Array.isArray(raw?.qchat?.allowFrom)
        ? raw.qchat.allowFrom
        : Array.isArray(raw?.qchat_allow_from)
          ? raw.qchat_allow_from
          : Array.isArray(raw?.qchatAllowFrom)
            ? raw.qchatAllowFrom
            : [],
    },
  };
}

export function normalizeTarget(chatId, fallbackSessionType = "p2p") {
  const raw = String(chatId ?? "").trim();
  if (!raw) {
    throw new Error("chat_id is required");
  }

  if (raw.startsWith("team:") || raw.startsWith("group:")) {
    return {
      id: raw.slice(raw.indexOf(":") + 1),
      sessionType: "team",
    };
  }

  if (raw.startsWith("user:") || raw.startsWith("nim:")) {
    return {
      id: raw.slice(raw.indexOf(":") + 1),
      sessionType: "p2p",
    };
  }

  return {
    id: raw,
    sessionType: fallbackSessionType,
  };
}

export function buildConversationId(nim, targetId, sessionType) {
  const util = nim?.V2NIMConversationIdUtil;
  if (util) {
    if (sessionType === "team") {
      return util.teamConversationId(targetId) || `0|2|${targetId}`;
    }
    if (sessionType === "superTeam") {
      return util.superTeamConversationId(targetId) || `0|3|${targetId}`;
    }
    return util.p2pConversationId(targetId) || `0|1|${targetId}`;
  }

  const typeNumber = sessionType === "team" ? 2 : sessionType === "superTeam" ? 3 : 1;
  return `0|${typeNumber}|${targetId}`;
}

export function parseConversationId(conversationId) {
  const parts = String(conversationId ?? "").split("|");
  if (parts.length < 3) {
    return { sessionType: "p2p", targetId: "" };
  }
  const typeNumber = Number(parts[1]);
  return {
    sessionType: typeNumber === 2 ? "team" : typeNumber === 3 ? "superTeam" : "p2p",
    targetId: parts[2],
  };
}

function normalizeAttachment(attach) {
  if (!attach || typeof attach !== "object") {
    return null;
  }

  const url = String(attach.url ?? "").trim();
  if (!url) {
    return null;
  }

  return {
    url,
    name: attach.name ?? null,
    size: attach.size ?? null,
    mime_type: null,
    width: attach.w ?? null,
    height: attach.h ?? null,
    duration: attach.dur ?? null,
    scene_name: attach.sceneName ?? attach.scene_name ?? null,
  };
}

function extractInboundText(messageType, text, attachment) {
  const content = String(text ?? "");
  if (content.trim()) {
    return content;
  }

  const attachmentUrl = attachment?.url ?? "";
  const placeholders = {
    image: "[Image]",
    audio: "[Audio]",
    video: "[Video]",
    file: "[File]",
  };
  const prefix = placeholders[messageType] ?? "";
  return prefix ? `${prefix} ${attachmentUrl}`.trim() : content;
}

async function maybeTranscribeAudio(nim, attachment) {
  const voiceService = nim?.V2NIMMessageService;
  if (!voiceService?.voiceToText || !attachment?.url || !Number.isFinite(Number(attachment.duration)) || Number(attachment.duration) <= 0) {
    return null;
  }

  try {
    const transcribedText = await voiceService.voiceToText({
      voiceUrl: attachment.url,
      duration: Number(attachment.duration),
      sceneName: attachment.scene_name ?? undefined,
      mimeType: "aac",
      sampleRate: "16000",
    });
    const normalized = String(transcribedText ?? "").trim();
    return normalized || null;
  } catch {
    return null;
  }
}

export async function toInboundMessage(message, botAccount, nim = null) {
  const parsed = parseConversationId(message?.conversationId);
  const pushIds = message?.pushConfig?.forcePushAccountIds ?? [];
  const mentioned = pushIds.includes(botAccount);
  const typeMap = {
    0: "text",
    1: "image",
    2: "audio",
    3: "video",
    6: "file",
  };
  const messageType = typeMap[message?.messageType] ?? "unknown";
  const attachment = normalizeAttachment(message?.attachment ?? message?.attach);
  let text = extractInboundText(messageType, message?.text, attachment);

  if (messageType === "audio") {
    const transcribedText = await maybeTranscribeAudio(nim, attachment);
    if (transcribedText) {
      text = transcribedText;
    }
  }

  return {
    message_id: String(message?.messageServerId ?? message?.messageClientId ?? ""),
    client_message_id: String(message?.messageClientId ?? ""),
    session_type: parsed.sessionType,
    sender_id: String(message?.senderId ?? ""),
    sender_name: message?.senderName ?? null,
    target_id: String(message?.receiverId ?? parsed.targetId ?? ""),
    conversation_name: null,
    text,
    message_type: messageType,
    attachment,
    force_push_account_ids: pushIds,
    mentioned,
    mention_all: false,
    from_self: String(message?.senderId ?? "") === String(botAccount ?? ""),
    raw: message,
  };
}

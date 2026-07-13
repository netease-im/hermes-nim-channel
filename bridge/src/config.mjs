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

  const advanced = raw?.advanced ?? {};

  return {
    credentials: resolved,
    debug: Boolean(raw?.debug),
    mediaMaxMb: Number(raw?.media_max_mb ?? raw?.mediaMaxMb ?? 30),
    textChunkLimit: Number(raw?.text_chunk_limit ?? raw?.textChunkLimit ?? raw?.advanced?.textChunkLimit ?? 4000),
    homeChannel: raw?.home_channel ?? raw?.homeChannel ?? null,
    p2p: {
      policy: String(raw?.p2p?.policy ?? raw?.p2p_policy ?? raw?.p2pPolicy ?? "open").trim() || "open",
      allowFrom: Array.isArray(raw?.p2p?.allowFrom)
        ? raw.p2p.allowFrom
        : Array.isArray(raw?.p2p_allow_from)
          ? raw.p2p_allow_from
          : Array.isArray(raw?.p2pAllowFrom)
            ? raw.p2pAllowFrom
            : [],
    },
    advanced: {
      weblbsUrl: advanced.weblbsUrl ?? raw?.weblbsUrl ?? raw?.weblbs_url ?? null,
      link_web: advanced.link_web ?? raw?.link_web ?? null,
      nos_uploader: advanced.nos_uploader ?? raw?.nos_uploader ?? null,
      nos_downloader_v2: advanced.nos_downloader_v2 ?? raw?.nos_downloader_v2 ?? null,
      nosSsl: advanced.nosSsl ?? raw?.nosSsl ?? raw?.nos_ssl ?? null,
      nos_accelerate: advanced.nos_accelerate ?? raw?.nos_accelerate ?? null,
      nos_accelerate_host: advanced.nos_accelerate_host ?? raw?.nos_accelerate_host ?? null,
    },
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

export function isP2pApplicantAllowed({ policy = "open", allowFrom = [], applicantId = "" } = {}) {
  const normalizedPolicy = String(policy ?? "open").trim() || "open";
  const normalizedApplicant = String(applicantId ?? "").trim().toLowerCase();
  if (!normalizedApplicant || normalizedPolicy === "disabled") {
    return false;
  }
  if (normalizedPolicy === "open") {
    return true;
  }
  if (normalizedPolicy !== "allowlist") {
    return false;
  }
  return (Array.isArray(allowFrom) ? allowFrom : [])
    .map((item) => String(item ?? "").trim().toLowerCase())
    .filter(Boolean)
    .includes(normalizedApplicant);
}

function setStringOption(target, key, value) {
  const normalized = String(value ?? "").trim();
  if (normalized) {
    target[key] = normalized;
  }
}

function normalizedString(value) {
  const normalized = String(value ?? "").trim();
  return normalized || null;
}

function optionalBoolean(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (typeof value === "boolean") {
    return value;
  }
  return ["1", "true", "yes", "on"].includes(String(value).trim().toLowerCase());
}

export function buildNimConstructorOptions(config) {
  const advanced = config?.advanced ?? {};
  const weblbsUrl = normalizedString(advanced.weblbsUrl);
  const linkWeb = normalizedString(advanced.link_web);
  const nosSsl = optionalBoolean(advanced.nosSsl);
  const privateConf = {};

  setStringOption(privateConf, "weblbsUrl", weblbsUrl);
  setStringOption(privateConf, "link_web", linkWeb);
  setStringOption(privateConf, "nos_uploader", advanced.nos_uploader);
  setStringOption(privateConf, "nos_downloader_v2", advanced.nos_downloader_v2);
  if (nosSsl !== null) {
    privateConf.nosSsl = nosSsl;
  }
  setStringOption(privateConf, "nos_accelerate", advanced.nos_accelerate);
  setStringOption(privateConf, "nos_accelerate_host", advanced.nos_accelerate_host);

  const options = {};
  if (Object.keys(privateConf).length > 0) {
    options.privateConf = privateConf;
  }

  if (weblbsUrl || linkWeb) {
    const loginServiceConfig = {};
    if (weblbsUrl) {
      loginServiceConfig.lbsUrls = [weblbsUrl];
    }
    if (linkWeb) {
      loginServiceConfig.linkUrl = linkWeb;
    }
    options.V2NIMLoginServiceConfig = loginServiceConfig;
  }

  return options;
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

export function collectReadReceiptBatches(messages = [], batchSize = 50) {
  const p2p = [];
  const team = [];
  const safeBatchSize = Math.max(1, Number(batchSize) || 50);

  for (const message of Array.isArray(messages) ? messages : []) {
    if (message?.messageSource !== 1) {
      continue;
    }
    const { sessionType } = parseConversationId(message?.conversationId ?? "");
    if (sessionType === "p2p") {
      p2p.push(message);
    } else if (sessionType === "team" || sessionType === "superTeam") {
      team.push(message);
    }
  }

  const teamBatches = [];
  for (let index = 0; index < team.length; index += safeBatchSize) {
    teamBatches.push(team.slice(index, index + safeBatchSize));
  }

  return {
    p2p,
    teamBatches,
  };
}

export class ReplyMessageCache {
  constructor(limit = 200) {
    this.limit = Math.max(1, Number(limit) || 200);
    this.entries = new Map();
  }

  add(message) {
    const keys = [
      message?.messageServerId,
      message?.messageClientId,
    ]
      .map((value) => String(value ?? "").trim())
      .filter(Boolean);
    if (keys.length === 0) {
      return;
    }
    for (const key of keys) {
      if (this.entries.has(key)) {
        this.entries.delete(key);
      }
      this.entries.set(key, message);
    }
    while (this.entries.size > this.limit) {
      const oldestKey = this.entries.keys().next().value;
      this.entries.delete(oldestKey);
    }
  }

  get(messageId) {
    const key = String(messageId ?? "").trim();
    if (!key) {
      return null;
    }
    return this.entries.get(key) ?? null;
  }
}

export function splitMessageIntoChunks(text, maxLength = 4000) {
  const limit = Math.max(1, Number(maxLength) || 4000);
  const content = String(text ?? "");
  if (content.length <= limit) {
    return [content];
  }

  const chunks = [];
  let remaining = content;

  while (remaining.length > 0) {
    if (remaining.length <= limit) {
      chunks.push(remaining);
      break;
    }

    let splitIndex = remaining.lastIndexOf("\n", limit);
    if (splitIndex === -1 || splitIndex < limit * 0.5) {
      splitIndex = remaining.lastIndexOf(" ", limit);
    }
    if (splitIndex === -1 || splitIndex < limit * 0.5) {
      splitIndex = limit;
    }

    chunks.push(remaining.slice(0, splitIndex));
    remaining = remaining.slice(splitIndex).trimStart();
  }

  return chunks;
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

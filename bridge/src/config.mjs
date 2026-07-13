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
  const legacyLogin = optionalBoolean(raw?.legacy_login ?? raw?.legacyLogin ?? advanced.legacyLogin);
  const antispamEnabled = optionalBoolean(raw?.antispam_enabled ?? raw?.antispamEnabled);

  return {
    credentials: resolved,
    debug: Boolean(raw?.debug),
    mediaMaxMb: Number(raw?.media_max_mb ?? raw?.mediaMaxMb ?? 30),
    textChunkLimit: Number(raw?.text_chunk_limit ?? raw?.textChunkLimit ?? raw?.advanced?.textChunkLimit ?? 4000),
    inboundDebounceMs: Number(raw?.inbound_debounce_ms ?? raw?.inboundDebounceMs ?? raw?.advanced?.inboundDebounceMs ?? 0),
    quickComment: {
      enabled: optionalBoolean(raw?.quick_comment?.enabled ?? raw?.quickComment?.enabled ?? raw?.quick_comment_enabled ?? raw?.quickCommentEnabled) ?? false,
      index: Number(raw?.quick_comment?.index ?? raw?.quickComment?.index ?? raw?.quick_comment_index ?? raw?.quickCommentIndex ?? 71),
      ttlMs: Number(raw?.quick_comment?.ttl_ms ?? raw?.quickComment?.ttlMs ?? raw?.quick_comment_ttl_ms ?? raw?.quickCommentTtlMs ?? 30000),
    },
    legacyLogin: legacyLogin ?? false,
    antispamEnabled: antispamEnabled ?? true,
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

const teamNameCache = new Map();

export async function resolveTeamName(nim, teamId, sessionType = "team") {
  const normalizedTeamId = String(teamId ?? "").trim();
  if (!normalizedTeamId) {
    return null;
  }
  const normalizedSessionType = sessionType === "superTeam" ? "superTeam" : "team";
  const cacheKey = `${normalizedSessionType}:${normalizedTeamId}`;
  if (teamNameCache.has(cacheKey)) {
    return teamNameCache.get(cacheKey);
  }

  let name = normalizedTeamId;
  try {
    const teamService = nim?.V2NIMTeamService;
    if (teamService?.getTeamInfo) {
      const teamType = normalizedSessionType === "superTeam" ? 2 : 1;
      const teamInfo = await teamService.getTeamInfo(normalizedTeamId, teamType);
      const resolvedName = String(teamInfo?.name ?? "").trim();
      if (resolvedName) {
        name = resolvedName;
      }
    }
  } catch {
    name = normalizedTeamId;
  }

  teamNameCache.set(cacheKey, name);
  return name;
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

export function normalizeTopicRefer(topicRefer) {
  if (!topicRefer || typeof topicRefer !== "object") {
    return null;
  }
  const topicId = Number(topicRefer.topicId);
  const conversationId = String(topicRefer.conversationId ?? "").trim();
  const createTime = Number(topicRefer.createTime);
  if (!Number.isFinite(topicId) || topicId <= 0 || !conversationId || !Number.isFinite(createTime) || createTime <= 0) {
    return null;
  }
  return {
    topicId,
    conversationId,
    createTime,
  };
}

export function normalizeTopicInfo(topic, fallbackRefer = null) {
  if (!topic || typeof topic !== "object") {
    return null;
  }
  const fallback = normalizeTopicRefer(fallbackRefer);
  const topicId = Number(topic.topicId ?? fallback?.topicId);
  const conversationId = String(topic.conversationId ?? fallback?.conversationId ?? "").trim();
  const createTime = Number(topic.createTime ?? fallback?.createTime);
  if (!Number.isFinite(topicId) || topicId <= 0 || !conversationId || !Number.isFinite(createTime) || createTime <= 0) {
    return null;
  }
  const info = {
    topicId,
    conversationId,
    createTime,
  };
  const topicName = String(topic.topicName ?? "").trim();
  if (topicName) {
    info.topicName = topicName;
  }
  for (const key of ["messageClientId", "messageServerId", "serverExtension"]) {
    const value = String(topic[key] ?? "").trim();
    if (value) {
      info[key] = value;
    }
  }
  for (const key of ["messageTime", "updateTime"]) {
    const value = Number(topic[key]);
    if (Number.isFinite(value) && value > 0) {
      info[key] = value;
    }
  }
  return info;
}

const topicInfoCache = new Map();

export async function resolveTopicInfo(nim, topicRefer) {
  const refer = normalizeTopicRefer(topicRefer);
  if (!refer) {
    return null;
  }
  const cacheKey = `${refer.conversationId}:${refer.topicId}:${refer.createTime}`;
  if (topicInfoCache.has(cacheKey)) {
    return topicInfoCache.get(cacheKey);
  }
  let topicInfo = null;
  try {
    const topicService = nim?.V2NIMTopicService;
    if (typeof topicService?.getTopicByRefer === "function") {
      topicInfo = normalizeTopicInfo(await topicService.getTopicByRefer(refer), refer);
    }
  } catch {
    topicInfo = null;
  }
  const resolved = topicInfo ?? refer;
  topicInfoCache.set(cacheKey, resolved);
  return resolved;
}

export function resolveTopicReplyContext(nim, originalMessage) {
  const topic = normalizeTopicRefer(originalMessage?.topicRefer);
  const topicService = nim?.V2NIMTopicService;
  if (!topic || typeof topicService?.replyTopicMessage !== "function") {
    return null;
  }
  return {
    topic,
    topicService,
  };
}

export function resolveQuickCommentIndex(value) {
  const index = Number(value ?? 71);
  return Number.isInteger(index) && index >= 1 ? index : 71;
}

export function deriveMessageRefer(message) {
  if (!message || typeof message !== "object") {
    return null;
  }
  const senderId = String(message.senderId ?? "").trim();
  const receiverId = String(message.receiverId ?? "").trim();
  const messageClientId = String(message.messageClientId ?? "").trim();
  const messageServerId = String(message.messageServerId ?? "").trim();
  const conversationId = String(message.conversationId ?? "").trim();
  const createTime = Number(message.createTime);
  const conversationType = Number(message.conversationType);
  if (!senderId || !receiverId || !messageClientId || !messageServerId || !conversationId || !Number.isFinite(createTime) || !Number.isFinite(conversationType)) {
    return null;
  }
  return {
    senderId,
    receiverId,
    messageClientId,
    messageServerId,
    createTime,
    conversationType,
    conversationId,
  };
}

export function addBatchMetadata(payload, { batchId, batchKey, batchIndex, batchSize } = {}) {
  if (!batchId || !batchKey || !Number.isFinite(Number(batchIndex)) || !Number.isFinite(Number(batchSize))) {
    return payload;
  }
  return {
    ...payload,
    batch_id: batchId,
    batch_key: batchKey,
    batch_index: Number(batchIndex),
    batch_size: Number(batchSize),
  };
}

export function inboundBatchKey(payload) {
  const sessionType = String(payload?.session_type ?? "p2p");
  if (sessionType === "p2p") {
    return `p2p:${String(payload?.sender_id ?? payload?.target_id ?? "unknown")}`;
  }
  if (sessionType === "qchat") {
    return `qchat:${String(payload?.target_id ?? "unknown")}`;
  }
  return `${sessionType}:${String(payload?.target_id ?? payload?.sender_id ?? "unknown")}`;
}

export class InboundBatchEmitter {
  constructor({ debounceMs = 0, emitBatch }) {
    this.debounceMs = Math.max(0, Number(debounceMs) || 0);
    this.emitBatch = emitBatch;
    this.buffers = new Map();
    this.nextSeq = 0;
  }

  enqueue(batchKey, item) {
    if (this.debounceMs <= 0) {
      this.nextSeq += 1;
      void this.emitBatch([item], batchKey, `${batchKey}:${Date.now()}:${this.nextSeq}`);
      return;
    }
    const existing = this.buffers.get(batchKey);
    if (existing) {
      existing.items.push(item);
      clearTimeout(existing.timeout);
      existing.timeout = this.schedule(batchKey, existing);
      return;
    }
    this.nextSeq += 1;
    const buffer = {
      batchId: `${batchKey}:${Date.now()}:${this.nextSeq}`,
      items: [item],
      timeout: null,
    };
    buffer.timeout = this.schedule(batchKey, buffer);
    this.buffers.set(batchKey, buffer);
  }

  schedule(batchKey, buffer) {
    const timeout = setTimeout(() => {
      this.flush(batchKey, buffer);
    }, this.debounceMs);
    timeout.unref?.();
    return timeout;
  }

  flush(batchKey, buffer) {
    if (this.buffers.get(batchKey) !== buffer) {
      return;
    }
    this.buffers.delete(batchKey);
    clearTimeout(buffer.timeout);
    void this.emitBatch(buffer.items, batchKey, buffer.batchId);
  }

  stop() {
    for (const [batchKey, buffer] of this.buffers) {
      this.flush(batchKey, buffer);
    }
  }
}

export async function addProcessingQuickComment({ nim, message, config, setTimer = setTimeout, trackCleanup = null, log = console.warn }) {
  const quickConfig = config?.quickComment ?? {};
  if (!quickConfig.enabled) {
    return null;
  }
  const messageService = nim?.V2NIMMessageService;
  if (typeof messageService?.addQuickComment !== "function") {
    return null;
  }
  const messageRefer = deriveMessageRefer(message);
  if (!messageRefer) {
    return null;
  }
  const index = resolveQuickCommentIndex(quickConfig.index);
  try {
    await messageService.addQuickComment(message, index, undefined, {
      pushEnabled: false,
      needBadge: false,
    });
    const ttlMs = Math.max(1000, Number(quickConfig.ttlMs) || 30000);
    let cleaned = false;
    const cleanup = () => {
      if (cleaned) {
        return Promise.resolve();
      }
      cleaned = true;
      return Promise.resolve(messageService.removeQuickComment?.(messageRefer, index)).catch((error) => {
        log(`[nim] quick comment cleanup failed — error: ${error instanceof Error ? error.message : String(error)}`);
      });
    };
    const timeout = setTimer(cleanup, ttlMs);
    timeout?.unref?.();
    trackCleanup?.({ timeout, cleanup });
    return {
      index,
      message_id: String(message?.messageServerId ?? message?.messageClientId ?? ""),
      cleanup_ttl_ms: ttlMs,
    };
  } catch (error) {
    log(`[nim] quick comment add failed — error: ${error instanceof Error ? error.message : String(error)}`);
    return null;
  }
}

export async function sendTextReplyMessage({ nim, messageService, message, originalMessage, options }) {
  const topicReplyContext = resolveTopicReplyContext(nim, originalMessage);
  if (topicReplyContext) {
    return topicReplyContext.topicService.replyTopicMessage(
      message,
      originalMessage,
      topicReplyContext.topic,
      options,
    );
  }
  if (typeof messageService?.replyMessage !== "function") {
    throw new Error("reply_message is unavailable");
  }
  return messageService.replyMessage(message, originalMessage, options);
}

export async function sendMediaMaybeTopicReply({ nim, message, originalMessage, options, sendOrdinary }) {
  const topicReplyContext = resolveTopicReplyContext(nim, originalMessage);
  if (topicReplyContext) {
    return {
      usedTopicReply: true,
      result: await topicReplyContext.topicService.replyTopicMessage(
        message,
        originalMessage,
        topicReplyContext.topic,
        options,
      ),
    };
  }
  return {
    usedTopicReply: false,
    result: await sendOrdinary(),
  };
}

export function createStreamChunkParams({ text = "", chunkIndex = 0, isComplete = true } = {}) {
  const index = Number(chunkIndex);
  return {
    text: String(text ?? ""),
    index: Number.isFinite(index) ? index : 0,
    finish: isComplete ? 1 : 0,
  };
}

export async function sendStreamTextMessage({ messageService, message, conversationId, originalMessage, options, streamChunkParams, sendOrdinary }) {
  if (originalMessage && typeof messageService?.replyStreamMessage === "function") {
    return {
      mode: "reply_stream",
      result: await messageService.replyStreamMessage(
        message,
        originalMessage,
        options,
        streamChunkParams,
      ),
    };
  }
  if (typeof messageService?.sendStreamMessage === "function") {
    return {
      mode: "stream",
      result: await messageService.sendStreamMessage(
        message,
        conversationId,
        options,
        streamChunkParams,
      ),
    };
  }
  return {
    mode: "fallback",
    result: await sendOrdinary(),
  };
}

export async function sendEditReplacementMessage({ messageCreator, text, messageId = "", sendCreated }) {
  const message = messageCreator?.createTextMessage?.(String(text ?? ""));
  if (!message) {
    throw new Error("failed to create edit replacement message");
  }
  const result = await sendCreated(message);
  return {
    ...result,
    edited_message_id: String(messageId ?? ""),
  };
}

export function normalizeConnectionStatus(kind, value = null) {
  if (kind === "login") {
    const code = typeof value === "object" && value !== null
      ? Number(value.code ?? value.status)
      : Number(value);
    if (code === 1) {
      return { status: "connected", reason: "login" };
    }
    if (code === 0) {
      return { status: "logout", reason: "login_status" };
    }
    if (code === 2) {
      return { status: "connecting", reason: "login_status" };
    }
    return { status: "unknown", reason: "login_status", raw: value ?? null };
  }
  if (kind === "kickout") {
    return { status: "kickout", reason: detailMessage(value) };
  }
  if (kind === "disconnected") {
    return { status: "disconnected", reason: detailMessage(value) };
  }
  return { status: "unknown", reason: String(kind ?? "unknown"), raw: value ?? null };
}

function detailMessage(value) {
  if (value instanceof Error) {
    return value.message;
  }
  if (value && typeof value === "object") {
    return String(value.reasonDesc ?? value.reason ?? value.message ?? value.desc ?? "unknown");
  }
  return String(value ?? "unknown");
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
  const targetId = String(message?.receiverId ?? parsed.targetId ?? "");
  const conversationName =
    parsed.sessionType === "team" || parsed.sessionType === "superTeam"
      ? await resolveTeamName(nim, targetId, parsed.sessionType)
      : null;

  const topicRefer = normalizeTopicRefer(message?.topicRefer);
  const topicInfo = topicRefer ? await resolveTopicInfo(nim, topicRefer) : null;
  const topicName = String(topicInfo?.topicName ?? "").trim() || null;

  return {
    message_id: String(message?.messageServerId ?? message?.messageClientId ?? ""),
    client_message_id: String(message?.messageClientId ?? ""),
    session_type: parsed.sessionType,
    sender_id: String(message?.senderId ?? ""),
    sender_name: message?.senderName ?? null,
    target_id: targetId,
    conversation_name: conversationName,
    text,
    message_type: messageType,
    attachment,
    force_push_account_ids: pushIds,
    mentioned,
    mention_all: false,
    topic_refer: topicRefer,
    topic_info: topicInfo,
    topic_name: topicName,
    thread_reply: message?.threadReply ?? null,
    from_self: String(message?.senderId ?? "") === String(botAccount ?? ""),
    raw: message,
  };
}

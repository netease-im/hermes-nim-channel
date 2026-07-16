import {
  createQChatChannelInfoResolver,
  deriveQChatServerIds,
  enrichQChatMessageWithChannelInfo,
  normalizeQChatMessage,
  normalizeQChatSystemNotification,
  registerQChatPassiveListeners,
} from "./qchat.mjs";

export async function discoverJoinedQChatServers(nim) {
  const serverIds = [];
  let timestamp = 0;
  const pageLimit = 100;

  for (let page = 0; page < 20; page += 1) {
    const resp = await nim.qchatServer.getServersByPage({ timestamp, limit: pageLimit });
    const servers = resp.datas ?? [];
    if (servers.length === 0) {
      break;
    }
    for (const server of servers) {
      if (server?.serverId) {
        serverIds.push(String(server.serverId));
      }
    }
    const hasMore = resp.listQueryTag?.hasMore ?? servers.length >= pageLimit;
    if (!hasMore) {
      break;
    }
    const lastServer = servers[servers.length - 1];
    if (!lastServer?.createTime) {
      break;
    }
    timestamp = lastServer.createTime;
  }
  return [...new Set(serverIds)];
}

export function createQChatRuntime(
  nim,
  config,
  qchatReplyCache,
  { emitMessage = () => {}, logger = console } = {},
) {
  if (!nim?.qchatMsg || !nim?.qchatServer) {
    logger.warn("[qchat] qchat APIs are unavailable on this SDK instance");
    return null;
  }

  const qchatConfig = config?.qchat ?? {};
  const policy = String(qchatConfig.policy ?? "open").trim() || "open";
  const allowFrom = Array.isArray(qchatConfig.allowFrom) ? qchatConfig.allowFrom : [];
  const isEffectivelyDisabled = policy === "disabled" || (policy === "allowlist" && allowFrom.length === 0);
  if (isEffectivelyDisabled) {
    logger.info(`[qchat] disabled — policy: ${policy}, allowFrom count: ${allowFrom.length}`);
    return null;
  }

  const subscribedServerIds = new Set();
  const logPrefix = "[qchat]";
  const resolveChannelInfo = createQChatChannelInfoResolver(nim);

  const subscribeServer = async (serverId) => {
    if (!serverId || subscribedServerIds.has(serverId)) {
      return;
    }
    const resp = await nim.qchatServer.subscribeAllChannel({ type: 1, serverIds: [serverId] });
    const failed = resp.failServerIds ?? [];
    if (failed.includes(serverId)) {
      logger.warn(`${logPrefix} subscribe failed — server: ${serverId}`);
      return;
    }
    subscribedServerIds.add(serverId);
    logger.info(`${logPrefix} subscribed — server: ${serverId}`);
  };

  const refreshSubscriptions = async () => {
    const serverIds = policy === "allowlist"
      ? deriveQChatServerIds(allowFrom)
      : await discoverJoinedQChatServers(nim);
    if (serverIds.length === 0) {
      logger.info(`${logPrefix} no servers to subscribe`);
      return;
    }
    const resp = await nim.qchatServer.subscribeAllChannel({ type: 1, serverIds });
    const failed = new Set(resp.failServerIds ?? []);
    for (const serverId of serverIds) {
      if (!failed.has(serverId)) {
        subscribedServerIds.add(serverId);
      }
    }
    if (failed.size > 0) {
      logger.warn(`${logPrefix} subscribe failed — servers: ${[...failed].join(", ")}`);
    }
  };

  const messageHandler = (message) => {
    void (async () => {
      qchatReplyCache?.add(message);
      const normalized = normalizeQChatMessage(message, config.credentials.account);
      if (!normalized) {
        return;
      }
      let enriched = normalized;
      try {
        enriched = await enrichQChatMessageWithChannelInfo(normalized, resolveChannelInfo);
      } catch (error) {
        logger.warn(`${logPrefix} message enrich failed — error: ${error instanceof Error ? error.message : String(error)}`);
      }
      emitMessage(enriched);
    })().catch((error) => {
      logger.warn(`${logPrefix} message handling failed — error: ${error instanceof Error ? error.message : String(error)}`);
    });
  };

  const systemNotificationHandler = async (notification) => {
    const normalized = normalizeQChatSystemNotification(notification);
    if (normalized.type === "serverMemberInvite") {
      const serverId = normalized.serverId ?? normalized.server_id ?? normalized.attach?.serverInfo?.serverId;
      const inviterAccid = normalized.fromAccount ?? normalized.from_accid;
      const requestId = normalized.attach?.requestId;
      if (!serverId || !inviterAccid || !requestId) {
        return;
      }
      if (policy === "allowlist" && !new Set(deriveQChatServerIds(allowFrom)).has(serverId)) {
        return;
      }
      try {
        await nim.qchatServer.acceptServerInvite({
          serverId,
          accid: inviterAccid,
          recordInfo: { requestId },
        });
      } catch (error) {
        logger.warn(`${logPrefix} invite accept failed — server: ${serverId}, error: ${error instanceof Error ? error.message : String(error)}`);
      }
      return;
    }

    if (normalized.type === "serverMemberInviteDone") {
      const serverId = normalized.serverId ?? normalized.server_id;
      if (!serverId || subscribedServerIds.has(serverId)) {
        return;
      }
      if (policy === "allowlist" && !new Set(deriveQChatServerIds(allowFrom)).has(serverId)) {
        return;
      }
      try {
        await subscribeServer(serverId);
      } catch (error) {
        logger.warn(`${logPrefix} subscribe after invite failed — server: ${serverId}, error: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
  };

  const passiveListeners = registerQChatPassiveListeners(nim.qchatMsg, {
    onMessage: messageHandler,
    onSystemNotification: systemNotificationHandler,
  });

  return {
    activate: async () => {
      try {
        await refreshSubscriptions();
      } catch (error) {
        logger.warn(`${logPrefix} initial subscription failed — error: ${error instanceof Error ? error.message : String(error)}`);
      }
    },
    stop: async () => {
      try {
        passiveListeners.stop();
      } catch {}
      if (subscribedServerIds.size > 0) {
        try {
          await nim.qchatServer.subscribeAllChannel({ type: 1, serverIds: [] });
        } catch {}
      }
    },
  };
}

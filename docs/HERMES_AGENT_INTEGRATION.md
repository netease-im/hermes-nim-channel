# Hermes Agent 接入指南与功能验证清单

本文档面向 hermes-agent 最新主线接入 `hermes-nim-channel` 插件。核对日期：2026-07-13。

## 版本与接入方式

- hermes-agent `main` 当前 `pyproject.toml` 版本为 `0.18.2`。
- hermes-agent 官方推荐第三方消息通道使用插件方式接入：将插件目录放到 `~/.hermes/plugins/<name>/`，目录内提供 `plugin.yaml` 和 `adapter.py`。
- 当前插件已按该方式组织：根目录包含 `plugin.yaml`、`adapter.py`，内部 Python 包为 `hermes_nim_channel/`，Node bridge 位于 `bridge/`。

## 前置条件

- Python：hermes-agent 当前要求 Python `>=3.11,<3.14`；建议用与 hermes-agent 相同的 Python 环境运行。
- Node.js：需要可执行 `node`，并在插件 `bridge/` 下安装 `@yxim/nim-bot` 等依赖。
- NIM 账号：需要云信 AppKey、机器人账号 accid、token。
- 网络：运行环境需要能连接云信 LBS/link/NOS；私有化部署需要额外配置私有化 endpoint。
- Hermes：已安装并可执行 `hermes` 命令。

## 安装插件

开发态推荐软链，便于继续迭代当前仓库：

```bash
mkdir -p ~/.hermes/plugins
ln -sfn /path/to/hermes-nim-channel \
  ~/.hermes/plugins/hermes-nim-channel
```

生产态推荐拷贝固定版本：

```bash
mkdir -p ~/.hermes/plugins/hermes-nim-channel
rsync -a --delete \
  /path/to/hermes-nim-channel/ \
  ~/.hermes/plugins/hermes-nim-channel/
```

发布后推荐使用 Hermes 官方插件命令安装：

```bash
hermes plugins install netease-im/hermes-nim-channel --enable
hermes gateway restart
```

首次启动 gateway 时，插件会在默认 `node bridge/index.mjs` 模式下自动安装
Node bridge 依赖。受控环境可设置 `NIM_AUTO_INSTALL_BRIDGE=false` 后手动安装：

```bash
cd ~/.hermes/plugins/hermes-nim-channel
npm install --omit=dev --prefix bridge
```

本地自检：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node --test bridge/test/*.test.mjs
```

## 基础配置

最小配置只需要凭证：

```bash
export NIM_CREDENTIALS='<app-key>|<bot-accid>|<token>'
```

也可拆分配置：

```bash
export NIM_APP_KEY='<app-key>'
export NIM_ACCOUNT='<bot-accid>'
export NIM_TOKEN='<token>'
```

多实例可配置 `NIM_INSTANCES` JSON 数组，最多 3 个实例。每个实例派生
`accountId=<app-key>:<accid>`，并独立维护登录连接、策略和 bridge 进程。

建议显式配置消息准入策略：

```bash
# P2P：open / allowlist / disabled
export NIM_P2P_POLICY='allowlist'
export NIM_P2P_ALLOW_FROM='alice,bob'

# 群：open / allowlist / disabled；默认 allowlist
export NIM_GROUP_POLICY='allowlist'
export NIM_GROUP_ALLOWLIST='123456,789012'

# QChat：open / allowlist / disabled
export NIM_QCHAT_POLICY='allowlist'
export NIM_QCHAT_ALLOW_FROM='serverId|channelId,serverId2|channelId2|alice'
```

可选运行参数：

```bash
export NIM_HOME_CHANNEL='user:alice'
export NIM_TEXT_CHUNK_LIMIT='4000'
export NIM_INBOUND_DEBOUNCE_MS='0'
export NIM_QUICK_COMMENT_ENABLED='false'
export NIM_LEGACY_LOGIN='false'
export NIM_ANTISPAM_ENABLED='true'
```

私有化部署示例：

```bash
export NIM_WEBLBS_URL='https://lbs.example.com'
export NIM_LINK_WEB='wss://link.example.com'
export NIM_NOS_UPLOADER='https://upload.example.com'
export NIM_NOS_DOWNLOADER_V2='https://download.example.com/{object}'
export NIM_NOS_SSL='true'
export NIM_NOS_ACCELERATE='https://cdn.example.com/{object}'
export NIM_NOS_ACCELERATE_HOST='cdn.example.com'
```

如果 bridge 入口需要自定义：

```bash
export NIM_BRIDGE_COMMAND='node /absolute/path/to/hermes-nim-channel/bridge/index.mjs'
```

## 启动 Hermes Gateway

在 Hermes 环境中确认插件被发现后启动 gateway：

```bash
hermes gateway
```

如果 Hermes 当前版本提供插件检查命令，可先执行：

```bash
hermes plugins
hermes doctor
```

预期行为：

- Hermes 加载 `hermes-nim-channel` 插件。
- 插件注册平台名 `nim`，显示名称 `NIM`。
- Node bridge 启动并完成 NIM SDK 登录。
- 收到连接状态事件后 adapter 标记为 connected。

## Chat ID 约定

- P2P：`user:<accid>`，例如 `user:alice`。
- 群：`team:<teamId>`，例如 `team:123456`。
- QChat：`qchat:<serverId>:<channelId>`，例如 `qchat:server-a:channel-b`。
- 多实例：`acct:<url-encoded-account-id>:` + 上述目标，例如 `acct:app%3Abot-a:user:alice`。

## 功能验证清单

### 1. 基础健康检查

- [ ] `python3 -m unittest discover -s tests -p 'test_*.py'` 通过。
- [ ] `node --test bridge/test/*.test.mjs` 通过。
- [ ] 首次 `hermes gateway` 启动能自动安装 bridge 依赖，或手动 `npm install --omit=dev --prefix bridge` 无失败。
- [ ] `hermes gateway` 启动后无 `bridge credentials are incomplete`。
- [ ] NIM bot 登录成功，断开时 gateway 能正常退出。
- [ ] 故意配置错误 token 后，进程不会残留不可恢复的 bridge 子进程。

### 2. P2P 收发

- [ ] `NIM_P2P_POLICY=open` 时，任意用户私聊 bot 可触发 Hermes 回复。
- [ ] `NIM_P2P_POLICY=allowlist` 时，只允许 `NIM_P2P_ALLOW_FROM` 内账号触发。
- [ ] `NIM_P2P_POLICY=disabled` 时，私聊消息被忽略。
- [ ] bot 可主动发送文本到 `user:<accid>`。
- [ ] 超长文本会按 `NIM_TEXT_CHUNK_LIMIT` 分片发送。
- [ ] 带 `reply_to` 的文本回复能命中缓存消息并发送回复。

### 3. 群消息

- [ ] `NIM_GROUP_POLICY=allowlist` 时，只处理 `NIM_GROUP_ALLOWLIST` 内群。
- [ ] 群内 @bot 或 force push bot 时才触发 Hermes。
- [ ] 非 @bot 的普通群消息不会触发。
- [ ] 入站事件包含 `conversation_name`，能解析群名时显示群名。
- [ ] 收到群消息后 bridge 尝试发送群已读回执，失败不影响消息处理。

### 4. QChat

- [ ] `qchat:<serverId>:<channelId>` 目标格式可发送文本。
- [ ] `NIM_QCHAT_POLICY=disabled` 时 QChat 入站和出站被阻断。
- [ ] `NIM_QCHAT_POLICY=allowlist` 时，仅匹配 `server|channel|account` 规则的消息触发。
- [ ] QChat 入站需要 mention bot 或 mention all 才触发。
- [ ] 入站事件包含 `server_id`、`channel_id`、`channel_topic`、`channel_info`。
- [ ] QChat 频道名解析失败时，不影响消息正常进入。
- [ ] QChat 媒体发送当前返回 `qchat media is not supported`，符合预期限制。

### 5. 媒体能力

- [ ] 图片发送：`send_image_file("user:alice", "/tmp/a.png")` 可发送。
- [ ] 文件发送：`send_document("team:123", "/tmp/report.pdf")` 可发送。
- [ ] 语音发送：`send_voice(..., "/tmp/a.aac")` 可发送，运行环境需有 `ffprobe`。
- [ ] 视频发送：`send_video(..., "/tmp/a.mp4")` 可发送，运行环境需有 `ffprobe`。
- [ ] 图片/文件/语音/视频入站后，Hermes event 填充 `media_urls` 和 `media_types`。
- [ ] 入站媒体下载失败时，文本事件仍能进入，不应导致消息丢弃。
- [ ] 语音入站在 SDK 支持 `voiceToText` 且转写成功时，`text` 使用转写结果。

### 6. 话题、回复与编辑/流式

- [ ] 普通文本 `reply_to` 能走 NIM 回复消息。
- [ ] topic 消息的文本回复能走 topic reply。
- [ ] topic 消息的媒体回复能走 topic media reply。
- [ ] 入站 topic 消息保留 `topic_refer`、`topic_info`、`topic_name`。
- [ ] `metadata={"stream": {...}}` 会调用 `send_stream_message` bridge 方法。
- [ ] SDK 不支持 stream API 时，bridge fallback 为普通文本发送。
- [ ] `metadata={"edit_message_id": "..."}` 会发送替代文本，并返回 `edited_message_id`。

### 7. 运营与可靠性

- [ ] `NIM_INBOUND_DEBOUNCE_MS>0` 时，同会话短时间多条消息带有一致 `batch_id` 和递增 `batch_index`。
- [ ] `NIM_QUICK_COMMENT_ENABLED=true` 时，收到消息后添加 processing quick comment，并在 TTL 后清理。
- [ ] gateway 退出时，未到期 quick comment cleanup 会被主动执行。
- [ ] NIM kickout/logout/disconnected 事件会更新 adapter connected 状态。
- [ ] friend auto-accept 只接受符合 P2P 策略的申请。
- [ ] bridge stderr 日志不打印 token、消息全文等敏感信息。

## 常见问题排查

### Hermes 未发现插件

- 确认目录为 `~/.hermes/plugins/hermes-nim-channel/plugin.yaml`。
- 确认同级存在 `adapter.py`。
- 确认 `plugin.yaml` 的 `kind: platform`。
- 如果使用软链，确认 Hermes 运行用户有读取权限。

### 登录失败

- 检查 `NIM_CREDENTIALS` 是否为 `appKey|accid|token`，不是 `appKey-account-token` 时优先使用竖线。
- 确认 accid 是 bot 账号且 token 未过期。
- 如使用私有化，检查 `NIM_WEBLBS_URL` 和 `NIM_LINK_WEB`。

### 能收到消息但不回复

- P2P 检查 `NIM_P2P_POLICY` 和 `NIM_P2P_ALLOW_FROM`。
- 群检查 `NIM_GROUP_POLICY`、`NIM_GROUP_ALLOWLIST` 和是否 @bot。
- QChat 检查 `NIM_QCHAT_POLICY`、`NIM_QCHAT_ALLOW_FROM` 和 mention。

### 媒体发送失败

- 确认本地文件路径可读。
- 语音/视频需要 `ffprobe` 可执行。
- QChat 媒体当前未支持，应改用普通 P2P/team 或降级文本。

## 发布前验收标准

- [ ] 插件以软链或拷贝方式安装到目标 Hermes 环境。
- [ ] 所有必填环境变量已写入目标运行环境。
- [ ] Python 与 Node 单测全部通过。
- [ ] P2P、群、QChat 三类通道至少各完成一次真实入站验证。
- [ ] 文本、回复、媒体、长文本分片至少各完成一次真实出站验证。
- [ ] 断网/错误 token/退出 gateway 三类异常路径不残留 bridge 进程。
- [ ] 回滚方案明确：移除 `~/.hermes/plugins/hermes-nim-channel` 并重启 `hermes gateway`。

## 参考来源

- hermes-agent `pyproject.toml` `0.18.2`：https://github.com/NousResearch/hermes-agent/blob/main/pyproject.toml
- Hermes 官方 Platform Adapter 文档：https://hermes-agent.nousresearch.com/docs/developer-guide/adding-platform-adapters
- Hermes 官方插件指南：https://github.com/NousResearch/hermes-agent/blob/main/website/docs/guides/build-a-hermes-plugin.md

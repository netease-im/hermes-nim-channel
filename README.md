# Hermes NIM Channel

`hermes-nim-channel` 是 Hermes Agent 的网易云信 IM（NIM）平台插件。它通过 Python 适配 Hermes 插件接口，通过 Node.js bridge 调用 `@yxim/nim-bot`，让 `hermes-agent` 可以经由 NIM SDK 收发消息。

适配的 Hermes Agent 项目：`https://github.com/NousResearch/hermes-agent`

## 功能能力

- 支持 P2P、群、超大群、QChat 的消息收发路由。
- 支持最多 3 个 NIM 账号实例，每个实例独立登录、独立策略、独立 bridge 进程。
- 默认使用 NIM Bot SDK `aiBot: 2` 登录，支持可选 legacy 登录。
- 支持 P2P、群、QChat 访问策略：`open`、`allowlist`、`disabled`。
- 群和 QChat 消息按 @/强推触发后才进入 Hermes。
- 群 @ 消息会移除开头的 `@xxx` 前缀，避免把 @ 文本当成用户内容。
- 只处理在线消息：跳过漫游、离线、历史、同步消息，避免 gateway 重启后重复回复旧消息。
- 对在线 P2P 和群消息发送已读回执，具体是否成功取决于服务端和 SDK 权限。
- 支持文本、长文本分片、有状态流式消息、编辑替换、回复消息发送。
- 当 NIM Topic 元数据可用时，按 Topic 隔离 Hermes 会话，并支持文本、媒体和分块流式延迟路由。
- 支持 P2P/群图片、文件、音频、视频出站发送。
- 支持入站媒体下载；SDK 支持时可做音频转文本。
- 支持用户、群、QChat 名称解析；Topic 名称进入会话标题，QChat 频道名称和主题进入 Agent 上下文。
- QChat 入站消息支持原生引用回复；QChat 媒体出站降级为包含 caption 和路径/URL 的单条文本。
- 支持按 P2P 策略自动通过好友申请。
- 支持私有化 LBS/link/NOS 配置。
- 支持可选入站消息批处理元数据和临时快捷评论处理标记。

## 已知限制

- 入站引用消息展示依赖 NIM SDK 是否提供 `threadReply` 或等价回复元数据。当前实测普通客户端引用回复消息未携带 `threadReply/reply/quote/refer` 字段，因此 Hermes WebUI 无法展示被引用源消息。
- QChat 暂不创建原生图片、文件、音频或视频消息，而是发送包含 caption 和路径/URL 的文本回退消息。
- 群已读回执可能因服务端或应用权限返回 `forbidden`，插件会记录日志但不阻断消息处理。

## 安装

发布版推荐使用 Hermes 官方插件命令安装：

```bash
hermes plugins install netease-im/hermes-nim-channel --enable
hermes gateway restart
```

首次启动 gateway 时，如果使用默认 `node bridge/index.mjs` 命令，插件会自动安装 Node bridge 依赖。受控或离线环境可关闭自动安装：

```bash
export NIM_AUTO_INSTALL_BRIDGE='false'
```

关闭自动安装或自动安装失败时，可手动安装 bridge 依赖：

```bash
npm install --omit=dev --prefix ~/.hermes/plugins/hermes-nim-channel/bridge
```

本地开发可使用软链安装：

```bash
mkdir -p ~/.hermes/plugins
ln -sfn /path/to/hermes-nim-channel ~/.hermes/plugins/hermes-nim-channel
hermes plugins enable hermes-nim-channel
hermes gateway restart
```

## 配置

可以使用合并凭据：

```bash
export NIM_CREDENTIALS='<app-key>|<accid>|<token>'
```

也可以拆分配置：

```bash
export NIM_APP_KEY='<app-key>'
export NIM_ACCOUNT='<bot-accid>'
export NIM_TOKEN='<token>'
```

多实例可使用 `NIM_INSTANCES` 配置 JSON 数组，最多 3 个实例。每个实例会派生 `accountId=<app-key>:<accid>`，并独立维护连接和访问策略。

```bash
export NIM_INSTANCES='[
  {
    "enabled": true,
    "nimToken": "<app-key>|<bot-accid-1>|<token-1>",
    "p2p": { "policy": "allowlist", "allowFrom": ["<accid-1>"] },
    "team": { "policy": "open" },
    "qchat": { "policy": "disabled" }
  },
  {
    "enabled": true,
    "nimToken": "<app-key>|<bot-accid-2>|<token-2>",
    "p2p": { "policy": "open" },
    "team": { "policy": "allowlist", "allowFrom": ["<team-id>"] },
    "qchat": { "policy": "allowlist", "allowFrom": ["<server-id>|<channel-id>"] }
  }
]'
```

多实例出站时需要指定实例。入站消息会自动带上实例前缀，直接在 WebUI 中回复即可；手动发送时使用：

```text
acct:<url-encoded-account-id>:user:<accid>
acct:<url-encoded-account-id>:user:<accid>:topic:<topicId>
acct:<url-encoded-account-id>:team:<teamId>
acct:<url-encoded-account-id>:qchat:<serverId>:<channelId>
```

例如 `accountId` 为 `app:bot-a` 时，目标写作 `acct:app%3Abot-a:user:<accid>`。

访问策略默认是 `open`，如需限制可显式配置：

```bash
# P2P: open / allowlist / disabled
export NIM_P2P_POLICY='allowlist'
export NIM_P2P_ALLOW_FROM='<accid-1>,<accid-2>'

# 群/超大群: open / allowlist / disabled
export NIM_GROUP_POLICY='open'
export NIM_GROUP_ALLOWLIST='<team-id-1>,<team-id-2>'

# QChat: open / allowlist / disabled
export NIM_QCHAT_POLICY='allowlist'
export NIM_QCHAT_ALLOW_FROM='<server-id>|<channel-id>,<server-id-2>|<channel-id-2>|<accid>'
```

常用运行配置：

```bash
export NIM_HOME_CHANNEL='team:<team-id>'
export NIM_TEXT_CHUNK_LIMIT='4000'
export NIM_INBOUND_DEBOUNCE_MS='0'
export NIM_QUICK_COMMENT_ENABLED='false'
export NIM_QUICK_COMMENT_INDEX='71'
export NIM_QUICK_COMMENT_TTL_MS='30000'
export NIM_LEGACY_LOGIN='false'
export NIM_ANTISPAM_ENABLED='true'
```

私有化环境配置：

```bash
export NIM_WEBLBS_URL='https://lbs.example.com'
export NIM_LINK_WEB='wss://link.example.com'
export NIM_NOS_UPLOADER='https://upload.example.com'
export NIM_NOS_DOWNLOADER_V2='https://download.example.com/{object}'
export NIM_NOS_SSL='true'
export NIM_NOS_ACCELERATE='https://cdn.example.com/{object}'
export NIM_NOS_ACCELERATE_HOST='cdn.example.com'
```

需要覆盖 bridge 命令时：

```bash
export NIM_BRIDGE_COMMAND='node /absolute/path/to/hermes-nim-channel/bridge/index.mjs'
export NIM_AUTO_INSTALL_BRIDGE='false'
```

## Chat ID 格式

- P2P：`user:<accid>`。
- P2P Topic：`user:<accid>:topic:<topicId>`。
- 群/超大群：`team:<teamId>`。
- QChat：`qchat:<serverId>:<channelId>`。
- 多实例：在上述目标前增加 `acct:<url-encoded-account-id>:` 前缀。

## 运行行为

- 只有在线消息（`messageSource === 1`）会进入 Hermes；漫游、离线、历史、同步消息会被跳过。
- 群/超大群消息需要 @ 或强推机器人后才会进入 Hermes。
- QChat 消息需要 @ 或 @所有人后才会进入 Hermes。
- QChat 被动监听在登录前注册，登录成功后再发现圈组并订阅频道，避免登录切换窗口丢消息。
- QChat 引用回复命中 bridge 原始消息缓存时使用原生 `replyMessage`；缓存未命中时普通发送并返回 fallback 元数据。
- QChat 入站文本前会注入一次频道名称/主题上下文；媒体出站合并为一条文本消息。
- 群消息开头的 @ 文本会在进入 Hermes 前剥离。
- 原始 NIM payload 会保留在事件 metadata 中，便于排障和高级处理。
- `reply_to` 出站消息会在 bridge 缓存或 message refer 可找到原消息时使用 NIM 回复接口。
- P2P Topic 按 NIM 账号、对端账号和 Topic ID 隔离会话及入站批次；Topic 上下文在 bridge 中保留 30 分钟，支持不携带 `reply_to` 的延迟发送。
- 流式发送可在 metadata 的 `stream.stream_id` 中提供稳定 ID；普通 P2P/群中，相同账号、目标、回复目标和 stream ID 的分片复用同一个 SDK base message。未提供时插件按目标上下文派生兼容 ID。
- 网关连接后会创建权限为 `0600` 的 `~/.hermes/nim-channel.sock`，供 `hermes send --to nim:...` 和独立 cron 复用当前 NIM 登录；网关未运行时会明确失败，不会启动第二个 NIM 客户端。
- NIM SDK 没有 Topic 原生流接口，因此 Topic 流式内容按参考实现逐块调用 `replyTopicMessage`，保证每个分块仍位于原 Topic，而不会误发为 Thread 流消息。

## 验证

Python 测试：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Node 测试：

```bash
node --test bridge/test/*.test.mjs
```

当前基线：

- Python：55 个测试通过。
- Node：74 个测试通过。

运行态排查命令：

```bash
hermes gateway status
tail -n 120 ~/.hermes/logs/gateway.log
tail -n 120 ~/.hermes/logs/gateway.error.log
ps -ef | rg 'gateway run|bridge/index.mjs' | rg -v rg
```

## 功能验证清单

- [ ] NIM 登录成功，bridge 进程保持存活。
- [ ] P2P 在线消息只触发一次 Hermes 回复。
- [ ] gateway 重启后不会重复处理旧 P2P/群消息。
- [ ] 群 @ 消息能触发 Hermes，并移除开头 @ 文本。
- [ ] 群非 @ 消息会被忽略。
- [ ] 在线群消息会尝试发送已读回执。
- [ ] P2P 文本回复在目标消息已缓存时使用 NIM 回复接口。
- [ ] 长文本按 `NIM_TEXT_CHUNK_LIMIT` 分片发送。
- [ ] 入站媒体会生成 `media_urls` 和 `media_types`。
- [ ] P2P/群出站图片、文件、音频、视频可用。
- [ ] QChat 文本收发符合配置策略。
- [ ] QChat 引用回复命中时使用原生回复，媒体发送可收到 caption + 路径/URL 文本。
- [ ] 同一 P2P 用户的不同 Topic 进入不同 Hermes 会话，延迟回复仍回到原 Topic。
- [ ] 同一 `stream_id` 的多个分片在完成前复用一条 SDK 流消息。
- [ ] 多实例配置下，不同账号各自登录，入站会话带 `acct:<url-encoded-account-id>:` 前缀，出站回复回到正确账号。
- [ ] WebUI 会话标题符合 `云信·单聊·<昵称>` 和 `云信·群聊·<群名>`。

## 目录结构

```text
plugin.yaml
adapter.py
__init__.py
hermes_nim_channel/
  config.py
  inbound_media.py
  qchat.py
  session_titles.py
  targets.py
  platforms/
    base.py
    nim.py
    nim_bridge.py
    nim_protocol.py
bridge/
  index.mjs
  package.json
  src/
    config.mjs
    qchat.mjs
    qchat-runtime.mjs
  test/
docs/
openspec/
tests/
```

## SDD 工作流

本项目使用全局 `openspec` CLI 做规格驱动开发。

- 项目配置：`openspec/config.yaml`
- 工作流脚本：`./scripts/sdd`
- 使用说明：`docs/SDD_WORKFLOW.md`

常用流程：

```bash
./scripts/sdd new <change-name>
./scripts/sdd instructions proposal <change-name>
./scripts/sdd instructions specs <change-name>
./scripts/sdd instructions design <change-name>
./scripts/sdd instructions tasks <change-name>
./scripts/sdd validate <change-name>
```

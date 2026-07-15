# Hermes NIM Channel

`hermes-nim-channel` 是 Hermes Agent 的网易云信 IM（NIM）平台插件。它通过 Python 适配 Hermes 插件接口，通过 Node.js bridge 调用 `@yxim/nim-bot`，让 `hermes-agent` 可以经由 NIM SDK 收发消息。

本项目的 NIM 行为基线对齐 `openclaw-nim-channel`：

- Hermes Agent: `https://github.com/NousResearch/hermes-agent`
- OpenClaw: `https://github.com/openclaw/openclaw`
- 参考实现：`openclaw-nim-channel`

## 功能能力

- 支持 P2P、群、超大群、QChat 的消息收发路由。
- 默认使用 NIM Bot SDK `aiBot: 2` 登录，支持可选 legacy 登录。
- 支持 P2P、群、QChat 访问策略：`open`、`allowlist`、`disabled`。
- 群和 QChat 消息按 @/强推触发后才进入 Hermes。
- 群 @ 消息会移除开头的 `@xxx` 前缀，避免把 @ 文本当成用户内容。
- 只处理在线消息：跳过漫游、离线、历史、同步消息，避免 gateway 重启后重复回复旧消息。
- 对在线 P2P 和群消息发送已读回执，具体是否成功取决于服务端和 SDK 权限。
- 支持文本、长文本分片、流式回退、编辑替换、回复消息发送。
- 当 NIM topic 元数据可用时，支持 topic 文本/媒体回复。
- 支持 P2P/群图片、文件、音频、视频出站发送。
- 支持入站媒体下载；SDK 支持时可做音频转文本。
- 支持用户、群、QChat 名称解析，用于 Hermes WebUI 会话标题。
- 支持按 P2P 策略自动通过好友申请。
- 支持私有化 LBS/link/NOS 配置。
- 支持可选入站消息批处理元数据和临时快捷评论处理标记。

## 已知限制

- 入站引用消息展示依赖 NIM SDK 是否提供 `threadReply` 或等价回复元数据。当前实测普通客户端引用回复消息未携带 `threadReply/reply/quote/refer` 字段，因此 Hermes WebUI 无法展示被引用源消息。
- QChat 媒体出站暂不支持，会返回明确的 unsupported 结果。
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
- 群/超大群：`team:<teamId>`。
- QChat：`qchat:<serverId>:<channelId>`。

## 运行行为

- 只有在线消息（`messageSource === 1`）会进入 Hermes；漫游、离线、历史、同步消息会被跳过。
- 群/超大群消息需要 @ 或强推机器人后才会进入 Hermes。
- QChat 消息需要 @ 或 @所有人后才会进入 Hermes。
- 群消息开头的 @ 文本会在进入 Hermes 前剥离。
- 原始 NIM payload 会保留在事件 metadata 中，便于排障和高级处理。
- `reply_to` 出站消息会在 bridge 缓存或 message refer 可找到原消息时使用 NIM 回复接口。

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

- Python：44 个测试通过。
- Node：59 个测试通过。

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
  platforms/
    base.py
    nim.py
    nim_bridge.py
    nim_protocol.py
bridge/
  index.mjs
  package.json
  src/
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

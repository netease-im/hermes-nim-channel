# Hermes NIM Channel

`hermes-nim-channel` is a Hermes Agent platform plugin for NetEase Yunxin IM (NIM, 网易云信). It lets `hermes-agent` receive and send messages through the NIM Bot SDK via a Python Hermes adapter and a Node.js bridge backed by `@yxim/nim-bot`.

The NIM behavior baseline is `openclaw-nim-channel`:

- Hermes host: `https://github.com/NousResearch/hermes-agent`
- Reference project: `https://github.com/openclaw/openclaw`
- Local reference implementation: `/Users/xumengxiang/Documents/00.NetEase/05.IM/openclaw-nim-channel`

## Current Capabilities

- P2P, team, superTeam, and QChat inbound/outbound routing.
- NIM Bot SDK login with `aiBot: 2` by default, plus optional legacy login.
- P2P/team/QChat sender policies: `open`, `allowlist`, `disabled`.
- Team and QChat mention-gated inbound processing.
- Team mention prefix cleanup: leading `@xxx` tokens are removed before text reaches Hermes.
- Online-only inbound dispatch: roaming/offline/history/sync messages are skipped, so gateway restart does not reprocess old messages.
- P2P and team read receipts for online messages where the SDK/server allows it.
- Text, long-text chunking, stream fallback, edit-as-replacement, and reply sends.
- Topic text/media reply support when NIM topic metadata is available.
- Image, file, audio, and video outbound media.
- Inbound media download and audio-to-text when SDK support is available.
- Team/user/QChat name resolution for Hermes session display names.
- Friend auto-accept governed by P2P policy.
- Private deployment endpoint options for LBS/link/NOS.
- Optional inbound batching metadata and temporary quick-comment processing marker.

## Known Limits

- Inbound quoted/referenced-message display depends on the SDK exposing `threadReply` or equivalent reply metadata. Current live Bot SDK messages observed in this project do not include `threadReply/reply/quote/refer` fields for normal client quote replies, so Hermes WebUI cannot show the referenced source for those messages.
- QChat media outbound is intentionally unsupported and returns an explicit unsupported result.
- Team read receipt calls may return `forbidden` depending on server/app permissions; this is logged and does not block message handling.

## Layout

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

## Install

Published plugin install:

```bash
hermes plugins install netease-im/hermes-nim-channel --enable
hermes gateway restart
```

The plugin auto-installs Node bridge dependencies on first gateway start when
the default `node bridge/index.mjs` command is used. Set
`NIM_AUTO_INSTALL_BRIDGE=false` to disable this behavior in locked-down
environments.

Development install, using a symlink:

```bash
mkdir -p ~/.hermes/plugins
ln -sfn /Users/xumengxiang/Documents/00.NetEase/05.IM/hermes-nim-channel \
  ~/.hermes/plugins/hermes-nim-channel
```

Manual bridge dependency install, only needed when auto-install is disabled or
failed:

```bash
npm install --omit=dev --prefix ~/.hermes/plugins/hermes-nim-channel/bridge
```

Restart Hermes after changing plugin code or config:

```bash
hermes gateway restart
```

## Configuration

Credentials can be provided as a single token:

```bash
export NIM_CREDENTIALS='appKey|accid|token'
```

Or as separate values:

```bash
export NIM_APP_KEY='appKey'
export NIM_ACCOUNT='botAccid'
export NIM_TOKEN='token'
```

Access policy defaults are `open` unless explicitly configured.

```bash
# P2P: open / allowlist / disabled
export NIM_P2P_POLICY='allowlist'
export NIM_P2P_ALLOW_FROM='alice,bob'

# Team/superTeam: open / allowlist / disabled
export NIM_GROUP_POLICY='open'
export NIM_GROUP_ALLOWLIST='123456,789012'

# QChat: open / allowlist / disabled
export NIM_QCHAT_POLICY='allowlist'
export NIM_QCHAT_ALLOW_FROM='serverId|channelId,serverId2|channelId2|alice'
```

Common runtime options:

```bash
export NIM_HOME_CHANNEL='team:123456'
export NIM_TEXT_CHUNK_LIMIT='4000'
export NIM_INBOUND_DEBOUNCE_MS='0'
export NIM_QUICK_COMMENT_ENABLED='false'
export NIM_QUICK_COMMENT_INDEX='71'
export NIM_QUICK_COMMENT_TTL_MS='30000'
export NIM_LEGACY_LOGIN='false'
export NIM_ANTISPAM_ENABLED='true'
```

Private deployment options:

```bash
export NIM_WEBLBS_URL='https://lbs.example.com'
export NIM_LINK_WEB='wss://link.example.com'
export NIM_NOS_UPLOADER='https://upload.example.com'
export NIM_NOS_DOWNLOADER_V2='https://download.example.com/{object}'
export NIM_NOS_SSL='true'
export NIM_NOS_ACCELERATE='https://cdn.example.com/{object}'
export NIM_NOS_ACCELERATE_HOST='cdn.example.com'
```

Override bridge command when needed:

```bash
export NIM_BRIDGE_COMMAND='node /absolute/path/to/hermes-nim-channel/bridge/index.mjs'
export NIM_AUTO_INSTALL_BRIDGE='false'
```

## Chat ID Format

- P2P: `user:<accid>`, for example `user:alice`.
- Team/superTeam: `team:<teamId>`, for example `team:123456`.
- QChat: `qchat:<serverId>:<channelId>`, for example `qchat:server-a:channel-b`.

## Runtime Behavior

- Only online messages (`messageSource === 1`) are dispatched to Hermes. Non-online sync, roaming, offline, and history messages are skipped.
- Team/superTeam messages require mention/force-push to the bot before dispatch.
- QChat messages require mention or mention-all before dispatch.
- Leading group mention text is stripped before Hermes sees the message content.
- Raw NIM payload is still kept in the event metadata for debugging and advanced handling.
- `reply_to` sends use NIM reply APIs when the original message can be found in the bridge cache or by message refer.

## Verification

Python tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Node tests:

```bash
node --test bridge/test/*.test.mjs
```

Expected current baseline:

- Python: 44 tests passing.
- Node: 59 tests passing.

Useful runtime checks:

```bash
hermes gateway status
tail -n 120 ~/.hermes/logs/gateway.log
tail -n 120 ~/.hermes/logs/gateway.error.log
ps -ef | rg 'gateway run|bridge/index.mjs' | rg -v rg
```

## Feature Checklist

- [ ] NIM login succeeds and bridge process stays alive.
- [ ] P2P online message triggers exactly one Hermes response.
- [ ] Gateway restart does not replay old P2P/team messages.
- [ ] Team @ message triggers Hermes and strips the leading @ mention text.
- [ ] Team non-@ message is ignored.
- [ ] Team read receipt is attempted for online team messages.
- [ ] P2P text reply uses NIM reply when reply target is cached.
- [ ] Long text is chunked according to `NIM_TEXT_CHUNK_LIMIT`.
- [ ] Inbound media creates `media_urls` and `media_types`.
- [ ] Outbound image/file/audio/video works in P2P/team.
- [ ] QChat text send/receive works with configured policy.
- [ ] WebUI session names follow `云信·单聊·<昵称>` and `云信·群聊·<群名>`.

## SDD Workflow

This repository uses the global `openspec` CLI for spec-driven development.

- Project schema config: `openspec/config.yaml`
- Workflow wrapper: `./scripts/sdd`
- Usage guide: `docs/SDD_WORKFLOW.md`

Typical flow:

```bash
./scripts/sdd new <change-name>
./scripts/sdd instructions proposal <change-name>
./scripts/sdd instructions specs <change-name>
./scripts/sdd instructions design <change-name>
./scripts/sdd instructions tasks <change-name>
./scripts/sdd validate <change-name>
```

# 让手机收到访客推送（明天 demo 用）

访客与 AI 完成问答后，系统把访客信息**推到保安手机**。本仓库通知渠道可插拔（`NOTIFY_CHANNEL`），
本文给"明天最快能在手机上收到消息"的设置。

## 渠道路线图（已定）
1. **同步推进（当前）→ Telegram + 企业微信群机器人**：两者都只需手机号、不要公司/营业执照、当天可通。两边可**同时推**。
2. **备用 → Discord**：webhook，已具备。
3. **未来 / 国内生产落地 → 企业微信自建应用 / 微信生态**：原生按钮回调、合规、国内可用（升级路径见 `WECHAT_PLAN.md`）。

> 通知是可插拔适配器（`notify/dispatch.py`）。`NOTIFY_CHANNEL` **支持多渠道（逗号分隔）**，
> 例如 `NOTIFY_CHANNEL=telegram,wecom` 会**同时推到 Telegram 和企业微信**。换渠道不动主流程。

> ⚠️ 消息里那个「✅ 确认放行」按钮/链接要能点开生效，需要后端**公网可达**（`PUBLIC_BASE_URL` 指向公网）。
> 本地 demo：用 cloudflared/ngrok 隧道映射 8080，把得到的 https 填进 `PUBLIC_BASE_URL`；或直接在电脑后台 Dashboard 点放行。
> 仅"收到消息"不需要公网——Telegram/企微会把消息推到你手机；只有"点按钮放行"那一步需要链接可达。

---

## 方案 1（推荐，明天用）：Telegram —— 5 分钟，手机即时收到 + 放行按钮

### 你做的
1. 手机/电脑打开 Telegram，搜 **@BotFather** → 发 `/newbot` → 起名字 → 拿到 **bot token**（形如 `12345:ABC...`）。
2. 在 Telegram 里搜你刚建的 bot，给它发一句话（如 "hi"）——**必须先发一条，否则取不到 chat id**。
3. 浏览器打开（把 <token> 换成你的）：`https://api.telegram.org/bot<token>/getUpdates`
   → 在返回 JSON 里找 `"chat":{"id": 数字}` → 这个数字就是 **chat id**。

### 填 .env
```
NOTIFY_CHANNEL=telegram
TELEGRAM_BOT_TOKEN=<你的 token>
TELEGRAM_CHAT_ID=<你的 chat id>
PUBLIC_BASE_URL=<公网 https（要点放行按钮才需要）>
```

### 验证（不用打电话也能测）
```
# 文本仿真会真的把卡片推到你的 Telegram
PYTHONPATH=src python -m visitor_agent.sim.run_text --scenario scenarios/songhuo.json --live
```
手机 Telegram 应收到一张访客卡片 + 「✅ 确认放行」按钮；点按钮（需 PUBLIC_BASE_URL 公网可达）→ 后端抬杆、后台变已放行。

---

## 方案 2（生产）：企业微信群机器人 —— 当天可通

### 你做的
1. 企业微信建一个群（保安们在里面）→ 群设置 → 群机器人 → 添加 → **复制 Webhook URL**。

### 填 .env
```
NOTIFY_CHANNEL=wecom
WECOM_WEBHOOK_URL=<刚复制的 URL>
PUBLIC_BASE_URL=<公网 https>
```
验证同上（`sim ... --live`）。群里收到 markdown 卡片 + 「确认放行」链接。
> 群机器人是单向推送，放行用**链接**（点开网页确认）。要"微信里原生按钮 + 回复"需企微自建应用，见 `WECHAT_PLAN.md` 方案 B（2~3 天）。

---

## 方案 3：Discord —— 也很快（如果你常用 Discord）
```
NOTIFY_CHANNEL=discord
DISCORD_WEBHOOK_URL=<频道→整合→Webhooks→New→Copy URL>
```

---

## 同时推两边（Telegram + 企业微信，同步推进）
配齐两边的密钥后，把渠道写成逗号分隔即可**一条登记同时推到 Telegram 和企微群**：
```
NOTIFY_CHANNEL=telegram,wecom
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
WECOM_WEBHOOK_URL=...
```

## 都不配：后台点放行（默认，零账号）
`NOTIFY_CHANNEL=none` → 保安在电脑 `/dashboard` 看到访客记录、点「放行」。手机收不到主动推送，但无需任何账号。

---

## 交给本地 Claude Code 的设置 Prompt（配好并自测，不用打电话）
```
帮我把保安通知配好并自测，让我手机能收到访客卡片。我想同步推进 Telegram 和企业微信。
1. Telegram：我已用 @BotFather 建 bot；问我要 TELEGRAM_BOT_TOKEN；并告诉我怎么取 chat id
   （让我先给 bot 发一句话，然后你帮我请求 https://api.telegram.org/bot<token>/getUpdates 解析出 chat id）。
2. 企业微信（可选，我若已建群机器人就配）：问我要 WECOM_WEBHOOK_URL。
3. 写 .env：NOTIFY_CHANNEL=telegram,wecom（只配了一个就只写那一个）；填上对应密钥；
   PUBLIC_BASE_URL 暂填 http://localhost:8080（要在手机点放行链接时再换公网隧道）。
4. 自测（不用打电话）：PYTHONPATH=src python -m visitor_agent.sim.run_text --scenario scenarios/songhuo.json --live
   确认我手机的 Telegram（和/或企微群）收到了访客卡片。把结果告诉我。
报错先自查修复；最后告诉我两边各收到没有。
```

## 明天 demo 建议
- **最快**：先把 **Telegram** 配好（手机即时收到）；**企业微信**有空用手机号建一个群机器人，`NOTIFY_CHANNEL=telegram,wecom` 两边一起推。
- **要在手机上点放行**：加一个 cloudflared 隧道把 8080 暴露、`PUBLIC_BASE_URL` 填隧道地址。
- **不想折腾链接可达**：消息照收，放行在电脑后台 Dashboard 点——一样完成闭环。

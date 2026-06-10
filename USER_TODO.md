# 🙋 需要你亲手做的事（只有这些）+ 手把手教程

整个 demo **只需要你提供两个 API key**：`ANTHROPIC_API_KEY` 和 `OPENAI_API_KEY`。
（这俩要花钱+要你的账号，没法替你做；但一次 demo 的花费通常就几美分到不到 1 美元。）

其它所有事——装环境、起 LiveKit、起服务、跑通——都交给本地 Claude Code（见 `ACCEPTANCE_PROMPT.md`）。

---

## ① 拿 Anthropic（Claude）API Key —— 给 `ANTHROPIC_API_KEY`

1. 打开 https://console.anthropic.com ，用邮箱注册 / 登录。
2. 左下角点 **Settings（设置）** → 进 **Billing（账单）**。
   - 点 **Add payment method / Buy credits**，绑一张信用卡，**充值最少额度**（如 $5）即可，足够 demo。
3. 左侧菜单点 **API keys** → 右上 **Create Key**。
4. 给它起个名字（如 `voice-agent`）→ **Create** → **复制**弹出的 key（形如 `sk-ant-...`）。
   ⚠️ 这串 key 只显示一次，复制好。
5. 把这串 key 交给本地 Claude Code（它问你要 `ANTHROPIC_API_KEY` 时粘贴即可）。

## ② 拿 OpenAI API Key —— 给 `OPENAI_API_KEY`

1. 打开 https://platform.openai.com ，注册 / 登录。
2. 右上头像 → **Settings** → **Billing** → **Add payment details**，绑卡并充一点额度（如 $5）。
   - 注意：要的是 **platform.openai.com 的 API**，不是 ChatGPT 订阅（那俩是两码事）。
3. 左侧 / 右上头像 → **API keys**（或 https://platform.openai.com/api-keys ）→ **Create new secret key**。
4. 起名 → **Create** → **复制** key（形如 `sk-...`）。同样只显示一次。
5. 交给本地 Claude Code（它问你要 `OPENAI_API_KEY` 时粘贴）。

## ③ 怎么把 key 给本地 Claude Code

两种都行，任选：
- **直接粘贴**：当本地 Claude Code 问"请提供 OPENAI_API_KEY / ANTHROPIC_API_KEY"时，把对应 key 粘给它，它会写进本地 `.env`（这个文件已被 `.gitignore`，不会上传，安全）。
- **自己填**：打开项目里的 `.env` 文件，把两行 `ANTHROPIC_API_KEY=` 和 `OPENAI_API_KEY=` 后面填上。

---

## 花费预期（放心）

- 一次完整语音 demo（几轮对话）大约：STT + TTS + Claude 合计 **几美分**。
- 反复测十几次也通常 **< $1**。充值 $5 量级完全够整个验收周期。
- 不用时不产生费用（按调用计费）。

## （可选）想让通知发到手机群，而不是只在后台看

默认**不需要**——保安直接在后台 Dashboard 点"放行"。如果你想额外收到手机推送：

- **Discord（最简单）**：
  1. 在你的 Discord 服务器里建/选一个频道 → 频道名旁 **齿轮(编辑频道)** → **整合 Integrations** → **Webhooks** → **New Webhook** → **Copy Webhook URL**。
  2. 告诉本地 Claude Code：把 `.env` 改成 `NOTIFY_CHANNEL=discord` 并填 `DISCORD_WEBHOOK_URL=<刚复制的>`。
- **Telegram**：找 `@BotFather` 发 `/newbot` 拿 `TELEGRAM_BOT_TOKEN`；给你的 bot 发条消息，再让本地 CC 用 `getUpdates` 取 `TELEGRAM_CHAT_ID`；`.env` 设 `NOTIFY_CHANNEL=telegram`。

---

**总结**：你的活就是 ①② 拿两个 key、③ 粘给本地 CC，然后**打开网页和 AI 说话、在后台点放行**做体验测试。其余别管。

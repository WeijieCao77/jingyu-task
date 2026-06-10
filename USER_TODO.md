# 🙋 需要你亲手做的事（手把手教程）

我们现在**默认只用一个 key 把线路跑通**。其余所有事都交给本地 Claude Code（见 `ACCEPTANCE_PROMPT.md`）。

| 你想测的版本 | 你需要提供 |
|---|---|
| **电脑本机浏览器语音**（最省事，先跑这个） | 只要 **`OPENAI_API_KEY`** |
| **手机扫码版（路 A，任何网络）** | `OPENAI_API_KEY` + **LiveKit Cloud 免费账号**（3 个值） |
| 手机扫码版（路 B，同一 WiFi） | 只要 `OPENAI_API_KEY`（零账号） |

> 想把 LLM 大脑换成 Claude（更强的中文对话）才需要 Anthropic key —— 可选，见最后。

---

## ① 拿 OpenAI API Key —— `OPENAI_API_KEY`（必需）

1. 打开 https://platform.openai.com ，注册 / 登录。
2. 右上头像 → **Settings** → **Billing** → **Add payment details**，绑卡并充一点额度（如 $5）。
   - 注意：要的是 **platform.openai.com 的 API**，不是 ChatGPT 订阅（两码事）。
3. 打开 https://platform.openai.com/api-keys → **Create new secret key** → 起名 → **Create**。
4. **复制** key（形如 `sk-...`，只显示一次）。
5. 交给本地 Claude Code（它问你要 `OPENAI_API_KEY` 时粘贴），或自己填进项目 `.env` 文件。

**有了这一个 key，就能跑"电脑本机浏览器语音"完整流程了。**

## ② （仅扫码版路 A）拿 LiveKit Cloud 免费账号 —— 3 个值

手机扫码要连公网媒体服务器，用 LiveKit Cloud **免费版**（免费、不用付款，只是注册个账号）：

1. 打开 https://cloud.livekit.io ，用邮箱 / GitHub 注册登录。
2. 创建一个 **Project**（随便起名）。
3. 进项目 → **Settings** 里能看到：
   - **Project URL / WebSocket URL**（形如 `wss://xxxx.livekit.cloud`）→ 这是 `LIVEKIT_URL`
   - **API Key** → `LIVEKIT_API_KEY`
   - **API Secret** → `LIVEKIT_API_SECRET`（点显示/复制）
4. 把这 3 个值交给本地 Claude Code（按 `QR_DEMO.md` 路 A 的步骤）。
   - 免费额度按连接分钟计，个人测试根本用不完，不会扣费。

> 只测电脑本机版 / 扫码路 B（同一 WiFi）的话，**不需要**这个账号——本地 Claude Code 会用本机 Docker 起 LiveKit。

## ③ 怎么把这些值给本地 Claude Code

两种都行：
- **直接粘贴**：当它问"请提供 OPENAI_API_KEY / LiveKit 三个值"时，粘给它，它写进本地 `.env`。
- **自己填**：打开项目根目录的 `.env` 文件（由 `.env.example` 复制而来），把对应行填上。

> 🔐 安全：`.env` 已被 `.gitignore` 忽略，**永远不会上传**，即使仓库是 public，你的 key 也只在你本机。
> 仓库里只有 `.env.example`（模板，无真实密钥）。**铁律：不要把 `.env` 提交上去**（正常操作不会误传）。

---

## 花费预期（放心）

- 一次完整语音 demo（几轮对话）约 **几美分**；反复测十几次通常 **< $1**。充 $5 量级够整个验收周期。
- 按调用计费，不用时不产生费用。LiveKit Cloud 免费额度个人测试用不完。

## （可选）想用 Claude 当大脑 —— `ANTHROPIC_API_KEY`

默认用 OpenAI 当大脑，已够用。若想要更强中文对话：
1. https://console.anthropic.com → 登录 → Settings → Billing 充值 → API keys → Create Key → 复制（`sk-ant-...`）。
2. 让本地 CC 把 `.env` 改成 `LLM_PROVIDER=anthropic`、`LLM_MODEL=claude-haiku-4-5`，并填 `ANTHROPIC_API_KEY`。

## （可选）想让通知发到手机群（而非只在后台点放行）

默认不需要（保安在后台 Dashboard 点"放行"即可）。想额外手机推送：
- **Discord**：频道 → 编辑频道 → 整合 → Webhooks → New → Copy URL；让 CC 设 `NOTIFY_CHANNEL=discord` + `DISCORD_WEBHOOK_URL`。

---

**总结**：先拿 ① 一个 OpenAI key → 粘给本地 CC → 打开网页和 AI 说话、后台点放行。想测扫码版再按 ② 拿 LiveKit Cloud 三个值。其余别管。

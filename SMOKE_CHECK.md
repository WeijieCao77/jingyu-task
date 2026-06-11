# 首次运行 Smoke Check（真跑前/中排查清单）

> 背景诚实说明：本项目在远程沙箱开发（无法连 OpenAI/LiveKit、无音频），**离线单测 37 个全绿**，
> 但端到端语音链路尚未真实执行过。本清单 = 第一次真跑最可能出问题的点 + 即时判别方法。
> 给本地 Claude Code：跑验收时按此逐项核对，出错先对照"症状→原因"再修。

## A. 起服务前

| # | 检查 | 命令/方法 | 期望 |
|---|---|---|---|
| 1 | 依赖完整 | `pip install -r requirements.txt` 末尾无 error | exit 0 |
| 2 | 单测全绿 | `PYTHONPATH=src pytest -q` | `39 passed` |
| 3 | 模型已下载 | `PYTHONPATH=src python -m visitor_agent.agent download-files` | 正常退出（首次约 1–2 分钟） |
| 4 | .env 生效 | `PYTHONPATH=src python -c "from dotenv import load_dotenv;load_dotenv();import os;print(bool(os.getenv('OPENAI_API_KEY')), os.getenv('LIVEKIT_URL'))"` | `True ws://localhost:7880` |
| 5 | LiveKit 活着 | `curl -s localhost:7880` | 有响应（任意 HTTP 响应即可，连接被拒=容器没起） |

## B. 起服务时（症状 → 原因 → 处置）

| 症状 | 多半是 | 处置 |
|---|---|---|
| worker 报 `LIVEKIT_URL is not set` | .env 没被进程读到 | 确认从仓库根目录启动；或 `export $(grep -v '^#' .env | xargs)` |
| worker 连不上 / 一直重试 | LiveKit 容器没起/端口占用 | `docker ps`、`docker logs livekit-dev`；7880/7881/7882 是否被占 |
| worker 起来但来访无 agent 加入 | dispatch 问题 | dev 模式默认自动 dispatch；确认 `/token` 用的 room 与 worker 同一 LiveKit |
| `/voice` 点接入报 "LiveKit not configured" | web 进程没读到 .env | 重启 `run_web.sh`（main 里已 load_dotenv，须从根目录跑） |
| 浏览器连上但听不到 AI | 自动播放被拦 / TTS 失败 | 看 worker 日志有无 TTS 错误；页面再点一次（已做手势 play 兜底）；换 Chrome |
| AI 听不懂/不回应 | STT 失败或 key 无效 | worker 日志找 `401/insufficient_quota`；`curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"` |
| 回答是英文/中英混 | LLM 没吃到中文指令 | 确认没改 prompts.py；LLM_MODEL 是否被改坏 |
| `database is locked` | 老库没开 WAL | 删 `data/visits.db*` 重来（WAL 已默认开启） |
| Dashboard 不动 | SSE 被代理缓冲 | 直连 localhost 不要经代理；看 `/events/stream` 是否有输出 |
| 放行按钮 404 | web/agent 用了不同 DATABASE_URL | 两终端都从根目录起，确保同一 .env |

## C. 跑通后的验收断言

1. `/voice` 接入 → **AI 先开口**中文问"车牌、找哪家、什么事"。
2. 一句话给多项信息 → Dashboard 字幕+字段实时出现，**不重复追问已给项**。
3. 信息齐 → AI 复述确认；访客记录出现"待确认"。
4. 点 ✅放行 → 状态"已放行"、出现"抬杆"事件、有开闸时间。
5. **计时**：AI 开口 → 访客记录出现 **≤25 秒**。
6. 同车牌再来一次 → 开场直接确认（回访识别）。
7. `python -m visitor_agent.guard_query "今天多少访问车辆？"` 数字正确。

## C5. Windows 专用备注（已在真实 Windows 11 ARM64 跑通）

| 事项 | 做法 |
|---|---|
| **ARM64 机器（骁龙等）** | 必须用 **x64 Python**（不是系统自带 ARM64 Python）——`livekit-blingfire` 无 win_arm64 wheel。装官方 x64 Python 3.12（用户级即可），用它建 venv；Win11 on ARM 的 x64 模拟能加载所有原生扩展。 |
| **没装 Docker** | 用 LiveKit 官方 Windows 二进制：从 github.com/livekit/livekit/releases 下对应平台包，`livekit-server.exe --dev`（等价 `ws://localhost:7880` + devkey/secret）。会打印一段 `capacity management is unavailable` 告警，**非致命可忽略**。 |
| **PowerShell 命令** | `source .venv/bin/activate` → `.\.venv\Scripts\Activate.ps1`；`cp` → `Copy-Item`；`mkdir -p` → `New-Item -ItemType Directory -Force`；行内 `PYTHONPATH=src python ...` → 先 `$env:PYTHONPATH="src"; $env:PYTHONUTF8="1"` 再 `python ...`。 |
| **pip 刷红字 `Logging error`** | OneDrive/中文路径 + 旧控制台导致，**只影响日志不影响安装**；末行有 `Successfully installed` 即成功。可设 `$env:PIP_NO_COLOR=1`。 |
| **`curl`** | PowerShell 里 `curl` 是 `Invoke-WebRequest` 别名；用 `Invoke-WebRequest http://localhost:7880` 或 `curl.exe`。 |
| **dev 模式房间坑** | LiveKit 只对**新建房间**自动派 job。若先开浏览器占住 `voice-demo` 房间再启/重启 worker，AI 不出声 → **刷新/重连浏览器**（或先关标签页清空房间）。 |

## D. 已知未验证项（修复时别误判为新 bug）

- 浏览器↔本地 LiveKit↔worker 的房间互通是**首次验证点**（/token 发的 room 名为 `voice-demo`，dev 模式 worker 自动加入任意房间——若没加入，先查 worker 日志而不是改代码）。
- OpenAI STT 对中文电话口语的断句质量未实测；若断句差，候选项：`STT_MODEL=gpt-4o-transcribe`（已默认）→ 试 `whisper-1` → 上 `deepgram`。
- 25 秒达标未实测；若超，先看 worker 日志里每轮的 STT/LLM/TTS 耗时分布再定优化点。

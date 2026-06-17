# 本地落地问题清单 + 跑通记录 / Local Run Issue Log & Working Recipe

> **目的**:把 `WeijieCao77/jingyu-task` 分支 `claude/voice-agent-takehome-qzjbd2`(园区语音访客登记 Voice Agent)在一台真实 Windows 机器上跑通,记录全过程的问题与解法,供仓库侧 AI 做永久修复。
>
> **测试环境**:Windows 11 Home，**ARM64**（骁龙类机器），PowerShell 5.1，**未安装 Docker**。系统自带 Python 是 **ARM64 原生 3.12.10**。仅提供一个 `OPENAI_API_KEY`，其余全自动完成，要求**不改架构**。
>
> 每条问题格式:**症状 → 根因 → 临时解法(本地已做) → 建议永久修复(repo 侧)**。优先级:🔴 P0 阻断 / 🟠 P1 影响功能 / 🟡 P2 体验 / 🟢 P3 文档。

---

## 一、最终结论 & 跑通配方(How it finally ran)

**结论**:在做完下列修复后,**端到端出声链路已跑通**——浏览器接入后 agent 成功入房、用 OpenAI TTS 发出中文问候(已用无声探测客户端客观验证:`PARTICIPANT_JOINED agent-...` 且收到 agent 音频轨)。单测 **39 passed**。STT/LLM(听懂+填槽)需真人开口说话才能最终确认,接入后即可验。

**可复现的本地运行配方(Windows / PowerShell)**:

```powershell
# 0) 关键前提:本机是 ARM64,必须用 x64 Python(见 P0-1)
#    已安装在 C:\Users\15967\python312-x64\python.exe
& "C:\Users\15967\python312-x64\python.exe" -m venv .venv

# 1) 装依赖(requirements.txt 已加 tzdata,见 P1-1)
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2) 单测
$env:PYTHONPATH="src"; $env:PYTHONUTF8="1"
.\.venv\Scripts\python.exe -m pytest -q          # 39 passed

# 3) 起本地 LiveKit(无 Docker,用原生二进制,见 P0-2)
#    已下载在 C:\Users\15967\livekit-dev\livekit-server.exe(arm64 原生)
C:\Users\15967\livekit-dev\livekit-server.exe --dev   # ws://localhost:7880, devkey/secret

# 4) .env:OPENAI_API_KEY + LIVEKIT_URL=ws://localhost:7880 + devkey/secret + sqlite + 8080

# 5) 两个进程(各开一个窗口,均从仓库根目录、x64 venv)
$env:PYTHONPATH="src"; $env:PYTHONUTF8="1"
.\.venv\Scripts\python.exe -m visitor_agent.web.server     # 终端A → :8080
.\.venv\Scripts\python.exe -m visitor_agent.agent dev      # 终端B → 连 LiveKit、registered

# 6) 浏览器(Chrome):
#    访客 http://localhost:8080/voice  ·  后台 http://localhost:8080/dashboard
#    常客 http://localhost:8080/admin  ·  介入 http://localhost:8080/guard_call?room=voice-demo
```

> ⚠️ dev 模式坑:LiveKit 只对**新建房间**自动派 job。若先开浏览器占住 `voice-demo` 房间、再(重)启 worker,worker 收不到"房间已存在"事件 → 不派 job → AI 不出声。处置:重启 worker 后,**刷新/重连浏览器**(或先关标签页让房间清空)再接入。

---

## 🔴 P0-1:`livekit-blingfire` 在 Windows ARM64 上无 wheel,导致全部依赖装不上

**症状**
```
ERROR: Cannot install -r requirements.txt because:
    livekit-agents 1.5.x depends on livekit-blingfire<2 and ~=1.1
Additionally, some packages in these conflicts have no matching distributions
available for your environment:
    livekit-blingfire
ERROR: ResolutionImpossible
```
去掉 `[turn-detector]` extra 也一样——`livekit-agents 1.5` **核心本身**就依赖 `livekit-blingfire`。

**根因**
- 机器是 Windows on ARM64,系统 Python 也是 ARM64 原生构建(`sys.version` 末尾 `64 bit (ARM64)`),pip 只接受 `win_arm64` 标签 wheel。
- `livekit-blingfire 1.1.0` 在 PyPI 只发了 `win_amd64`、`macosx_arm64`、`manylinux_aarch64`,**唯独没有 `win_arm64`,且无 sdist**。→ ARM64 Windows 原生 Python 下无解。

**临时解法(本地已做,未改架构)**
- 安装官方 **x64(AMD64)Python 3.12.10**(用户级静默装到 `C:\Users\15967\python312-x64`,无需管理员),用它建 venv。Windows 11 on ARM 自带 x64 用户态模拟,能正常加载所有 `win_amd64` 原生扩展(blingfire/numpy/onnxruntime)。之后 `pip install -r requirements.txt` 全部成功。
- 注意:模拟层下 `platform.machine()` 仍显示 `ARM64`,以 `sys.version` 的 `AMD64` 为准。

**建议永久修复(repo 侧)**
1. README 增加 "**Windows ARM64 用户请使用 x64 Python**"(emulation 路线,零代码改动)。
2. 或向上游 `livekit/agents` 反馈,为 `livekit-blingfire` 补 `win_arm64` wheel 或提供 sdist(仓库层面无法独立解决原生 ARM64)。

---

## 🔴 P0-2:未装 Docker,但 README/SMOKE_CHECK 默认用 Docker 跑 LiveKit

**症状**:`docker` 命令不存在;文档只给 `docker run ... livekit/livekit-server --dev` 一条路。

**根因**:Windows 装 Docker Desktop 很重(需 WSL2 + 重启),对"只想本地试"的用户门槛高。

**临时解法**:下载 LiveKit 官方 **Windows 原生二进制**(本机用 `livekit_1.13.1_windows_arm64.zip`,有原生 arm64 版),`livekit-server.exe --dev` 启动,效果与 Docker 等价(`ws://localhost:7880` + `devkey/secret`)。

**建议永久修复(repo 侧)**:文档补"非 Docker 备选":从 https://github.com/livekit/livekit/releases 下对应平台二进制,`livekit-server --dev`。并提示:Windows 上该二进制会打印一段 Prometheus 节点容量统计的堆栈告警(`capacity management is unavailable`),**非致命**可忽略。

---

## 🔴 P0-3:Windows 上 job 一启动就崩 ——「Plugins must be registered on the main thread」(AI 完全不出声、不回应)

**这是 Windows 上最致命的真实 bug —— 不修则无法语音对话。**

**症状**
- 浏览器 `/voice` 点接入后绿色麦克风在闪(已连上 LiveKit),但 **AI 既不说话也不回应**,后台时间线毫无反应。
- worker 日志每次来电必崩:
```
WARNING visitor_agent.agent  turn detector unavailable, using VAD only:
                             InferenceRunner must be registered on the main thread
ERROR   livekit.agents       unhandled exception while running the job task
Traceback (most recent call last):
  ... agent.py line 138, in entrypoint:  stt=build_stt(cfg),
  ... providers.py line 19, in build_stt:  from livekit.plugins import openai
  ... livekit/agents/plugin.py line 33, in register_plugin:
      raise RuntimeError("Plugins must be registered on the main thread")
RuntimeError: Plugins must be registered on the main thread
DEBUG livekit.agents  shutting down job task {"reason": "job crashed"}
```

**根因**
- `providers.py` 刻意用**惰性导入**(`from livekit.plugins import openai/silero` 写在 `build_stt/build_llm/build_tts/build_vad` 函数体内,见其 docstring "Optional providers use lazy imports")。
- 但 `Plugin.register_plugin()` 强制要求**在主线程、import 时**注册。LiveKit job 在 **Linux 用 fork**、**Windows 用 spawn**;Windows 下 `entrypoint()` 里的 build_*() 落在 job 子进程的**非主线程**,惰性 import 触发注册 → 抛 `RuntimeError` → **job 当场崩**,连开场白都发不出。
- 同根因也让 turn-detector 报 `InferenceRunner must be registered on the main thread`(与 P1-2 叠加,但这才是 Windows 上的首要原因)。
- 平台相关真实 bug:Linux 开发时不暴露,Windows(含本机 ARM64-x64 模拟)必现。

**临时解法(本地已改 `src/visitor_agent/agent.py`,仅加 2 行 import,逻辑/架构不变)**
```python
# 在 agent.py 顶层(模块加载 = 主线程)预先注册默认插件:
from livekit.plugins import openai as _openai  # noqa: E402,F401
from livekit.plugins import silero as _silero  # noqa: E402,F401
```
providers.py 的惰性 import 保持不变(此后变成"已注册"的 no-op),swappable 设计不受影响。
- 验证:重启 worker 后日志出现 `plugin registered livekit.plugins.openai / silero`;无声探测客户端连入新房间后观测到 `PARTICIPANT_JOINED agent-...` 并收到 agent 发布的音频轨(问候已由 OpenAI TTS 合成推流)。**崩溃消失,出声链路通。**

**建议永久修复(repo 侧)**
1. 在 `agent.py` 顶层 import 默认使用的 plugin 模块(本次采用),**或**用 `WorkerOptions(prewarm_fnc=...)` / 模块顶层完成注册,确保发生在主线程;providers.py 的惰性分支仅留给"可选 provider"。
2. **跨平台必修**——否则项目在 Windows 上完全无法语音对话。

---

## 🟠 P1-1:Windows 缺 IANA 时区库,`zoneinfo` 找不到 `Asia/Shanghai`,4 个测试失败

**症状**
```
zoneinfo._common.ZoneInfoNotFoundError: 'No time zone found with key Asia/Shanghai'
FAILED tests/test_integration.py::test_register_persists_and_then_recognizes_returning
FAILED tests/test_integration.py::test_full_dashboard_events_emitted
FAILED tests/test_session_logic.py::test_record_then_complete_pushes_once
FAILED tests/test_slots.py::test_entry_time_stamped         （首次:4 failed, 35 passed）
```

**根因**:项目用 `zoneinfo.ZoneInfo("Asia/Shanghai")`。Linux/macOS 有系统 IANA tzdb;**Windows 不自带**,Python 需 `tzdata` 包兜底。不止影响测试——运行时登记入场时间(`entry_time`)同样抛错。

**临时解法(本地已改 `requirements.txt`)**:`pip install tzdata`,并新增:
```
tzdata; sys_platform == "win32"   # Windows lacks the IANA tz DB that zoneinfo needs
```
重跑:**39 passed**。

**建议永久修复(repo 侧)**:直接采纳上面这行进 `requirements.txt`(环境标记 `; sys_platform == "win32"` 不影响 Linux/mac)。

---

## 🟠 P1-2:turn-detector 模型无法预下载(两处 bleeding-edge 依赖不兼容)

**症状(分两段)**
1) `download-files` 子命令已废弃且为空操作:
```
Invoking the download-files command via your agent script is deprecated as of 1.5.10. ...
```
退出码 0,但**实际没下载** turn-detector 模型(没有插件被注册到 download 流程)。

2) 手动触发下载时连撞两个新库 bug:
```
# 经 transformers 5.11.0:
OSError: Can't load the configuration of 'livekit/turn-detector'. ... config.json
# 绕过 transformers、直接 huggingface_hub 1.18.0:
RuntimeError: Cannot send a request, as the client has been closed.
```

**根因**:依赖被解析到最新大版本 `transformers==5.11.0`、`huggingface_hub==1.18.0`,二者都与 `livekit-plugins-turn-detector 1.5.17` + `livekit/turn-detector` 模型仓库(按 transformers 4.x 组织、无根目录 `config.json`)不兼容;且 `download-files` 经 agent 脚本调用在 1.5.10+ 已废弃。

**临时解法(未改架构)**:不强求 turn-detector。`agent.py` 内置降级——`build_turn_detection()` 抛错 → `turn_detection=None` → **纯 VAD 端点检测**(已冒烟验证)。打断(barge-in)靠 VAD + `allow_interruptions=True` 仍工作,缺它不影响验收 a–f。

**建议永久修复(repo 侧)**
1. `requirements.txt` 钉兼容版本,例如 `transformers>=4.40,<5`、`huggingface_hub>=0.23,<1`(上界以 1.5.x 实测为准)。
2. 修文档 `download-files` 命令为 `python -m livekit.agents download-files`,并确保能注册到 turn-detector 插件(否则需先 `import livekit.plugins.turn_detector.multilingual` 再触发 `_download_files()`)。
3. 不依赖 turn-detector 时,文档明确"Windows 默认 VAD-only 即可"。

---

## 🟠 P1-3:没有"挂断"机制 —— 访客和介入门卫都无法主动结束通话(用户实测发现)

**症状**:`/voice`(访客)与 `/guard_call`(门卫介入)页面接入后,**没有任何"挂断"按钮**;唯一结束方式是手动**关闭浏览器标签页**(页面仅有一行小字「说完可关闭页面挂断」)。门卫介入页同样无挂断。对真实使用是明显的 UX/功能缺口。

**根因**:`web/server.py` 内嵌的 `_VOICE_HTML` / `_GUARD_CALL_HTML` 里,`room` 对象是 `btn.onclick` 的**局部变量**,页面未暴露任何主动 `room.disconnect()` 的入口,也没有挂断 UI。

**临时解法**:按用户要求**不在本地改源码**,仅记录。测试期间用"关闭标签页"挂断(关页 → 房间清空 → agent job 自动结束,功能上可用)。

**建议永久修复(repo 侧,改动很小,只动两段内嵌 HTML/JS)**
- 把 `room` 提到外层作用域,加一个红色「挂断」按钮,接入后显示、点了调用 `room.disconnect()` 并复位 UI。示意:
```html
<button id="hang" style="display:none;background:#c62828">挂断</button>
```
```js
let room;                       // 提升作用域
btn.onclick = async () => {
  room = new LivekitClient.Room();
  // ...connect/setMicrophoneEnabled 后:
  hang.style.display='inline-block';
};
hang.onclick = async () => { try{ await room.disconnect(); }catch(_){}
  hang.style.display='none'; btn.disabled=false; st.textContent='已挂断'; };
```
- `/guard_call` 同样加;`room.on(Disconnected, ...)` 已存在,复位逻辑可复用。
- (可选增强)agent 侧:访客挂断或登记完成后,让 AI 说一句结束语并 `session.aclose()` 干净退出房间。

---

## 🟡 P2-1:文档命令全是 bash,Windows/PowerShell 无法直接执行

**症状/根因**:README、SMOKE_CHECK 用了 `source .venv/bin/activate`、`cp`、`mkdir -p`、行内 `PYTHONPATH=src python ...`、`export $(grep ...)`、`./scripts/*.sh`;`scripts/` 下只有 `.sh`,无 `.ps1`/`.bat`。

**临时解法(PowerShell 等价,供文档参考)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1                 # 或直接用 .\.venv\Scripts\python.exe
$env:PYTHONPATH="src"; $env:PYTHONUTF8="1"
.\.venv\Scripts\python.exe -m pytest -q
Copy-Item .env.example .env                  # = cp
New-Item -ItemType Directory -Force data      # = mkdir -p
```

**建议永久修复(repo 侧)**:`scripts/` 增加 `run_web.ps1`/`run_agent.ps1`/`run_sim.ps1`,或 README 增加 "Windows (PowerShell)" 命令对照表。

---

## 🟡 P2-2:pip 26.x 在 OneDrive 中文路径 + 旧版控制台下刷红字(非致命)

**症状**
```
--- Logging error ---  ... self.handleError(record)
Message: 'Successfully installed %s'           # 安装其实成功
assert _stderr_console is not None, "stderr rich console is missing!"
```

**根因**:项目目录在 OneDrive、含中文路径(`…\桌面\蓝色鲸鱼第三轮任务\…`),pip 26.x 的 rich 日志渲染器在 Windows legacy console 上报渲染异常,**只影响日志输出、不影响安装结果**。

**临时解法**:忽略红字,以末行 `Successfully installed` 为准;设 `$env:PYTHONUTF8="1"` 减少中文编码问题。

**建议永久修复(repo 侧)**:文档提示 Windows 用户见到 pip `Logging error` 时,只要末行有 `Successfully installed` 即成功;可设 `PIP_NO_COLOR=1` 抑制。

---

## 🟡 P2-3:离线模拟器 `sim/run_text.py` 写死 Anthropic,只有 OpenAI key 跑不了

**症状/根因**:README 称"默认全 OpenAI,单 key 即可",但 `sim/run_text.py` 里 `import anthropic` + `anthropic.Anthropic(api_key=cfg.anthropic_api_key)` 且用 `cfg.llm_model`。当 `LLM_PROVIDER=openai`、只有 `OPENAI_API_KEY` 时,这个"无麦克风文本仿真"路径(`run_sim.sh --live`)无法运行(无 Anthropic key,且 gpt-4o-mini 不是 Anthropic 模型)。

**临时解法**:无(该工具是加分项,非主链路);主链路用真实语音验证。

**建议永久修复(repo 侧)**:让模拟器尊重 `LLM_PROVIDER`——OpenAI 时走 OpenAI Chat Completions 的 tool-use 循环,Anthropic 时才走 anthropic。这样"单 OpenAI key 跑通全部"才名副其实。

---

## 🟡 P2-4:`test_token_requires_config` 在存在真实 `.env` 时必失败(测试隔离 bug)

**症状**:配好 `.env`(运行 app 必需)后,`pytest` 出现 `FAILED tests/test_dashboard.py::test_token_requires_config - assert 200 == 400`(其余 38 通过)。无 `.env`(如 CI)时 39 全过。

**根因**:`config.Settings` 用 `SettingsConfigDict(env_file=".env")`,pydantic-settings **会直接从磁盘读 `.env`**。而该测试只 `monkeypatch.delenv("LIVEKIT_*")` 删了进程环境变量、**没有阻止读 `.env` 文件**,于是 LiveKit 仍被判为"已配置",`/token` 返回 200 而非预期 400。**非功能回归**——`/token` 实际工作正常。

**临时解法**:无(不影响运行);知道它是测试隔离问题即可。

**建议永久修复(repo 侧)**:测试里禁用 .env 读取,例如 `monkeypatch.setattr(config.Settings.model_config, "env_file", None)`(或在 reload 前设 `SETTINGS_*`/用 `_env_file=None` 实例化),保证该用例不受本地 `.env` 影响。

---

## 🟢 P3:文档小瑕疵

- **SMOKE_CHECK.md 写 `37 passed`,实际 `39 passed`**(测试数已增,文档过期)。
- README 的 `curl -s localhost:7880` 在 PowerShell 下 `curl` 是 `Invoke-WebRequest` 别名,参数语义不同;Windows 建议 `Invoke-WebRequest http://localhost:7880` 或 `curl.exe`。

---

## 二、验证证据(Proven vs. Not-yet)

**已客观验证 ✅**
- 依赖安装齐全(x64 venv):`livekit-agents 1.5.17 / numpy 2.4.6 / onnxruntime 1.26.0 / openai 2.41.1 / transformers 5.11.0 / huggingface_hub 1.18.0`。
- `pytest -q` → **39 passed, 2 warnings**(warning:starlette TestClient 弃用 + JWT key 长度,无害)。
- silero VAD 模型随包自带(`silero_vad.onnx`),x64 模拟层加载正常;turn-detector 干净降级 VAD。
- LiveKit `livekit-server.exe --dev` → `http://localhost:7880` 返回 `200 OK`,端口 7880/7881/7882 监听。
- Web server(:8080)→ `/health` 200、`/voice` 200、`/token` 正常签发 LiveKit JWT。
- OpenAI key 有效,`gpt-4o-mini / gpt-4o-transcribe / gpt-4o-mini-tts` 三模型均可用。
- **修复 P0-3 后**:无声探测客户端连入新房间 → `PARTICIPANT_JOINED agent-AJ_...` + 收到 agent 音频轨 = **agent 入房并用 OpenAI TTS 发出问候**,出声链路打通。

**尚未验证 ⏳(需真人开口说话)**
- STT 听懂中文 + LLM 一句多槽/不重问 + 3 轮内完成。
- "AI 开口 → 访客记录出现 ≤25 秒" 真实计时。
- 放行抬杆 stub、回访识别、转人工(客户要求 / 保安主动介入 `/guard_call` 让位对讲)。
- 风险点:`openai>=2.0` SDK 与 `livekit-plugins-openai 1.5.17` 对 `gpt-4o-transcribe` 流式 STT、`gpt-4o-mini-tts` 的 `instructions` 参数兼容性(未实测)。

---

## 三、本地改动汇总

| 文件/项 | 改动 | 影响架构? |
|---|---|---|
| `requirements.txt` | 新增 `tzdata; sys_platform == "win32"`(修 P1-1) | 否(平台依赖) |
| `src/visitor_agent/agent.py` | 顶层加 2 行 `from livekit.plugins import openai/silero`(修 P0-3) | 否(平台 bug 修复,逻辑不变) |
| `.env` | 由 `.env.example` 生成,填本地值(OpenAI key / `ws://localhost:7880` / devkey/secret / sqlite / 8080) | 否(本地配置,gitignore) |
| `LOCAL_RUN_ISSUES.md` | 本文档(新增) | 否 |
| 其余 `src/**` | **无改动** | — |
| 环境(非仓库内) | 装 x64 Python 3.12(`C:\Users\15967\python312-x64`);下载 LiveKit Windows arm64 二进制(`C:\Users\15967\livekit-dev`) | — |

> turn-detector extra 在排查中曾临时去掉又还原,**最终与原版一致**。

---

## 四、给 repo 的推荐 patch 清单(汇总)

1. **`requirements.txt`**
   ```
   tzdata; sys_platform == "win32"
   transformers>=4.40,<5
   huggingface_hub>=0.23,<1
   ```
2. **`src/visitor_agent/agent.py`** 顶层加默认插件 import(主线程注册,修 Windows spawn 崩溃)。
3. **`web/server.py`** 给 `/voice`、`/guard_call` 加「挂断」按钮(P1-3)。
4. **`sim/run_text.py`** 按 `LLM_PROVIDER` 支持 OpenAI(P2-3)。
5. **文档**:Windows ARM64 用 x64 Python;非 Docker 起 LiveKit;PowerShell 命令对照;`37→39 passed`;`download-files` 命令修正。

---

## 🔴 P0-4(realtime 分支):`VOICE_MODE=realtime` 下 `session.say(GREETING)` 崩溃,问候发不出、job 挂掉

**分支**:`feature/realtime-voice`(HEAD f48db54)。**症状**:浏览器接入后,worker 日志:
```
RuntimeError: trying to generate speech from text without a TTS model or a
RealtimeSession that supports say(); add a TTS model to AgentSession to enable
... unhandled exception while running the job task
```
**根因**:`agent.py` 末尾 `await session.say(GREETING, allow_interruptions=True)` 对 **pipeline 模式**有效,但 **realtime(speech-to-speech)模式没有独立 TTS**,`RealtimeSession.say(fixed_text)` 不被支持 → 开场问候抛异常 → job 崩。
**临时修复(本地已改 agent.py,未改架构)**:问候按模式分支——
```python
if cfg.voice_mode == "realtime":
    await session.generate_reply(instructions=f"用自然中文向访客开场问好：{GREETING}")
else:
    await session.say(GREETING, allow_interruptions=True)
```
验证:探测客户端连入 → agent 入房 + 出声(40 帧),日志 `voice_mode=realtime`、无 RuntimeError。
**建议永久修复(repo)**:realtime 分支的 entrypoint 用 `generate_reply` 发开场白(或任何 realtime 兼容方式),勿用 `say(fixed_text)`。

**实测延迟(realtime)**:点击「开始对话」→ AI 出声 ≈ **1.44 秒**(对比 pipeline 冷启动明显更快)。

**注意**:`feature/realtime-voice` 是从 roster 合并之前分出的,**不含公司名单匹配**(roster.py 等被删)。若要 realtime + roster 同时可用,需 repo 把两条分支合并。

---

# 六、功能请求(给 repo AI)/ Feature Requests

## FR-1:realtime 提速 与 公司名单匹配(roster)需要同时可用

**现状**:
- `claude/voice-agent-takehome-qzjbd2`(dev,HEAD 6b73b49):有 **roster 公司名单匹配** + Telegram,但**只有 pipeline**(STT→LLM→TTS),首句冷启动慢(实测"等好久")。
- `feature/realtime-voice`(HEAD f48db54):有 **VOICE_MODE=realtime**(speech-to-speech,实测首句 ≈1.44s、明显更快),但**从 roster 合并之前分出**,**删掉了 roster.py 等**,所以**没有名单匹配**。

**用户需求**:既要 realtime 的低延迟,又要 roster 的公司名纠正(如"蓝色金鱼科技"→"蓝色鲸鱼科技")。

**建议(repo)**:把 `feature/realtime-voice` 与 dev 的 roster 合并到一条分支——即在 realtime 模式下,`RegistrationSession` 仍注入 `roster_match=make_matcher(...)`,`record_visitor_info` 工具照常把单位 snap 到名单官方名。两者互不冲突(roster 在 session_logic 层、与 voice_mode 无关),只是分支分裂导致没并到一起。本地已验证:realtime 出声正常、roster 匹配器在 dev 分支单测全过——合并后应可共存。

## FR-2:门卫点「放行」后,AI 用语音对访客说一句"已放行/请进"

**现状**:门卫在 `/dashboard` 点「✅放行」→ `POST /api/confirm/{id}` 标记 confirmed + 抬杆 stub + 写 confirmed/gate 事件。但**访客端那通正在进行的语音通话里,AI 不会说任何话**——访客不知道已经放行了。

**用户需求**:放行后,AI 语音对访客说一声(如「已为您放行,请进,栏杆已抬起,祝您顺利」)。

**建议实现(repo,跨进程协调)**:
- Web confirm 端点(在 web 进程)与 AI 会话(在 agent 子进程)目前只共享 SQLite,没有直接消息通道。最干净的做法是 **LiveKit 数据消息**:
  1. `POST /api/confirm/{id}` 成功后,用已有的 LiveKit API 凭据向该访客房间(room=`voice-demo` 或按 call_id)发一条数据消息,如 `{"type":"approved","visit_id":id}`(`livekit.api` 的 RoomService 发 data,或 server SDK `publish_data`)。
  2. agent `entrypoint` 注册 `@ctx.room.on("data_received")`,收到 `approved` 时:
     - pipeline 模式 `await session.say("已为您放行，请进，栏杆已抬起。")`;
     - realtime 模式 `await session.generate_reply(instructions="告诉访客已放行，请进，栏杆已抬起，礼貌道别")`(注意:realtime 不能用 say(固定文本),见 P0-4)。
- 备选:agent 在登记完成后轮询 DB 该 visit 的 status,翻成 confirmed 时播报(实现简单但有轮询开销)。
- 需处理:访客可能已挂断(房间无人)→ 发送失败时静默忽略,不影响放行/抬杆。

> 备注:本地助手可按需先做一个最小原型验证(web 发 data + agent 收并播报),但属功能新增、跨 web/agent 两个文件,建议在 repo 正式实现。

---

# 七、真实电话验收发现(2026-06-12，用户拨 Twilio 号实测后反馈)

## FR-3:开场太生硬，需要一句开场白(再进入提问)

**现象**:电话/浏览器一接通,AI **直接开问**"您好，请问车牌号多少，今天找哪家公司，什么事儿？"——用户反馈过于死板生硬,缺一句寒暄/自报家门的开场。

**根因**:`src/visitor_agent/prompts.py:10` 的 `GREETING` 本身就是那句"直接三连问",接通即说;没有热场前缀。

**建议(repo)**:把 `GREETING` 改成"先一句温和开场 + 再并问",例如:
```python
GREETING = "您好，这里是园区门岗，我是智能门卫，很高兴为您服务～请问您的车牌号、找哪家公司、来办什么事呢？"
```
- 仍保留 SYSTEM_PROMPT 里"一并问、不要逐字段审问"的要求(prompts.py:18),只是开头加一层礼貌缓冲。
- 注意 **25 秒计时从开口算起**,开场白别太长(1 句即可),以免吃掉时间预算。

## FR-4:结束语后 3–5 秒无应答 → agent 应自动挂断

**现象**:AI 说完结束语(如"…已通知门卫,请稍等放行")后,通话**一直挂着不断**,既费线路也不自然。

**期望**:结束语说完后,若 **3–5 秒内访客没有新的话/新问题**,agent 主动挂断电话。

**建议实现(repo,agent.py entrypoint)**:
- 登记完成(`reg.completed` 置真)并说完收尾话后,启动一个**静默看门狗**:
  - 监听用户新一轮发言(`session` 的 `conversation_item_added` 中 role=user,或 `user_input_transcribed` 事件)→ 每次重置计时;
  - 计时器到点(建议 4s,可配 `HANGUP_SILENCE_SEC`)且期间无新用户输入 → 结束通话:
    `await session.aclose()` 然后 `await ctx.room.disconnect()`(SIP 通话会随房间关闭而挂断;也可用 RoomService delete_room)。
  - 仅在**完成后/已道别**才武装看门狗,避免对话中途的正常停顿被误挂。
- 兜底:再加一个全局最长通话时长(如 120s)防止异常情况下线路常开。
- 鲁棒性:访客可能已先挂断 → 关闭/断开要 try/except,不报错。

> 备注:这两条都是验收实测反馈,本地助手按用户要求**只记录、未改源码**,交由 GitHub 侧 AI 正式实现。

## FR-5:对话异常时主动给"转人工"出口(尤其"找的公司不在园区名单")

**需求**:当对话出现 AI 无法妥善处理的情况时,AI 应**主动转人工**,并告诉访客"已通知门卫、马上请门卫师傅来"。典型触发:**访客要找的公司在园区名单里搜不到**;以及其他特殊/异常情况——**具体由 AI 自行判定**。

**现状**:
- 已有 `request_human` 工具 + SYSTEM_PROMPT 的【转人工】段(`prompts.py` 约 56–61 行),但当前触发仅限:访客明确要真人 / 连续听不清 / 访客拒绝提供信息或纠纷异常。
- **"公司不在名单"未触发转人工**:roster 仅在**命中**时返回"单位已匹配名单"提示;**未命中时静默**,直接按访客原话记录并继续,LLM 收不到"这家不在名单"的信号,也就不会升级。

**建议实现(repo)**:
1. **把 roster 未命中暴露给 LLM**:`session_logic.record()` 里,当已配置 roster 且给了单位却 `roster_match` 返回 None 时,追加一条提示,例如:
   `【单位不在园区名单】未找到"<原话>",可能听错或确不在册,先跟访客确认一次;仍无法对上就转人工核实。`
2. **扩展 SYSTEM_PROMPT【转人工】触发**,加入:"找的公司不在园区名单且无法澄清""遇到你判断处理不了的异常情况"——由 AI 判定后调用 `request_human`,并对访客说:"好的,我已通知门卫,马上请门卫师傅来帮您核实,请您稍等别挂机。"
3. **确保"已通知门卫"名副其实**:`request_human` 目前 emit `escalation` 事件 → 后台 `/dashboard` 显示 ⚠️转人工 + 介入按钮。建议**转人工时也走一次通知渠道推送**(Telegram/微信),让门卫离开后台也能收到。
4. **判定要稳**:名单可能不全,"未命中"不等于一定有问题——先让 AI 确认一次(是否听错/换个说法),确实对不上再升级,避免误转。

> 验收实测反馈,本地助手按要求**仅记录、未改源码**,交 GitHub 侧 AI 实现。

## FR-6:字母 b/d(及同类易混字母)听不清/读不清,核对环节尤其明显

**现象**:电话里访客报车牌字母 **B / D**(以及 e/g/p/t 等同类)时,STT 容易听混;AI 在**核对复述**时单读一个字母也不够清楚,访客难以判断对不对。

**根因**:中文语境下念单个拉丁字母本身辨识度低;`STT`(gpt-4o-transcribe / realtime 输入转写)对 b/d 这类近音字母区分弱;TTS 单字母回读同样模糊。属语音识别+合成的固有难点,**应在"核对话术"层缓解**。

**建议(repo)**:在 `prompts.py` 的【核对确认】里要求 AI:
- 回读车牌字母时**带消歧词**,例如:"B,Boy 的 B" / "D,Dog 的 D"(或中文习惯:"B,8 旁边那个 B");不要只蹦一个字母。
- 听访客报字母时若不确定,**主动用消歧词反问**:"您说的是 Boy 的 B,还是 Dog 的 D?"
- 可在 SYSTEM_PROMPT 给一份常用字母→消歧词对照(B-Boy、D-Dog、E-Egg、G-Good、P-Peter、T-Tom…),让 AI 统一用。
- (可选,后端)评估更强 ASR 或对车牌字母做受限词表/后处理纠正。

## FR-7:更正某项后,AI 不应重复已确认正确的项(只复述被改的那项)

**现象**:核对车牌+手机时,访客说"手机不对"并报了新号码,AI **却又把车牌从头念一遍、再念新手机**。车牌此前已确认无误,重念纯属浪费时间和算力(电话里尤其拖沓)。

**根因**:`prompts.py`【核对确认】现逻辑是"复述车牌和手机两项;某项不对→重报→**再复述一次**",没有区分"哪项已确认、哪项被改",于是整体重读。

**建议(repo)**:在 SYSTEM_PROMPT 增加状态意识——
- 记住哪些项**已确认正确**;当某项被更正时,**只复述被更正的那一项**让访客确认,不再重读已确认项。
  例如访客改手机:"好的,手机改成 138-0013-5678,对吗?"(**不再重复车牌**)。
- 仅当被改的项也确认无误后,再 `complete_registration`。
- 可顺带提醒:复述要简短,避免逐项全量重播。

> 均为真实电话验收反馈,本地助手按要求**仅记录、未改源码**,交 GitHub 侧 AI 实现。

## FR-8:手机号位数不校验(中国手机应 11 位,报了 10 位也被接受)

**现象**:访客报了一个**10 位**号码(可能是 STT 漏听一位,或访客少报),AI 直接收下并完成,**没发现位数不对**。中国大陆手机号应为 **11 位、且以 1 开头**。

**根因**:`slots.py` 的手机号处理多半只做"去非数字"归一化,**没有位数/格式校验**;`record`/核对环节也未据此提示 LLM。

**建议(repo)**:
- 在 `slots.py`(或 record 返回)加中国手机号校验:正则 `^1\d{10}$`(11 位、1 开头)。不满足时,在 `record_visitor_info` 返回里给 LLM 提示,如"【手机号位数异常】收到 10 位,中国手机应 11 位,请向访客确认重报"。
- 配合【核对确认】:复述手机号时若位数不对,**主动指出并请访客重报那一位/整段**(与 FR-6/FR-7 同属"核对纠错"链路)。
- 若项目要支持境外号码,校验应可按区号/locale 放宽;但默认中国园区场景按 11 位。

## FR-9:访客无具体拜访公司(如"参观园区")时,AI 强求公司 / 或自行编造一个公司

**现象**:访客说目的是"**参观园区**",并没有要找的具体公司。AI 的表现有两种都不对:① **硬要**访客提供一个具体公司;② **随便编/填了一个公司**(幻觉,信息失真)。

**根因**:SYSTEM_PROMPT 把"来访单位"当作必填四项之一,未考虑"无具体接待单位"的合理场景(参观、找物业/管理处、送快递到驿站等);且未明确**禁止编造**。

**建议(repo)**:
- **绝不编造**:在 SYSTEM_PROMPT 明确"只记录访客真实所说,严禁臆造单位/任何字段"。
- **允许无具体公司**:当事由是参观/找物业管理处/园区公共事务等,"来访单位"可填合理替代(如"园区参观""园区管理处")或标记为"无具体单位",**不强逼**访客报一个公司。
- **可结合 FR-5 转人工**:若园区策略要求必须有接待方而访客确无,转人工核实("已通知门卫,请稍等"),而不是卡住或编造。
- 产品上明确:此类来访的放行/登记口径(如归为"访客参观"类),让 complete 流程能正常收尾。

> 真实验收反馈,本地助手按要求**仅记录、未改源码**,交 GitHub 侧 AI 实现。

## FR-4b:自动挂断会"拦腰切断 AI 正在说的话"(看门狗计时口径错了)

**现象(真机实测)**:通话中 **AI 的语音正说着,说着突然断了**。不是崩溃,是自动挂断在 AI 收尾话还没播完时就触发了。

**根因**:`agent.py` 的 `_idle_watchdog` 用 **访客最后一次说话时间(`last_user`)** 算静默——`reg.completed and now - last_user > hangup_silence_sec` 就挂断。但**没考虑"AI 此刻还在说话"**:访客报完最后一项 → `complete_registration` 瞬间完成 → AI 开始念收尾话(realtime/TTS 输出要数秒)→ 然而"距访客上次说话"已超过 6 秒 → 看门狗在 AI 话中途挂断,切断语音。日志:`post-completion silence → hang up`(完成后约 6s)。

**临时缓解(本地已做)**:`.env` 设 `HANGUP_SILENCE_SEC=20`,给 AI 收尾话留足时间。但这是 band-aid——超长收尾仍可能被切。

**建议永久修复(repo)**:看门狗应从 **"AI 说完话之后"** 开始算静默,而不是从访客最后说话算:
- 监听 agent 说话状态(`session` 的 `agent_state_changed` → speaking/listening,或 `speech`/`playout` 结束事件),**AI 正在说话时绝不挂断**;
- 仅当 `reg.completed` **且 AI 已说完(idle)** 且此后静默 N 秒(默认 3–5s)→ 才 `aclose()`。
- 即把计时基准从 `last_user` 改成 `max(last_user, agent_last_spoke_end)`,或直接"agent 进入 listening 后开始计时"。

- 本地推送链路自检 OK @ 2026-06-13 19:27:39（local Claude → branch claude/voice-agent-takehome-qzjbd2）
- GitHub PAT 已配置用于本地推送认证(存 .env、设 git remote);推送验证 @ 2026-06-13 19:33:01

---

## 2026-06-13 真机轮次：realtime 电话"吞字/中途断音"修复
- 环境：Windows 11 ARM64 / x64 venv / livekit-agents 1.5.17 / VOICE_MODE=realtime（gpt-realtime, voice=marin）/ LiveKit Cloud + Twilio 电话
- 本轮做了什么：诊断并修复"电话里 AI 语音说着突然吞掉几个字/没声音"；降低 realtime 打断灵敏度 + 加远场降噪。

### 🟠 P1：电话语音中途吞字/断音
- 症状：手机通话时，AI 正说着突然没声、吞掉几个字。
- 根因：realtime 用 OpenAI **默认 server-VAD**；电话线路回声/底噪被误判为"访客开口"→ 触发 turn_detected / interrupt_response → **打断 AI 自己的语音**。agent.log 反复出现 `OpenAI Realtime API response reason=turn_detected`。`build_realtime` 此前未显式配置 `turn_detection`。
- 解决方法（本地已改 `src/visitor_agent/providers.py` 的 `build_realtime`）：显式设
  `turn_detection=server_vad`（threshold 0.6 / silence_duration_ms 600 / prefix_padding_ms 300 / interrupt_response=True 保留 barge-in）
  + `input_audio_noise_reduction=far_field`。两项阈值 env 可调：`REALTIME_VAD_THRESHOLD`、`REALTIME_SILENCE_MS`（已写本机 .env；代码内有默认值，无 .env 也生效）。
- 是否验证：✅ `pytest -q` 94 passed；✅ 探测客户端连 LiveKit Cloud，agent 正常入房+出声（带新 turn_detection 的模型构建/运行 OK）；⏳ **真机"吞字是否减少"待用户电话实测**。

### 🟢 顺带发现（未改）
- `guard_query` 工具偶发 JSON 解析错 `EOF while parsing a string`（LLM 产出被截断的 `until_iso`），属数据查询健壮性问题，建议工具入参解析做容错。

### 待办 / 给远程会话的建议
1. 把 `REALTIME_VAD_THRESHOLD` / `REALTIME_SILENCE_MS` 提升为 `config.py` 正式字段（我用 `os.getenv` 临时实现以减少与远程的冲突面）。
2. 若真机仍吞字：考虑 `interrupt_response=False`（彻底不被打断，牺牲 barge-in）或在电话路径加 AEC/回声消除。
3. `guard_query` 工具入参 JSON 容错（防截断/非法 JSON 直接报错）。

---

## 2026-06-13 真机轮次：国内 +86 电话接入（现用 Twilio 国际长途 + 未来 CPaaS 方案）

**需求**：中国手机经国际长途拨现有美国号即可使用——白名单门卫查询 + 另一号码普通入园放行对话；并备好未来用国内 CPaaS 拿 +86 号、可快速替换 Twilio 的完整方案（demo 暂不启用）。

**技术前提核对（已满足）**
- `normalize_phone` 对 +86 一致：`+8613812345678` / `008613812345678` / `13812345678` 均 → `13812345678`；`+1…` → `1…`。两边都过归一化，故 GUARD_PHONES 白名单匹配与来电显示预填对 +86 成立。
- **国内号普通入园放行**：现成可用——任意 +86 拨入未命中白名单 → 访客 agent，手机槽位按主叫号预填。无需改配置。
- **国内号白名单查询**：把该 +86 号加入 `.env` 的 `GUARD_PHONES`（逗号分隔）即生效。
- ⚠️ 真机风险：国际长途偶发丢/改主叫号；若来电不带 +86 主叫号，白名单匹配与预填失效（改用国内本地号后消失）。

**未来 CPaaS 迁移方案**：见新增文档 `CHINA_CPAAS_MIGRATION_PLAN.md`（架构、候选商、合规前提、快速替换步骤、代码改动量≈0、质量/延迟、时间线、给远程的建议）。核心：LiveKit 入口 URI 与 agent 固定、入站 trunk 接受任意来源 → 换运营商只需把新号 origination 指到同一 LiveKit SIP，并改几个 .env 值。

**给远程会话的建议**：把 `GUARD_PHONES` / `GUARD_DIAL_NUMBER` / `SIP_OUTBOUND_TRUNK_ID` / `REALTIME_*` 收进 `config.py` 正式字段 + `.env.example`，并在文档加"换运营商只需改这几处"一节，指向 CHINA_CPAAS_MIGRATION_PLAN.md。

---

## 2026-06-13 真机轮次：全量上云 Railway（GitHub 自动部署）

**目标**：不再本机起服务，整套迁到 Railway 常驻在线；以后 push 到分支自动构建上线。

**最终形态（已上线、已验证）**
- 一个 Railway 项目 `jingyu-voice-agent`：服务 `web`（Dockerfile：容器内同时跑 agent worker + FastAPI，`scripts/start.sh`）+ `Postgres-HN-9`（数据库）。
- 公网域名：`https://web-production-d105c.up.railway.app`（`/health` 返回 200；`/voice` `/dashboard` `/admin` `/ask` 可用，门卫 key=demo123）。
- agent worker 在容器内常驻、出站连 LiveKit Cloud：日志 `registered worker ... wss://jingyu-task-nhx84umh.livekit.cloud`（电话链路 Twilio→LiveKit→云端 worker 不变）。
- **GitHub 自动部署**：`railway service source connect --repo WeijieCao77/jingyu-task --branch claude/voice-agent-takehome-qzjbd2`。以后 push 到该分支 → Railway 自动构建+上线。
- 本机 web/agent 已全部停掉（避免两个 worker 抢同一 LiveKit 项目导致来电随机分派）。

**踩坑 1：容器崩溃循环 → 502（CRLF）**
- 现象：`scripts/start.sh: line 6: set: pipefail: invalid option name`，容器反复 Starting → 502。
- 根因：仓库在 Windows 检出时 `start.sh` 变成 CRLF，Linux 容器 bash 把行尾 `\r` 当成命令一部分（`...web.server\r` → ModuleNotFound → 退出）。
- 修复：Dockerfile 加 `RUN sed -i 's/\r$//' scripts/start.sh`（对 Windows 检出免疫）。已 commit `local: Dockerfile strip CR ...`（271a4d9）。**建议远程加 `.gitattributes`：`*.sh text eol=lf`。**

**踩坑 2：DATABASE_URL/密钥被加 UTF-8 BOM → 解析失败 / LiveKit 401**
- 现象：CRLF 修好后 web 仍崩 `sqlalchemy.exc.ArgumentError: Could not parse SQLAlchemy URL`；修好 DB 后 agent 连 LiveKit `401 Invalid response status`。
- 根因：在 Windows PowerShell 里用 **`railway variable set KEY --stdin`（管道/重定向喂值）** 时，值被前置了一个 **BOM 字符 U+FEFF**（码点 65279）。导致 `﻿postgresql://...` 无法解析、`﻿`+LIVEKIT key 认证 401、OPENAI/TELEGRAM 同样被污染。
- 修复：改用**参数形式** `railway variable set "KEY=VALUE"`（无 BOM）。DATABASE_URL 用 Railway 变量引用 `${{Postgres-HN-9.DATABASE_URL}}`（干净、自动同步）。4 个密钥重设后首字符校验为 s/A/l/8、长度正确。
- 教训：Railway CLI 在 Windows 上设密钥**别用 --stdin**，用 `KEY=VALUE` 参数；命令里用变量引用避免明文进终端记录。

**环境变量（web 服务，36 个含 Railway 注入）**：LLM/STT/TTS=openai、VOICE_MODE=realtime、LIVEKIT_*、DATABASE_URL=引用、NOTIFY_CHANNEL=telegram+TOKEN/CHAT、ROSTER/ACCESS、GUARD_ACCESS_KEY=demo123、GUARD_PHONES=+1857...,+8613500042868、REALTIME_VAD_*、HANGUP_SILENCE_SEC=20、SIP_OUTBOUND_TRUNK_ID、GUARD_DIAL_NUMBER、TIMEZONE、PORT=8080、PUBLIC_BASE_URL=域名。（GITHUB_PAT/HIKVISION/WEB_PORT 不上云。）

**给远程会话的建议**：①加 `.gitattributes` 强制 `*.sh` LF；②DEPLOY.md 增补「Windows 下设 Railway 密钥用参数而非 --stdin（BOM 坑）」；③把 `PORT` 读取与 `${{Postgres.DATABASE_URL}}` 引用写进 DEPLOY 范例。

---

## 2026-06-13 真机轮次：上云后造演示数据（常客名单/公司名单/DB 种子）

为测"常客回访"+"数据查询"，造了三份可复现的数据并入库 GitHub：
- `roster.demo.json`：园区公司名单（12 家，带同音 alias 供语音匹配）。
- `access.demo.json`：黑白名单（whitelist=常客：张师傅/李经理/王总/赵师傅；blacklist：沪A00000、13900000000）。
- `scripts/seed_demo.py`：清空 visits 后写入 21 条访客（11 人，5 个常客），created_at 跨今天/本周/本月、含 confirmed/pending、whitelist/blacklist 标记、不同时段，覆盖 count/list/busiest-hours/frequent-visitors 查询。

**Railway 接线**：`ROSTER_PATH=roster.demo.json`、`ACCESS_LIST_PATH=access.demo.json`（变量已设，随提交部署）。

**灌库方式**（数据在 Postgres 持久，平时无需重灌）：
- 远程一次性：`SEED_DATABASE_URL=<Postgres 的 DATABASE_PUBLIC_URL> python scripts/seed_demo.py`（脚本支持该 env 覆盖，经公网代理写云端库）。
- 或容器内：`python scripts/seed_demo.py`（用容器内 DATABASE_URL；需先 `railway ssh keys add` 且接受 host key）。

**验证（线上）**：/api/visits=21、/api/profiles(min2)=5 常客；NL 查询正确："今天来了5辆车"、"蓝色鲸鱼科技来过5次"、"最多的常客是张师傅5次"。

**Windows 测试坑（仅测试侧）**：PowerShell 用 Invoke-RestMethod 发中文 JSON 体若传字符串会被错误编码→服务端收到乱码问题→答非所问；需 `[Text.Encoding]::UTF8.GetBytes($json)` 以 UTF-8 字节发送。浏览器 /ask 无此问题。

**常客回访测试用**（任一）：车牌 沪A12345 或手机 13800138001 → 张师傅（5 次）；沪C66666/13611112222 → 赵师傅（4 次）。

---

## 2026-06-13 真机轮次：语音吞字/噪音修复 + 名单命名厘清 + 项目现状总览

### A. 本轮修改

**1) 语音 AI：吞字/卡顿 与 对噪音过敏（确认是两个独立问题）**
- 诊断：
  - *噪音过敏*：外界噪音越过 server-VAD → 被判为"访客在说话" → 打断 AI。
  - *安静也吞字*：电话扬声器的回声（**AI 自己的声音**）被麦克风拾到 → 同样被判为"访客在说话" → AI 自我打断 → 吞字；因为噪音源是 AI 自己，所以**安静环境也发生**。
  - 两者同源 = "打断太容易"。
- 修复（realtime 模式默认**禁用打断**，回声/噪音都切不断 AI）：
  - 模型层 `providers.build_realtime`：`turn_detection.interrupt_response=False`（默认）；降噪 `far_field`→`near_field`（电话/耳麦正确档）；VAD 阈值 0.6→0.8、静音 600→800ms。
  - 会话层 `agent.py`：realtime 的 `AgentSession(..., allow_interruptions=False)`（默认）。
  - 全部 env 可调：`REALTIME_ALLOW_INTERRUPT`(默认0=不打断)、`REALTIME_NOISE_REDUCTION`(near_field/far_field/off)、`REALTIME_VAD_THRESHOLD`(0.8)、`REALTIME_SILENCE_MS`(800)。想恢复 barge-in 设 `REALTIME_ALLOW_INTERRUPT=1`。
  - 改动文件：`providers.py`、`agent.py`、`.env`(本机)、Railway 变量。
- 残留风险（记录给收尾）：若安静仍偶有吞字，最可能是**跨太平洋网络抖动**（中国 ↔ 美国 OpenAI realtime / LiveKit / Twilio），realtime 连续流对抖动敏感。备选：① 切 `VOICE_MODE=pipeline`（STT→LLM→TTS，更抗抖、有文字、延迟略高）；② LiveKit/agent 就近区域；③ 生产在国内用就近媒体+合规模型。

**2) 名单命名厘清：常客名单 ≠ 门卫查询名单（不再统称"白名单"）**
- 「常客名单」= access list 的 whitelist（识别老客户/VIP，访客侧）；显示一律改为 **"常客"**（卡片/通知/后台/日志），不再叫"白名单"。
- 「门卫查询名单」= `GUARD_PHONES`（门卫自己的手机号，拨入转数据查询，电话侧）。
- 改动文件：`notify/common.py`、`web/server.py`、`session_logic.py`、`config.py`(注释)、`access.demo.json`、`tests/test_notify_channels.py`、`tests/test_session_logic.py`。源码内"白名单"字样已清零；单测 94 passed。

### B. 项目现状（2026-06-13）
- **部署**：全量在 Railway（项目 `jingyu-voice-agent`：服务 `web`=Dockerfile 容器内跑 agent+FastAPI；`Postgres-HN-9`=数据库）。**GitHub 自动部署**：push 分支 `claude/voice-agent-takehome-qzjbd2` 即自动构建上线。本机不再跑任何服务。
- **域名**：https://web-production-d105c.up.railway.app —`/voice` `/dashboard` `/admin` `/ask`（门卫口令 demo123；`/health`=200）。
- **电话**：任意手机拨 **+1 586 325 7270**（Twilio→LiveKit Cloud→云端 worker）。门卫查询名单含 +86 13500042868。
- **数据**：Postgres 持久；演示数据 21 访客 / 11 人 / 5 常客（`roster.demo.json`、`access.demo.json`、`scripts/seed_demo.py`，可复现）。
- **功能状态**：访客登记✓ · 门卫电话/网页数据查询✓（NL+结构化）· 常客回访（DB `recognize` 按车牌/手机；数据已备）✓ · 黑名单拦截✓ · 转人工电话回拨+DTMF(1放行/2拒绝)✓ · Telegram 推送✓（个人账号安全提醒不影响 bot 投递，已实测）。
- **已知坑 + 状态**：CRLF 致容器崩（已修：Dockerfile sed）· 密钥 BOM（已修：用 `KEY=VALUE` 参数而非 `--stdin`）· DATABASE_URL 用 Railway 引用（已修）· 吞字/噪音（本轮修，**待真机复测**）· guard_query 偶发工具入参 JSON 截断（历史记录，未复现）。

### C. 给远程会话的建议
- 把 `REALTIME_*` 收进 `config.py` 正式字段 + `.env.example`；加 `.gitattributes`：`*.sh text eol=lf`；`DEPLOY.md` 补两节：Windows 设 Railway 密钥用参数(BOM 坑)、名单命名（常客 vs 门卫查询）。

### D. 待办（明天收尾）
- 真机复测吞字/噪音是否消除；若残留 → 评估 pipeline 模式或就近区域。
- 决定仓库是否由 public 转 private。

---

## 2026-06-13 真机轮次：≤25s 流程收紧 + 网页语音归附件 + Telegram 按钮可点 + 微信通知就绪

1. **流程 ≤25 秒**：`prompts.py` 收紧——更短开场（一次问全 4 项）、新增「效率优先·硬性 25 秒」块、车牌+手机**一句话合并复述确认**（不再分两轮）。保留准确性兜底（号码复述、字母消歧、11 位校验），只是更快。说明：能把流程压短以瞄准 ≤25s，但实际时长还受访客话量 + 跨太平洋网络延迟影响，不能硬保证。
2. **网页版语音入园 → 归档为附件**：`/voice` `/qr` `/token` `/guard_call` 是"已实现但未选用"的备选方案（最终选电话）。控制台头部本就没有 /voice 入口，故无需删 UI；新增 `APPENDIX_web_voice.md` 归档说明，路由保留可演示。
3. **Telegram 放行按钮可点**：根因是 `telegram.button_safe_url()` 只在 host=localhost 时不放按钮；上云后 `PUBLIC_BASE_URL` 是 https 域名 → 按钮带上、手机可点（本地不能点的问题随上云消失）。已发带按钮测试卡复验。
4. **微信通知已就绪（待切换）**：`notify/wecom.py` 早已实现，且与 Telegram **完全同形式**（企业微信 markdown 卡片 + `[✅ 确认放行](confirm_url)` 链接，点击进 in-app 浏览器命中 /confirm 放行）。迁移 = 配置切换：`NOTIFY_CHANNEL=wecom` + `WECOM_WEBHOOK_URL=<企业微信群机器人 webhook>`。推荐先用**企业微信群机器人 webhook**（零审批、最快、镜像 Telegram）；若要"真按钮+服务端回调"再升级企业微信应用+模板卡片。需用户：在企业微信建群机器人→给我 webhook URL。

---

## 2026-06-13 真机轮次：微信通知方案（企业微信自建应用 API；PushPlus 备选）

**背景**：要把通知从 Telegram 迁到微信（国内不用 Telegram）。`notify/wecom.py`(企业微信群机器人 webhook)早已就绪、与 Telegram 同形式，但**群机器人必须先有普通群**；用户的企业是**单人企业，建不了普通群**（"发起群聊"无其他成员可选、Done 灰置），全员群又不支持加群机器人 → webhook 路线被堵。

**决定（用户选定）：企业微信「自建应用」API**（NOTIFY_CHANNEL=wecom_app）——不用建群，直接发给应用可见范围内的成员、收在企业微信 App。
- 新增 `notify/wecom_app.py`：`gettoken(corpid,secret)`(带缓存) → `message/send` 发 **textcard**（touser=@all，整卡可点 → confirm_url，按钮"放行"），与 Telegram/微信webhook **同形式**；另有 markdown `send_text` 用于转人工告警。
- `config.py` 新增 `wecom_corp_id` / `wecom_agent_id` / `wecom_app_secret`；`notify/dispatch.py` 接入 `wecom_app` 渠道（card + alert）。单测 94 passed。
- **待用户提供**（从 work.weixin.qq.com 管理后台取）：企业ID corpid、自建应用 AgentId、应用 Secret → 我设 Railway 环境变量 `NOTIFY_CHANNEL=wecom_app` + 三值 → 重部署 → 发测试卡验证。应用「可见范围」需含本人。

**备选（用户要求记录，present 时可提）：PushPlus → 个人微信**。关注一个公众号拿 token，加个小通道即可把通知发到**个人微信**（不是企业微信）。优点最省事、收在个人微信；缺点格式略简（标题+内容+放行链接，无富卡片）。**未实现，作为备选/演示话术保留。**

---

## 2026-06-13 真机轮次：企业微信通知打通（群机器人 webhook）+ 两条死路记录

**最终采用：企业微信「群机器人」webhook（NOTIFY_CHANNEL=wecom）= 已打通上线。**
- 关键坑：这版企业微信把"群机器人"放在 **群设置 → 「消息推送」→「添加自定义消息推送」** 下（用 Webhook 地址推到群聊），**没有叫"群机器人"**——找了很多回合才认出来。
- 全员群不支持；需先建**普通多人群**（单人企业建不了，用户邀请了微信同事进群后可建）。
- 拿到 webhook `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...` → 直接 POST 测试卡 **errcode=0 ok**（群里收到 markdown 卡片 + `[✅ 确认放行]` 链接，点开命中 /confirm 放行）。
- Railway 已切 `NOTIFY_CHANNEL=wecom` + `WECOM_WEBHOOK_URL`（存 Railway，不入库）→ 重部署 SUCCESS、health 200。放行/转人工告警现进企业微信群。webhook **无 IP 限制**，Railway 直接能发。

**死路 1（记录）：企业微信「自建应用」API（wecom_app.py）在 Railway 不可行。**
- `message/send` 报 **errcode 60020 "not allow to access from your ip"** —— 自建应用要求调用方 IP 在应用「可信IP」白名单；Railway 出口 IP 动态、无法固定 → 不可用。代码 `notify/wecom_app.py` 保留，仅当有固定出口 IP 时可用。

**备选（已实现，未启用）：PushPlus → 个人微信（NOTIFY_CHANNEL=pushplus）。**
- `notify/pushplus.py`：POST pushplus.plus/send（html 模板，标题+信息+`✅ 确认放行`链接）。无 IP 限制、不用建群/认证、收在**个人微信**。present 时可作"也能发个人微信"的备选。需 `PUSHPLUS_TOKEN`。

**现在通知渠道矩阵**：telegram ✅(已验证) / wecom 群机器人 webhook ✅(已启用) / wecom_app 自建应用(代码在,Railway 受可信IP限制) / pushplus 个人微信(代码在,备选)。dispatch 支持逗号多渠道并发。

---

## 2026-06-13 真机轮次：仓库交付完善（任何人 clone 即可完整体验）

目标：任何人打开 repo 都能下载并体验所有功能。仓库文档本就齐全（DOCS.md 索引 + README + 各专题），本轮补齐"我新增内容"的缺口，让 `.env.example` 开箱即用：
- `.env.example`：① 新增 realtime 抗噪音/防吞字调参（REALTIME_ALLOW_INTERRUPT/NOISE_REDUCTION/VAD_THRESHOLD/SILENCE_MS）；② 通知渠道补 wecom（群机器人 webhook，含"消息推送→添加自定义消息推送"取法）/ wecom_app（自建应用，附可信IP限制提醒）/ pushplus（个人微信）；③ ROSTER_PATH/ACCESS_LIST_PATH 默认指向开箱即用的 `roster.demo.json` / `access.demo.json`。
- `README.md`：NOTIFY_CHANNEL 行补全所有渠道；新增"演示数据一键写入"（`python scripts/seed_demo.py` → 21 访客/5 常客，试 /ask 查询 + 回访 + 黑白名单）与"全云端常驻部署见 DEPLOY.md"。
- 新人路径：clone → `pip install -r requirements.txt` → `cp .env.example .env`（填 OPENAI_API_KEY）→ `pytest`(94) → `python scripts/seed_demo.py` → 起 LiveKit/web/agent → 体验登记/回访/查询/黑白名单/通知；或直接 `scripts/run_sim.sh` 离线文本体验对话逻辑。

---

## 2026-06-14 轮次：README 一页化 + 详细 GUIDE.md + 默认分支迁到 main

**1) 文档（提交 `local: 1047a14`）**：README 砍到一页（保留架构图 + 5 分钟部署 + 核心 env 表，符合题目"一页以内"要求），细节移到新建的 `GUIDE.md`（自包含操作手册：本地/Windows/云端部署、环境变量全表、电话、通知、演示数据、测试、排错）；`DOCS.md` 索引收录 GUIDE.md。94 单测全绿。

**2) 默认分支 dev → main 收束（本轮）**：用户在 GitHub 手动把默认分支切成 `main`（fine-grained PAT 无 administration 权限，API 改不了 → 手动 Settings→Branches）。随后把"所有关联处"配套更新到 main：
- **Railway 部署源分支**：`railway service source connect --repo WeijieCao77/jingyu-task --branch main --service web` → 确认 `branch: main`（以后 push 到 main 自动部署）。
- **本地 git**：切到 `main` 跟踪 origin/main；`git remote set-head origin main` 修正 origin/HEAD。
- **文档引用**：DEPLOY.md（部署分支）、SETUP_GUIDE.md（4 处 git pull/分支说明）、SESSION_HANDOFF.md、ITERATION_SUMMARY.md（分支/PR 表）里"当前指令/状态"的旧分支名 `claude/voice-agent-takehome-qzjbd2` → 改为 `main`；ledger 表保留一句"原 dev 分支=claude/...、PR #1"作历史注脚。**历史迭代日志（本文件旧条目）不改写**，保留原貌。
- 旧分支 `claude/voice-agent-takehome-qzjbd2` 本地/远端仍在（与 main 同 commit），是否删除待用户定。

> 给远程会话：mainline 现在是 `main`，在 main 上工作、push 即自动部署。旧的 `claude/...` 分支若确认无用可删（先确认 Railway 已不再引用）。

---

## 2026-06-14 🔴 P0：realtime 电话接通后"完全没声音"——allow_interruptions=False 非法组合崩 job（与版本无关）

**症状**：用户拨 +1 586 325 7270 **全程无声**。一度以为 worker 没上线，实则 worker 在线且接到来电（日志有 `received job request` / `room="call_+1857...""` / `voice_mode=realtime` / `prefilled visitor phone from SIP caller id`），但 `session.start()` 当场抛错崩 job：
```
agent.py:466  await session.start(agent=agent, room=ctx.room)
ValueError: the RealtimeModel uses a server-side turn detection, allow_interruptions
  cannot be False, disable turn_detection in the RealtimeModel and use VAD on the
  AgentSession instead
reason="job crashed"
```

**真·根因（第二轮才查清）**：**不是版本问题**。RealtimeModel 用 server-side turn_detection 时，livekit-agents **强制要求** `AgentSession(allow_interruptions=True)`；给 False 直接抛 ValueError 崩 job——**这条校验在 1.5.17 和 1.6.0 里都有**（行号 194 vs 211）。病根是之前"默认禁打断防吞字"那次改动在 `agent.py` 给 realtime 的 `AgentSession` 设了 `allow_interruptions=False`，与 `build_realtime` 的 server_vad 撞车成非法组合。**那次改动从没真机打过电话验证**（笔记一直写"待真机复测"），所以这通从一开始就崩。

**走过的弯路（订正）**：第一轮**误判为 1.6.0 回归**，把 livekit 全家桶钉到 `==1.5.17`（commit `3a69efa`）。结果钉回 1.5.17 后**同样的错照崩**——证明与版本无关。1.5.17 的 pin **保留**（钉精确版本本身是好习惯、防未来意外升级），但它**不是**本 bug 的修复。

**真·修复（agent.py）**：realtime 的 `AgentSession` 改成 `allow_interruptions=True`（server_vad 下唯一合法值）。**防吞字改由模型层负责**——`build_realtime` 里 `TurnDetection(interrupt_response=False)`（默认）让 OpenAI 服务端不因回声/噪音打断 AI 自己的回复，正是我们要的效果。`REALTIME_ALLOW_INTERRUPT=1` 把 interrupt_response 打开恢复 barge-in。两层语义归一到 interrupt_response 这一个旋钮。

**教训/给远程**：① realtime + server_vad 时 **AgentSession.allow_interruptions 必须 True**，"禁打断"只能在模型层用 interrupt_response；② 任何 voice 配置改动**必须真机打一通电话验证**——光 `pytest`/探测客户端/`/health`/worker `registered` 都不够，job 是**接通才跑** session.start 才会触发这条校验；③ livekit 全家桶已钉 `==1.5.17`，别松回 `~=1.5`。

---

## 2026-06-14 功能轮次：门卫控制台合一 + 卡片三动作 + 通话等门卫出结果再挂 + 多门卫人工介入

按用户反馈一次做了四块（前端 + 通知 + 通话生命周期 + 配置）：

**1) 门卫网页合并成一个标签页（`web/server.py` `_CONSOLE_HTML`）**：原来分散的 4 个界面（门卫控制台 / 对话查询 / 筛选查询 / 常客名单）合成**一页 3 标签**——📂 数据库（控制台+筛选合并：筛选+统计+时段图+访客表带放行按钮+实时来电/转人工提醒）/ 💬 对话查询 / 🏆 常客名单。`/dashboard /ask /admin /` 都返回这一页（按路径选中标签）。顺带修了 **dashboard 静默空白 bug**：数据接口 401 时自动跳 `/login`，不再给空表。旧 `_DASHBOARD/_ASK/_ADMIN_HTML` 暂留作备份（已无引用，待清理）。

**2) 企业微信卡片三动作（`notify/wecom.py`）**：原来只有「✅确认放行」，加上「❌拒绝放行」「📞人工介入」。群机器人 webhook 卡片只能放**可点链接**（原生回调按钮需自建应用+可信IP，Railway 用不了），所以三个都是同 token、不同路径的链接（`/confirm` `/reject` `/takeover`）。

**3) 通话"等门卫出结果再挂"（`agent.py`）**：原来登记完 + 静默 N 秒就挂（FR-4）。改成**登记完不挂、保持通话**等门卫放行/拒绝；web 端放行→`{"type":"approved"}`、拒绝→新增 `{"type":"rejected"}` 数据消息 → AI 播报「已放行请进」/「抱歉未能放行」→ 播完静默 N 秒再挂。看门狗判据从 `reg.completed` 改成 `decided[0]`；门卫一直不处理则 `MAX_CALL_SEC`(默认180s)兜底。新增 `repo.mark_rejected` + `_notify_room_rejected`。

**4) 多门卫人工介入（`config.py` + `/takeover` 页）**：webhook 卡片对所有人是同一条、认不出谁点的，所以「人工介入」链接打开一个小页面，**列出每个门卫的拨号按钮**（当班的点自己那个 → 外呼对应号码进通话）+「电脑麦克风介入」按钮。配置 `TAKEOVER_GUARDS=名称:号码,...`；留空回退到单个 `GUARD_DIAL_NUMBER`。`sip_out.dial_guard(number=)` 本就支持指定号码。当前按用户要求只放一个号 `+18572091945`（靠回退，无需设 TAKEOVER_GUARDS）。

**验证**：94 单测全绿；`build_markdown` 含三链接；`parse_takeover_guards` 回退/多门卫都对；`/reject` `/takeover` TestClient 冒烟（坏 token=链接无效、错号码=不在名单、拒绝→status=rejected、介入页列出门卫）；`_CONSOLE_HTML` 整段 JS 过 node 语法检查。⏳ 真机端到端（卡片点拒绝/人工介入、通话等结果）待用户实拨复测。

### 真机实拨反馈（同日，两处）
- **转人工不能自动外呼门卫**：原 `_on_escalate` 一触发就 `dial_guard` 直接打门卫手机——用户反馈应**先群通知、门卫点"接入"后再打**。已改：`_on_escalate` 去掉自动外呼，群通知带 `/takeover?room=...&reason=...` 链接；门卫点开→选接听方式（拨我手机/浏览器介入），点了才外呼。`/takeover` 增加 `?room=`（转人工时还没访客 token，用房间号定位）入口，与卡片 `?token=` 共用同一页。
- **字母核对别用英文**：原 prompt 用"Dog 的 D / Boy 的 B"等英文单词消歧——国内很多访客听不懂。已改 `prompts.py`【核对确认】：改用**中文拼音联想**（北京的 B、东北的 D、朋友的 P、天津的 T、广州的 G、长城的 C…，E 用"鹅"、V 用"胜利手势"、U 用"马蹄形"），并主动用中文词反问。prompt 内已无任何英文消歧词。⏳ 待真机复测念字母效果。

---

## 2026-06-17 🔴 P0：realtime 电话「自说自话」——AI 没等访客回答就接自己的回声

**症状（用户真机反馈）**：realtime 模式下 AI 会"自说自话"——开场白说完，还没等访客开口，AI 自己又接着说话。

**怎么定位的（无声/回声探测，不用真机）**：写了两个程序化探测客户端连进 LiveKit Cloud（自动派单→云端 worker 入房），捕获 agent 音轨、按 RMS 数"说话段(burst)"：
- `probe_selftalk.py`（**不发任何音频**）：agent 只出 **1 段**（开场白 ~8s）后安静。→ 证明**不是**自发的二次回复 / 双重 generate_reply（排除怀疑方向①③）。
- `probe_echo.py`（**把 agent 自己的声音衰减 0.45 回灌**当"听筒回声"）：agent 出 **15 段**、每 ~2s 一段的反馈循环。→ **复现**，且证明是**输入触发**的。

**真·根因**：电话听筒把 AI 自己的声音回灌进线路；OpenAI **服务端 VAD** 把这段回声当成"访客在说话"，回声一停就判定"该访客说完了"→ `create_response=True` 自动对着回声生成回复 → AI 接自己的话。病根是 realtime 默认用 OpenAI 服务端 turn detection：此时 livekit 强制 `allow_interruptions=True`（给 False 会 ValueError 崩 job，见 06-14 条），于是**框架无法在 AI 说话时丢弃回声**（丢弃只在 `allow_interruptions=False` 的不可打断语音上做）。

**修复（两层，`providers.py` + `agent.py`）**：
1. **关掉服务端 VAD，改用本地 silero VAD 判轮次**（`REALTIME_SERVER_VAD=0` 默认）。`build_realtime` 给 RealtimeModel 传 `turn_detection=None`（实测序列化为 `turn_detection: null`，真关掉服务端 VAD；不是省略=保留默认）。AgentSession 加 `vad=build_vad`、`allow_interruptions=realtime_allow_interrupt()`（默认 False，现在**合法**了）。这样 AI 说话时框架丢弃入站音频（`discard_audio_if_uninterruptible`），回声进不去；访客轮次照常：本地 VAD 判完 → `commit_audio + generate_reply` → 回复。**单这层 15→3 段**。
2. **回声尾巴护栏（echo-settle）**：只关服务端 VAD 还残留——AI 说完后回声**尾巴**还会再飘 ~1 个往返才到，本地 VAD 把尾巴当访客轮次。`agent.py` 监听 `agent_state_changed`：AI 一开口就静音麦克风，回到 listening 后再等 `REALTIME_ECHO_SETTLE_MS`(默认 **1000ms**) 才重新听，让尾巴散掉。跨太平洋往返 ~0.4–0.5s，600ms 边界擦枪还漏 1 段，**1000ms 清零**。人工介入时置 `ears_locked` 让门卫接管麦克风、护栏不再自动开麦。仅在 realtime + 本地VAD + 不允许打断时启用。

**验证（部署后探测，job crashed 全程 0）**：echo 探测 **15→1 段**（0.45 重复两次 + 0.6 更狠都只剩开场白）；silent 探测 1 段开场白不崩；**speech 探测**（用 OpenAI TTS 合成"车牌沪A12345找蓝色鲸鱼送货"回灌）agent **正常回复**（clip 后 2.7s 起、~5.5s）——证明护栏没把 AI 弄聋。Railway 日志 job crashed / Traceback / ValueError / ERROR 全 0。94 单测全绿。

**给远程/教训**：① realtime 电话回声自说自话的根因是**服务端 VAD + 无法丢回声**，解法是**本地 VAD（allow_interruptions=False 才能丢回声）+ 说完后 settle 静默**；② 探测要能**回灌 agent 自己的音频**才能复现电话回声类 bug（纯静默探测复现不了）——`capture_frame` 是协程要 `await`（踩过）；③ 服务端 VAD 想保留可设 `REALTIME_SERVER_VAD=1`（仅在有真回声消除时安全）；④ `REALTIME_VAD_THRESHOLD/SILENCE_MS` 现在只在服务端 VAD 模式生效。探测脚本：`%TEMP%\probe_selftalk.py` / `probe_echo.py` / `probe_speech.py`。

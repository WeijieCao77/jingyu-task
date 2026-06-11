# 📱 在外面用手机测试 / 操作家里电脑的本地 Claude Code（Tailscale 方案）

目标：电脑常开放家里，你在外面用手机就能 ①**测试电脑里跑的语音 app**（说话/后台/转人工）②**驱动电脑上的本地 Claude Code**（发指令）。不用 cowork、不开放公网端口、数据不出你的设备。

原理：**Tailscale**（免费私有组网）让手机和电脑像在同一个局域网，手机直接访问电脑的 `8080`(网页) 和 `7880`(LiveKit)；再用手机 SSH 进电脑的 **tmux** 常驻会话操作 Claude Code。

---

## 第一部分：你亲手做的（账号 + 手机，机器没法替你做）

### 1. 注册并安装 Tailscale
1. 手机应用商店搜 **Tailscale**，安装 → 用 Google/邮箱注册登录（免费个人版够用）。
2. 登录后手机上会显示已连接。**记住你用的是哪个账号**——电脑要用同一个账号。

### 2. 电脑端授权（本地 Claude Code 会发起，你点一下）
- 本地 CC 在电脑装好 Tailscale 后会运行 `tailscale up`，终端会打印一个**授权链接**。
- 你在电脑（或手机）浏览器打开那个链接 → 用**同一个账号**登录授权 → 电脑就加入了你的私有网络。

### 3. 手机装一个 SSH App（用来给本地 Claude Code 打字）
- iOS：**Termius** 或 **Blink Shell**；安卓：**Termius** 或 **JuiceSSH**。
- 之后在 App 里新建连接，地址用本地 CC 给你的"电脑 Tailscale 地址"，用户名用你电脑的登录名。
  （首次连接可能要你电脑的开机密码或配 SSH key——App 里按提示操作即可。）

> 你要做的就这三件：手机装 Tailscale 并登录、电脑授权点一下、手机装个 SSH App。其余交给下面的 prompt。

---

## 第二部分：给本地 Claude Code 的 Prompt（复制整段喂给它）

```
我要在外面用手机访问你所在的这台电脑：①用手机测试这个语音 app（含语音通话）②用手机 SSH 进来操作你。
请用 Tailscale 帮我搭好，并把 LiveKit/web 改成手机也能连。需要我登录/授权的地方，把链接和步骤清楚地给我。

【1. 装 Tailscale（按本机系统）】
- 先判断系统（macOS/Linux/Windows）：
  · macOS: brew install tailscale  （或提示我装桌面版 App）
  · Linux: curl -fsSL https://tailscale.com/install.sh | sh
  · Windows: 提示我去 tailscale.com/download 装桌面版
- 运行 `tailscale up`，把它打印的**授权链接**给我，我用手机同款账号点开授权。
- 授权后运行 `tailscale ip -4`，把得到的地址（形如 100.x.x.x）记为 TS_IP，告诉我。

【2. 让语音 app 手机可连（关键：不能用 localhost）】
- 重启本地 LiveKit，绑定 Tailscale 地址，让手机的 WebRTC 能连：
  docker rm -f livekit-dev 2>/dev/null; \
  docker run -d --name livekit-dev -p 7880:7880 -p 7881:7881 -p 50000-50050:50000-50050/udp \
    livekit/livekit-server --dev --node-ip <TS_IP>
- 改 .env：
  LIVEKIT_URL=ws://<TS_IP>:7880
  PUBLIC_BASE_URL=http://<TS_IP>:8080
  （其余保持：OPENAI_API_KEY 已填、LLM_PROVIDER=openai、LLM_MODEL=gpt-4o-mini、
    LIVEKIT_API_KEY=devkey、LIVEKIT_API_SECRET=secret、NOTIFY_CHANNEL=none）
- 重启两个进程（web 已默认绑 0.0.0.0）：
  终端A: source .venv/bin/activate && PYTHONPATH=src python -m visitor_agent.web.server
  终端B: source .venv/bin/activate && PYTHONPATH=src python -m visitor_agent.agent dev

【3. 让我能用手机 SSH 进来驱动你（tmux 常驻）】
- 确认本机开了 SSH 服务（macOS: 系统设置→共享→远程登录打开；Linux: sudo systemctl enable --now ssh；
  Windows: 启用 OpenSSH Server）。需要我点开关的地方告诉我。
- 建一个常驻会话给我以后接管：
  tmux new -d -s cc       # 之后我会在这个会话里跑 claude
  并告诉我：在手机 SSH 连上后，运行  tmux attach -t cc  就能接管；想跑你（Claude Code）就在里面输入 claude。
- 把我的电脑登录用户名、和 `tailscale ip -4` 的地址一起给我，方便我在手机 SSH App 里配。

【4. 给我手机上能直接点的链接 + 自检】
- 访客端: http://<TS_IP>:8080/voice
- 后台:   http://<TS_IP>:8080/dashboard
- 常客:   http://<TS_IP>:8080/admin
- 自检：curl -s http://<TS_IP>:8080/health 应返回 ok；并确认 worker 已连上 LiveKit。
- 跑一遍单测确认没坏：PYTHONPATH=src python -m pytest -q

【输出要求】
- 把 Tailscale 授权链接、TS_IP、我的 SSH 用户名、四个手机链接、tmux 接管命令，整理成一小段清单给我。
- 任何需要我在系统设置里点开关的（远程登录/防火墙），明确告诉我点哪里。
- 报错先自查修复，改了什么说明。
```

---

## 第三部分：你在外面怎么用

**测 app（含语音）**：手机连着 Tailscale，浏览器开 `http://<TS_IP>:8080/voice` → 点接入、允许麦克风 → 直接对手机说话登记；另开 `…/dashboard` 看后台、点放行、测"📞主动介入"。

**驱动本地 Claude Code**：手机 SSH App 连 `<TS_IP>` → `tmux attach -t cc` → 里面就是常驻的 Claude Code，照常打字发指令、看输出；手机断网重连还在。

---

## 备选：只想测网页（不测语音），更省事
仓库自带 `./scripts/run_tunnel.sh`（cloudflared 免账号隧道）→ 给个公网 https，手机直接开 `/dashboard`、`/admin`。
**但隧道不转发实时音频**，"手机说话"连不上本地 LiveKit——测语音还是用 Tailscale，或把 LiveKit 换成 LiveKit Cloud。

## 安全提示
- Tailscale 是端到端加密的私有网络，只有你账号下的设备能互访，**不暴露到公网**。
- `--dev` 的 LiveKit 用的是公开默认密钥（devkey/secret），仅供你私有网络内的 demo；正式上线换正规凭据。
- 不用时可在手机 Tailscale App 里断开。

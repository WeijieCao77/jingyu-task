# 📱 在外面用手机：①操作本地 Claude Code（改文件/环境）②测语音 app

电脑常开放家里，你在外面用手机要做两件**不同**的事——分两条路，可同时用：

| 需求 | 推荐方案 | 要不要 Tailscale |
|---|---|---|
| **A. 跟本地 Claude Code 对话**，让它改本地文件、调本地环境、跑命令 | **VS Code Tunnel**（Windows 原生、手机浏览器、终端+文件编辑） | 不需要 |
| **B. 用手机测语音 app**（说话 / 后台 / 转人工） | **Tailscale**（让手机能连本地 LiveKit 的实时音频） | 需要 |

> 不用 cowork。两条路都不暴露公网端口、数据不出你的设备。

---

## 需求 A：手机操作本地 Claude Code —— VS Code Tunnel（推荐，Windows 友好）

效果：手机浏览器开 `vscode.dev` → 进入你电脑 → **集成终端里输入 `claude` 就是跟你本地的 Claude Code 对话**，它照常改你电脑上的文件、装东西、跑命令；左边文件树还能直接看/改文件。走微软 dev tunnel 中转，手机用蜂窝网也行。

### 你亲手做的（账号 + 授权，机器替不了）
1. 手机上准备一个 **GitHub 或 Microsoft 账号**（VS Code tunnel 用它认证）。
2. 电脑跑 `code tunnel` 时会打印一个**设备码 + 链接**（如 `https://github.com/login/device` + 一串码）→ 你在手机或电脑浏览器打开、登录、输入码授权。
3. 授权后它会给一个 `https://vscode.dev/tunnel/<你的电脑名>` 链接 → 手机浏览器收藏它，以后随时进。

### 给本地 Claude Code 的 Prompt（复制整段喂它）
```
我要在外面用手机浏览器操作你（本地 Claude Code）、改本机文件和环境。请用 VS Code Tunnel 搭好，
需要我登录/授权的地方把设备码和链接清楚地给我。

1. 确认/安装 VS Code（Windows）：
   - 已装就用现成的；没装：winget install Microsoft.VisualStudioCode
     （或让我去 code.visualstudio.com 下 ARM64 版安装）。
2. 在仓库根目录启动隧道（建一个常驻、断网重连还在的会话）：
   - 先确保能后台常驻：可在一个独立的 PowerShell 窗口里运行，别关它。
   - code tunnel --accept-server-license-terms --name my-pc
   - 把它打印的"设备码 + https://github.com/login/device（或 microsoft 的）"原样给我，我去授权。
3. 授权成功后，把它打印的 https://vscode.dev/tunnel/my-pc 链接给我。
4. 告诉我：手机浏览器打开那个链接后，怎么打开仓库文件夹、怎么开集成终端（Terminal→New Terminal）、
   在终端里输入 claude 就能跟你对话；并确认终端默认在仓库根目录、用的是我那个 x64 venv。
5. （可选）如果 code tunnel 容易断，帮我设成开机自启或包一层重启脚本，让它电脑常开时一直在。

输出：设备码+授权链接、最终的 vscode.dev/tunnel 链接、手机上"开终端→输 claude"的步骤、任何报错与处理。
```

### 在外面怎么用
手机浏览器开 `https://vscode.dev/tunnel/my-pc` → 打开仓库文件夹 → `Terminal → New Terminal` → 输入 `claude` → 就在跟你电脑上的本地 Claude Code 对话，它能改文件、装依赖、跑测试；你也能在编辑器里直接看/改文件。

### 备选（如果你更想用纯终端 / 已经搭了 Tailscale）
手机装 SSH App（Termius/Blink/JuiceSSH）→ SSH 到电脑（经 Tailscale 地址）→ `tmux attach -t cc` → 里面跑 `claude`。效果一样，只是终端而非浏览器。Windows 需先开 OpenSSH Server。

---

## 需求 B：手机测语音 app —— Tailscale（让手机能连本地 LiveKit）

测语音必须让手机能连到电脑的 LiveKit（实时音频），VS Code Tunnel 做不到这件事，用 **Tailscale**。

### 你亲手做的
1. 手机装 **Tailscale** + 注册登录（免费个人版）。
2. 电脑装好后本地 CC 会运行 `tailscale up` 并打印**授权链接** → 你用同账号点开授权。

### 给本地 Claude Code 的 Prompt
```
帮我用 Tailscale 让手机能连这台电脑测语音 app。需要我授权的地方把链接给我。
1. 装 Tailscale：Windows 去 tailscale.com/download 装桌面版（或 winget install tailscale）。
2. 运行 tailscale up，把授权链接给我；授权后 tailscale ip -4 取地址记为 TS_IP，告诉我。
3. 重启本地 LiveKit 绑定 TS_IP（手机 WebRTC 才连得上）：
   先停掉旧的，再用 LiveKit 二进制：livekit-server.exe --dev --node-ip <TS_IP>
   （如果用 Docker：docker run ... --dev --node-ip <TS_IP> 并映射 50000-50050/udp）
4. 改 .env：LIVEKIT_URL=ws://<TS_IP>:7880 ；PUBLIC_BASE_URL=http://<TS_IP>:8080 ；其余不变。
5. 重启 web + agent（web 已绑 0.0.0.0）。
6. 给我手机能点的链接：http://<TS_IP>:8080/voice、/dashboard、/admin。
输出：授权链接、TS_IP、三个手机链接、自检（/health 返回 ok、worker 已连 LiveKit）。
```

### 在外面怎么用
手机连着 Tailscale → 浏览器开 `http://<TS_IP>:8080/voice` 说话、`/dashboard` 看后台点放行/介入。

---

## 两条路一起用
- 手机浏览器一个标签开 `vscode.dev/tunnel/...`（指挥本地 Claude Code 改东西、跑命令）；
- 另一个标签开 `http://<TS_IP>:8080/voice`（亲自测语音）。
- 改完代码让本地 Claude Code 重启服务，你刷新语音页再测——闭环。

## 安全提示
- VS Code Tunnel 经微软认证中转，只有你登录的账号能进；Tailscale 是你账号下设备间的加密私网，都不暴露公网。
- `--dev` 的 LiveKit 用公开默认密钥（devkey/secret），仅供你私网 demo；上线换正规凭据。
- 不用时：`code tunnel` 那个窗口关掉即停；手机 Tailscale App 里断开即停。

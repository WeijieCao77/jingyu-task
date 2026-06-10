# 本地验证任务（喂给你本地的 Claude Code 跑）

这些 prompt 给**你本机的 Claude Code**（它能联网、能用你的 OpenAI/Anthropic 密钥、能起服务），
让它替你跑真实联调并把结果回报给我。**一条一条复制**给本地 CC 即可。跑完把它的输出贴回来，我据此定下一轮。

> 本远程环境出网受白名单限制，连不上 OpenAI/Twilio，也没有音频/电话，所以这部分必须在你本机做。

---

## 任务 1 · 环境自检 + 单测（最先跑，确认代码能装能跑）

```
这是一个 Python 仓库（语音访客登记 agent）。请：
1. 创建 venv，pip install -r requirements.txt。
2. 运行 `PYTHONPATH=src python -m pytest -q`，把完整输出贴出来。
3. 运行 `PYTHONPATH=src python -c "import visitor_agent.agent; print('agent import ok')"`。
4. 如有任何 import / 依赖错误，记录报错原文，尝试最小修复（不要改架构），并说明改了什么。
报告：测试通过数、失败项原文、你做的任何修复。
```

## 任务 2 · 对话质量（核心考核点：像不像真人）

```
仓库根目录有 .env.example。请复制为 .env，填入我的 ANTHROPIC_API_KEY 和 OPENAI_API_KEY
（密钥我会单独给你 / 已在环境变量里）。然后运行离线文本仿真，评估对话是否"像真人门卫"：

  ./scripts/run_sim.sh --scenario scenarios/songhuo.json
  ./scripts/run_sim.sh --scenario scenarios/mianshi.json

再自己设计 3 个刁钻场景各跑一次（用 --scenario 传 JSON，或交互式），例如：
  - 用户一句话给全 4 项信息（应一次记全、直接完成，不重复问）
  - 用户报错车牌又改口（应以最后一次为准）
  - 用户先问"怎么走"再给信息（应简短应付后拉回登记）

对每次对话打分并记录：①是否批量提问不机械 ②是否重复追问已知信息
③几轮完成 ④复述是否自然 ⑤槽位抽取是否正确（看 [record_visitor_info] 日志）。
把每个场景的完整对话 transcript + 你的评分贴出来。这是我最想看的反馈。
```

## 任务 3 · 微信推送 + 确认 + 抬杆 全链路（除电话）

```
按 SETUP_CHECKLIST.md 第 2、3 步：
1. 我已在企业微信建群机器人，webhook 已填入 .env 的 WECOM_WEBHOOK_URL（若没有，提醒我去拿）。
2. 起 web 服务：./scripts/run_web.sh ；另起隧道把 8080 映射公网，把 https 地址填回 PUBLIC_BASE_URL。
3. 运行：./scripts/run_sim.sh --scenario scenarios/songhuo.json --live
4. 确认：企业微信群是否收到访客卡片？卡片字段是否齐全？
5. 点卡片里的"✅确认放行"链接，确认浏览器显示"已放行 ✓"，且 web 终端打印 [GATE] 已发送抬杆指令。
报告：是否收到卡片（截图/文字）、确认链接是否工作、抬杆日志是否打印、任何报错。
```

## 任务 4 · 加分项（回访识别 + 门卫查询）

```
1. 回访识别：用同一车牌连续跑两次 live 仿真：
   ./scripts/run_sim.sh --scenario scenarios/songhuo.json --live   （跑两遍）
   第二遍开场，agent 是否识别为回访、直接确认而不是从头重问？贴 transcript。
2. 门卫查询 Agent（基于上面造的数据）：
   python -m visitor_agent.guard_query "今天一共多少访问车辆？"
   python -m visitor_agent.guard_query "什么时间段访问最多？"
   python -m visitor_agent.guard_query "蓝色鲸鱼今天来了几辆车？"
   贴出每个问题的回答，并判断数字是否正确。
报告：回访是否生效、查询回答是否准确。
```

## 任务 5（可选，耗时）· 真实电话 + 25 秒计时

```
按 SETUP_CHECKLIST.md 第 4、5、6 步接通 Twilio→LiveKit：
1. 起 ./scripts/run_agent.sh dev，确认 worker 已注册。
2. 配好 Twilio 号码 → LiveKit SIP（参考链接在 checklist 里）。
3. 用另一部手机拨打该号码，完整走一遍登记。
4. 用秒表测：从 Agent 开口 到 企业微信群消息出现 的耗时，是否 ≤ 25 秒。
报告：是否拨通、对话是否顺畅、是否被打断能正常处理、端到端耗时、任何卡点。
如果电话这步搞不定，记录卡在哪一步（Twilio 配置？SIP？），这本身也是答辩素材。
```

---

**回报格式**：每个任务给我 ①做了什么 ②实际输出/截图 ③通过与否 ④卡点。
我会据此判断哪里要改、要不要 A/B 其他架构（如换中文 TTS、试 TEN/Pipecat），并写下一轮夜间任务。

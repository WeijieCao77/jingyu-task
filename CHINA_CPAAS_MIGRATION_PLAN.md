# 国内 +86 号码接入方案（CPaaS 迁移 / 快速替换 Twilio）

> 目的：未来用**国内 CPaaS 的 +86 号码**替换/并存当前 Twilio 美国号，让国内来电算本地话费。
> 设计原则:**LiveKit 侧 + agent 代码完全不动**,换运营商=只换"号码+它的 SIP trunk 指向"。demo 暂不启用,此文档备好以便快速切换。
> 作者:local Claude(真机侧)。状态:**方案/未实施**。

## 0. 现状回顾(被替换的部分)
```
[Twilio 美国号 +1 586 325 7270]
  → Twilio Elastic SIP Trunk (TK901a1f6a…, 域 jingyu-task-qzjbd2.pstn.twilio.com)
  → Origination → sip:2zoatwoi9c4.sip.livekit.cloud;transport=tcp
  → LiveKit Cloud 入站 trunk ST_AEMYp6D4EFas(接受任意号码 / 0.0.0.0/0)
  → dispatch 规则 SDR_r6ADovwn3Wjt(每通来电独立房间)
  → 同一 agent:主叫在 GUARD_PHONES → 语音查询;否则 → 访客登记
转人工外呼:LiveKit 出站 trunk ST_mniczTfbtgFn → Twilio Termination → 回拨门卫
```

## 1. 替换后架构(下游全不变)
```
[+86 号(国内 CPaaS)] → [CPaaS SIP trunk:把该号的呼入 origination 到 ↓]
  → sip:2zoatwoi9c4.sip.livekit.cloud   ← 不变(LiveKit 入口)
  → LiveKit 入站 trunk(已接受任意号/IP)← 不变
  → dispatch 规则 ← 不变
  → 同一 agent ← 不变
```
**只有"运营商 + 号码 + 它的 SIP 指向"变了。** 这就是能"快速替换"的根本:LiveKit 入口 URI 固定、入站 trunk 接受任意来源、agent 与号码无关。

## 2. 候选 CPaaS(国内 +86)
| 提供商 | 备注 |
|---|---|
| 阿里云 语音服务(语音通知/呼叫中心 + 号码) | 生态全;需企业实名+资质+号码报备 |
| 腾讯云 语音/号码 | 同上 |
| 容联云 / 七陌 / 网易云信 | 传统 CPaaS,提供 SIP 中继 |
| 国际商(Telnyx/Plivo/Bandwidth) | +86 号库存极少且受限,一般不可行 |

> 选型关键:必须能提供 **SIP trunk + 可自定义 origination 到外部 SIP URI** 的能力(把呼入转发到 LiveKit)。不少国内 CPaaS 是"托管式呼叫中心",不一定开放裸 SIP 中继,选型时务必确认"支持 SIP 对接/外呼到自定义 SIP 地址"。

## 3. 合规/资质前提(国内硬门槛,需你方提供)
- 企业营业执照 + 实名认证;号码**报备**(主叫资质、反骚扰/反诈审核)。
- 语音机器人/外呼场景的合规说明(部分平台要审核话术)。
- **跨境数据**:呼叫音频送到**境外 LiveKit Cloud + OpenAI** 可能触及数据出境/PIPL 合规。生产建议二选一:
  - LiveKit 选**离中国近的区域**(东京/新加坡)降延迟;或
  - **自建 LiveKit**(部署在阿里云/腾讯云国内区)+ 走合规的大模型通道,实现音频不出境。
- 这些**由你方资质决定**,我无法代办。

## 4. 快速替换步骤(拿到号+trunk 后,技术侧约几小时)
1. CPaaS 侧:开通 +86 号 + SIP trunk;把该号的**呼入路由/origination 指向** `sip:2zoatwoi9c4.sip.livekit.cloud`(确认 transport=tcp/tls、编码 G.711/Opus)。
2. 若 CPaaS 要求鉴权:交换用户名/密码或 IP 白名单(LiveKit 出口 IP / 你的 CPaaS 出口 IP)。
3. LiveKit 入站:**当前 trunk 已 0.0.0.0/0 接受任意来源,无需改即可收**。(上线后建议收紧 allowed_addresses 到 CPaaS 的 IP 段 + 限定号码。)
4. (转人工外呼)新建一条 **LiveKit 出站 trunk** 指向 CPaaS 的 termination/外呼地址(地址+凭据),拿到新的 `ST_…`。
5. `.env` 改这几项即可(本机、不入库):
   - `GUARD_PHONES`= 门卫的 +86 号(逗号分隔多人)
   - `GUARD_DIAL_NUMBER`= 转人工回拨的门卫 +86 号
   - `SIP_OUTBOUND_TRUNK_ID`= 第 4 步新出站 trunk
   - `PUBLIC_BASE_URL`(若变)、必要时主叫显示号
6. 重启 agent worker;真机验证:+86 拨入 → 访客登记 / 门卫查询 / 转人工回拨 +86。
7. **可与 Twilio 并存**:两个号码同时 origination 到同一 LiveKit URI → 灰度/容灾,不必一次性下线 Twilio。

## 5. 代码侧改动量:≈ 0
- agent / providers / dispatch 规则 / LiveKit 入口 **都不用改**。
- 仅 `.env`(本机配置)调几个值 + 在 CPaaS/LiveKit 控制台建 trunk。
- 归一化已兼容 +86(`normalize_phone('+86…')` → 11 位),GUARD_PHONES 白名单与来电显示预填对 +86 都成立(见 LOCAL_RUN_ISSUES 当日记录)。

## 6. 质量/延迟注意
- 国内 PSTN 多为 G.711(a-law),确认 trunk 编码协商;
- realtime 对 RTT 敏感,LiveKit 选近中国区域(东京/新加坡)或国内自建;
- 国际长途主叫号可能被丢/改 → 影响白名单匹配与预填(走国内本地号后此问题消失)。

## 7. 时间线
- 资质审核 + 号码报备:数天~数周(国内监管,取决于平台)。
- 技术对接(有号+trunk 后):几小时(按第 4 节)。

## 8. 给远程会话的建议(配合此方案)
- 把 `REALTIME_*` / `GUARD_*` / `SIP_OUTBOUND_TRUNK_ID` 等都做成 `config.py` 正式字段 + `.env.example` 注释,换运营商时只动 .env。
- 入站 trunk 上线后支持"按号码+IP 收紧"的配置开关(安全)。
- 文档加一节"换运营商(Twilio↔国内CPaaS)只需改这几处",指向本文件。

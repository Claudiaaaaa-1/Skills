# JD-claim-audit

商品页面「主张—证据」一致性核验 Skill。面向电商商品上架前审核：把详情页里可验证的主张逐条抽出，与结构化属性、资质材料对齐，识别可解释的信息断裂，输出主张台账、证据台账与四态决策。

> 目录名按项目命名为 `JD-claim-audit`；Skill 标识遵循 kebab-case 规范，为 `sku-claim-audit`（见 `SKILL.md` frontmatter）。两者指向同一个 Skill。

## 背景

京东科技零售的商品信息「货不对板」治理场景。旧链路是「关键词过滤 + OCR + 词库命中 → 人工复核」，同时产生两类失效：

- **假阴性（漏放）**：参数造假不含高危词、图文不一致、资质编号格式正确但已注销。
- **假阳性（误伤）**：修辞被判欺诈、合法极限词「100%真蚕丝」被误拦、多 SKU 共用详情被一刀切。

两类失效同源于一处：判断停留在「词」，没有建立「主张 ↔ 证据」的关系。加长词库只会同时加剧两端问题。

## 它不回答什么

不回答「这个商品是不是假的」。真伪需要实物、检测、客诉等系统外真值，模型没有这些信号时只能猜。本 Skill 只回答一个更窄、更可靠的问题：

> 这一页里哪些表达构成可验证主张，每条主张最可信的证据是什么，证据与主张之间是否存在可解释的信息断裂，当前信息够不够支撑一个动作。

能力边界会随每次输出显式声明，避免上游把 `PASS` 误读为「已核实」。

## 核心设计

| 设计 | 说明 |
| --- | --- |
| 主张级，非页面级 | 一页多主张逐条判断，页面级状态取最严重者，但保留每条主张自己的状态 |
| 证据优先，禁止脑补 | 证据缺失标 `UNKNOWN` 转补证或人审，模型不替商家补结论 |
| 事实 / 解释 / 判断三成分立 | 出错时能分清是抽取错、对齐错还是裁定错 |
| 四态而非二态 | `PASS` / `BLOCK` / `REQUEST_EVIDENCE` / `HUMAN_REVIEW` |
| 规则用于召回，不用于终判 | 词库正是「100%真蚕丝」误拦的来源；仅硬红线允许短路 |
| 不确定性与确定性分离 | 模型只做语义抽取与断裂裁定，解析、对齐、路由全部由脚本确定性完成 |

三件套台账（主张 / 证据 / 断裂）不是产品品味，而是《广告法》第 8、11、38 条与平台审核义务在数据结构上的实现，详见 `references/compliance.md`。

## 目录结构

```
JD-claim-audit/
├── SKILL.md                 方法与能力边界、资源指针
├── references/
│   ├── claim-schema.md      主张 / 证据 / 断裂 / 决策字段契约
│   ├── gap-taxonomy.md      10 类断裂 → 四态映射、类目差异、失效案例库
│   └── compliance.md        法条 → 产品机制映射与可核查来源
├── scripts/
│   ├── parse_page.py        页面六类信息块解析
│   ├── align.py             证据对齐与断裂候选
│   ├── route.py             四态决策路由
│   ├── audit.py             端到端 CLI
│   └── validate_output.py   输出契约校验
├── assets/
│   ├── ledger_template.json 空白台账模板
│   └── examples/            四个可直接运行的 case
└── evals/
    ├── evals.json           测试用例与断言
    └── files/               评测权威副本
```

按 [anthropics/skills 的 skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) 规范组织：SKILL.md 只放流程与判断原则，详细 schema 放 `references/`，确定性逻辑放 `scripts/`，用例放 `evals/`，符合渐进式披露原则。

## 快速开始

无需 API key，仅依赖 Python 3.9+ 标准库。

```bash
python3 scripts/audit.py assets/examples/case-01-silk.json --out out.json
python3 scripts/validate_output.py out.json
```

输出示例（case-01）：

```
页面级状态  : BLOCK  (confidence 0.94)
主张级结果:
  [BLOCK] C01 100%真蚕丝   断裂: 数值冲突
  [PASS ] C02 柔软得像云朵 断裂: 无断裂
契约校验    : PASS
```

接真实页面时，先让模型按 `references/claim-schema.md` 把主张抽到 `claims` 字段，再交给 `audit.py`。

## 四态决策

| 状态 | 触发条件 | 对应失效治理 |
| --- | --- | --- |
| `PASS` | 主张已对齐或为纯表达 | 减少修辞误伤（假阳性） |
| `BLOCK` | 强事实直接否定主张 | 拦住真实冲突 |
| `REQUEST_EVIDENCE` | 证据缺失、功效无资质、条件泛化 | 把信息补全再判，不猜 |
| `HUMAN_REVIEW` | 资质过期、范围越界、证据未核验、图文不一致 | 兜住模型能力之外的部分 |

## 评测

四个用例覆盖全部四态，断言 29 条：

| 用例 | 目标状态 | 结果 |
| --- | --- | --- |
| `case-01-silk` 100%真蚕丝 vs 聚酯纤维 | `BLOCK` | 通过，且同页纯修辞仍 `PASS` |
| `case-02-cloud` 仅有「王者级触感」等修辞 | `PASS` | 通过，无误伤 |
| `case-03-hairloss`「防脱发」无资质 | `REQUEST_EVIDENCE` | 通过，不猜测 |
| `case-04-expired-cert` 编号正确但资质注销 | `HUMAN_REVIEW` | 通过，不因格式放行 |

**Skill 侧 29/29 断言通过（100%）；本地词库旧链路基线 25%，差值 +75%。** 基线失效模式：命中「王者级」误伤、「防脱发」漏放、注销资质放行；case-01 虽结果同为 `BLOCK`，但理由来自极限词命中且整页定性会连带拦下纯修辞，属于「对的结果、错的机制」。

评测产物（grading.json / benchmark.json / 官方静态 viewer）保存在本仓库外的本地工作区，不随 Skill 分发。

## 已知边界

- 未核验检测报告在官方库中的真伪；「编号格式正确但已注销」只能标为待核验并转人审。
- 未覆盖主图与 SKU 的图文关系，属 v2 范围；单模态文本 v1 会在 `boundary` 中显式声明。
- 未核验实物；真正的货不对板需售后、差评、抽检、职业打假工单回流做真值。
- 补证后的复审、次数上限、超时、防刷与幂等重跑属上游链路职责。

这些是当前信息条件下无法诚实跨越的边界，写进输出比让模型编一个结论更安全。

## 在 WorkBuddy 中安装

把本目录复制到 `~/.workbuddy/skills/` 即可。WorkBuddy 的 `skill_manage` 要求 frontmatter 含 `agent_created: true`，而 anthropics 官方 `quick_validate.py` 的允许字段里没有这一项——本仓库按官方规范保留纯净 frontmatter，装入 WorkBuddy 时补一行即可：

```yaml
---
name: sku-claim-audit
description: ...
compatibility: ...
agent_created: true
---
```

## 合规依据

- [《中华人民共和国广告法》全文（中国政府网）](https://www.gov.cn/guoqing/2021-10/29/content_5647620.htm)
- [市场监管总局第四批直播电商领域典型案例](https://www.samr.gov.cn/xw/zj/art/2025/art_cb90a1860b3d4cd18c87b1fa35baeeff.html)
- [市场监管总局 2025 年综合整治「内卷式」竞争十大案件](https://www.samr.gov.cn:9001/jzxts/sjdt/gzdt/art/2026/art_dce593ae14064458bb78897035625b5d.html)

条款到产品机制的逐条映射见 `references/compliance.md`。

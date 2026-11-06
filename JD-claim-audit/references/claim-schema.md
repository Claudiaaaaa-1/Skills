# 数据契约：主张、证据、断裂、决策

本文件是 `sku-claim-audit` 的唯一字段权威来源。模型抽取主张、脚本生成台账、上游解析输出，都以这里为准。

## 目录

1. [PageSnapshot 输入](#1-pagesnapshot-输入)
2. [Claim 主张](#2-claim-主张)
3. [Evidence 证据](#3-evidence-证据)
4. [Alignment 对齐结果](#4-alignment-对齐结果)
5. [Gap 断裂](#5-gap-断裂)
6. [Decision 决策](#6-decision-决策)
7. [Ledger 完整输出示例](#7-ledger-完整输出示例)
8. [枚举速查](#8-枚举速查)

---

## 1. PageSnapshot 输入

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `page.spu_id` | string | 标准产品单元 ID |
| `page.sku_id` | string | 具体销售单元 ID；属性组合唯一确定 |
| `page.category` | string | 类目路径，决定阈值与适用规则 |
| `page.blocks` | object | 六类信息块，见下 |
| `page.blocks.title` | string | 标题原文 |
| `page.blocks.main_image_ocr` | string \| null | 主图 OCR；v1 不处理，保留占位 |
| `page.blocks.attributes` | object | 结构化属性键值对 |
| `page.blocks.detail_text` | string | 详细描述文本 |
| `page.blocks.rules` | array | 类目规则或平台规则的条目 |
| `page.blocks.certificates` | array | 资质材料原始条目 |
| `claims` | array | 模型抽取的主张；离线 demo 中预置 |
| `evidence` | array | 证据条目；可为空，缺失本身是信号 |

信息块必须保留原文与出处，不做有损归并。SPU 与 SKU 分开存，因为多个 SKU 共用同一套详情图、检测报告只覆盖单一规格，是这类架构特有的风险来源。

## 2. Claim 主张

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `claim_id` | string | 是 | 页内唯一，如 `C01` |
| `text` | string | 是 | 主张原文片段 |
| `subject` | string | 是 | 主张对象，如「填充物材质」「防脱功效」 |
| `predicate` | string | 是 | 谓词，如「成分占比」「功效具备」 |
| `value` | string \| null | 否 | 可验证数值或结论；纯表达为 null |
| `type` | enum | 是 | `可验证事实` / `主观修辞` / `受约束承诺` |
| `scope` | object | 是 | `sku` / `batch` / `time` / `region`，未知填 null |
| `requires_evidence_types` | array | 是 | 期望的证据来源，如 `["属性表","检测报告"]`；纯表达为 `[]` |
| `evidence_refs` | array | 否 | 由对齐步骤填入 |

一条表达拆成多条主张是常态，不是异常。拆分的判据是「能否被独立证伪」，而不是句子边界。

## 3. Evidence 证据

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `evidence_id` | string | 是 | 页内唯一，如 `E01` |
| `subject` | string | 是 | 证据所指向的对象，用于与 `claim.subject` 对齐 |
| `source` | string | 是 | 来源信息块：`属性表` / `检测报告` / `认证书` / `授权书` / `报关单` / `官网链接` / `商家自填` |
| `content` | string | 是 | 证据原文 |
| `value` | string \| null | 否 | 可与主张数值比对的结构化值 |
| `level` | enum | 是 | `强事实` / `需交叉验证` / `纯表达` |
| `verified_against` | string | 是 | 核验到了什么，如「平台属性库」「仅格式，未查官方库」 |
| `status` | enum | 是 | `valid` / `expired` / `unverified` / `missing` |
| `scope` | object | 是 | 适用规格、批次、有效期、地区 |

`verified_against` 不能省略。只校验编号格式与真正查询官方数据库是两种完全不同的能力，把它们混写会让上游误以为资质已被核实。

## 4. Alignment 对齐结果

对齐步骤写入 `claim.alignment`：

| 字段 | 说明 |
| --- | --- |
| `matched` | 挂接到的 `evidence_id` 列表 |
| `status` | `matched` / `missing` / `scope_mismatch` / `not_required` |
| `checked_dims` | 实际检查过的维度：对象、时间、范围、数值、资质 |
| `note` | 对齐过程说明 |

`scope_mismatch` 指证据存在但只覆盖别的规格、别的批次或已过有效期，例如旧批次检测报告用于新配方商品。它不能算作 `matched`。

## 5. Gap 断裂

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `claim_id` | string | 关联主张 |
| `gap_type` | enum | 见 `gap-taxonomy.md` |
| `fact` | string | 事实陈述，不含判断 |
| `explanation` | string | 解释，说明为何构成断裂 |
| `judgement` | string | 判断，如「不可接受」 |
| `acceptable` | bool \| null | 是否有合理解释可接受 |
| `evidence_refs` | array | 相关证据 |

事实、解释、判断三成分立，便于定位错误发生在抽取、对齐还是裁定环节。

## 6. Decision 决策

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `state` | enum | 页面级：`PASS` / `BLOCK` / `REQUEST_EVIDENCE` / `HUMAN_REVIEW` |
| `claim_states` | object | 主张级状态映射，`{claim_id: state}` |
| `rule_first` | bool | 是否启用规则召回优先 |
| `confidence` | number | 0–1 |
| `reason` | string | 页面级结论理由 |
| `category` | string | 决策所用类目 |
| `hard_redline` | bool | 是否命中硬红线短路 |

页面级状态取主张级中最严重者，严重度顺序：`BLOCK` > `HUMAN_REVIEW` > `REQUEST_EVIDENCE` > `PASS`。**不得**用页面级状态覆盖 `claim_states`。

## 7. Ledger 完整输出示例

```json
{
  "page": {
    "spu_id": "SPU-10001",
    "sku_id": "SKU-10001-220x240",
    "category": "床品/蚕丝被",
    "blocks_present": ["title", "attributes", "detail_text", "certificates"]
  },
  "claims": [
    {
      "claim_id": "C01",
      "text": "100%真蚕丝",
      "subject": "填充物材质",
      "predicate": "成分占比",
      "value": "100%",
      "type": "可验证事实",
      "scope": {"sku": "SKU-10001-220x240", "batch": null, "time": null, "region": null},
      "requires_evidence_types": ["属性表", "检测报告"],
      "evidence_refs": ["E01"],
      "alignment": {
        "matched": ["E01"],
        "status": "matched",
        "checked_dims": ["对象", "范围", "数值", "资质"],
        "note": "属性表对象与主张对象一致，数值存在冲突"
      },
      "state": "BLOCK"
    },
    {
      "claim_id": "C02",
      "text": "柔软得像云朵",
      "subject": "触感",
      "predicate": "主观感受",
      "value": null,
      "type": "主观修辞",
      "scope": {"sku": null, "batch": null, "time": null, "region": null},
      "requires_evidence_types": [],
      "evidence_refs": [],
      "alignment": {"matched": [], "status": "not_required", "checked_dims": [], "note": "纯表达，无需证据"},
      "state": "PASS"
    }
  ],
  "evidence": [
    {
      "evidence_id": "E01",
      "subject": "填充物材质",
      "source": "属性表",
      "content": "填充物 = 聚酯纤维；蚕丝含量 = 0%",
      "value": "0%",
      "level": "强事实",
      "verified_against": "平台属性库",
      "status": "valid",
      "scope": {"sku": "SKU-10001-220x240", "batch": null, "valid_until": null, "region": null}
    }
  ],
  "gaps": [
    {
      "claim_id": "C01",
      "gap_type": "数值冲突",
      "fact": "主张写 100%，结构化属性写 0%（聚酯纤维）",
      "explanation": "同一对象的成分占比不可同时为 100% 与 0%",
      "judgement": "不可接受",
      "acceptable": false,
      "evidence_refs": ["E01"]
    }
  ],
  "decision": {
    "state": "BLOCK",
    "claim_states": {"C01": "BLOCK", "C02": "PASS"},
    "rule_first": true,
    "confidence": 0.94,
    "reason": "C01 存在不可接受的数值冲突",
    "category": "床品/蚕丝被",
    "hard_redline": false
  },
  "boundary": "未核验检测报告在官方库中的真伪；未覆盖主图与 SKU 的图文关系；未核验实物；单模态文本输入。"
}
```

## 8. 枚举速查

| 类别 | 取值 |
| --- | --- |
| `claim.type` | `可验证事实` / `主观修辞` / `受约束承诺` |
| `evidence.level` | `强事实` / `需交叉验证` / `纯表达` |
| `evidence.status` | `valid` / `expired` / `unverified` / `missing` |
| `alignment.status` | `matched` / `missing` / `scope_mismatch` / `not_required` |
| `gap.gap_type` | 见 `gap-taxonomy.md` |
| `decision.state` | `PASS` / `BLOCK` / `REQUEST_EVIDENCE` / `HUMAN_REVIEW` |

任何未列出的状态值都应被 `scripts/validate_output.py` 拒绝，避免上游静默兼容拼写错误。

# Recipe 用量提示：前端接入说明

本次仅新增后端返回字段，不修改页面、颜色、文案渲染或交互，不新增数据库迁移。
基于本地 Recipe required/optional 和替代食材修复分支；整套发布仍须执行此前的食材属性迁移。

## 接口

以下两个 GET 接口均返回相同结构的 `readiness`：

- `/api/v1/households/{household_id}/recipe-suggestions`：每个菜谱对象。
- `/api/v1/households/{household_id}/recipes/{recipe_id}`：菜谱详情对象。

原有食材计数、`quantity_status`、`is_quantity_sufficient`、排序和库存读写行为不变。
新字段只负责解释现有计算，不影响推荐可见性，不自动购买或扣减库存。
旧服务可能不返回此字段；前端遇到缺失/null时，不得自行认定足量。

## 总体状态

| `readiness.status` | 含义 | 默认英文提示 |
| --- | --- | --- |
| `READY` | 所有必需食材已有，且记录数量均足够 | Required ingredients and recorded quantities are sufficient for your household. |
| `MISSING_INGREDIENTS` | 至少一项必需食材未记录在库存 | Some required ingredients are not recorded in What You Have. |
| `INSUFFICIENT_QUANTITY` | 必需食材种类齐全，但至少一项有确定缺量 | All required ingredients are available, but some amounts are insufficient. Check quantities. |
| `CHECK_QUANTITIES` | 未能证明足量，例如库存数量未知、菜谱用量未审核或替代食材无法换算 | All required ingredients are available. Please confirm quantities. |

空的必需食材清单不会判为 READY，而返回 CHECK_QUANTITIES 和 `Recipe requirements need review.`。

两个独立布尔值：

- `all_required_ingredients_available`：必需食材种类是否齐全。
- `all_required_quantities_sufficient`：是否每一项都能证明记录数量足够。

可选调味料不阻止 READY。完整清单的 `7/7 ingredients` 包含 optional，与上述必需食材判断不是同一指标。
READY 仅依据当前记录量和家庭人数计算，不是对食材新鲜度、现实库存或烹饪安全的保证。

## 缺量与未知明细

`readiness.issues` 按菜谱顺序返回所有需要关注的必需食材，足量项和可选项不在其中。
缺食材、确定缺量、未知用量可以同时存在；即使总体状态优先显示缺食材/缺量，也不能丢掉其他明细。

| 字段 | 用途 |
| --- | --- |
| `recipe_food_id` | 原始菜谱食材位 ID，作为稳定关联键 |
| `food` | 显示用食材对象；发生替代时使用真实库存食材 ID/名称 |
| `status` | MISSING / INSUFFICIENT / UNKNOWN / NOT_TRACKED |
| `reason` | NOT_IN_PANTRY / KNOWN_SHORTFALL / AMOUNT_UNKNOWN / RECIPE_AMOUNT_UNREVIEWED / SUBSTITUTION_CONVERSION_UNAVAILABLE |
| `required_quantity_kg` | 当前家庭所需量，无法确定时 null |
| `available_quantity_kg` | 已知可比较的库存量；部分已知库存不等于全部库存 |
| `shortfall_quantity_kg` | 仅确定缺量才返回数字，否则 null；不得把 null 当成零 |
| `message_en` | 可直接使用或交由 UIUX 调整的默认英文提示 |

示例：鸡胸需要 500g、库存 100g，返回：

```json
{
  "status": "INSUFFICIENT_QUANTITY",
  "all_required_ingredients_available": true,
  "all_required_quantities_sufficient": false,
  "message_en": "All required ingredients are available, but some amounts are insufficient. Check quantities.",
  "issues": [{
    "recipe_food_id": "SF017",
    "food": {"canonical_food_id": "SF017", "name": "Chicken breast", "name_ms": null, "category": "protein"},
    "status": "INSUFFICIENT",
    "reason": "KNOWN_SHORTFALL",
    "required_quantity_kg": 0.5,
    "available_quantity_kg": 0.1,
    "shortfall_quantity_kg": 0.4,
    "message_en": "Chicken breast: need 400 g more."
  }]
}
```

英文缺量提示不足 1kg 用 g，否则用 kg；提示向上取整到 1g，避免正缺量显示为零。数值字段保留计算精度。

整鸡替代鸡腿、鲜椰浆替代盒装椰浆，没有审核过的换算时：

- 食材种类可以记为已有。
- issue 使用真实库存名称，但 `recipe_food_id` 保留原菜谱食材位。
- reason 为 SUBSTITUTION_CONVERSION_UNAVAILABLE。
- 三个数量字段均为 null，不套用原鸡腿/盒装椰浆的克数。
- 提示例如 `Whole chicken: confirm the usable amount for this recipe.`。

已有但未填数量返回 AMOUNT_UNKNOWN。菜谱本身未标定用量返回 RECIPE_AMOUNT_UNREVIEWED，不能误导用户为“只要填写库存即可解决”。

## 验证范围

纯逻辑回归覆盖：种类齐全但缺量、足量、未知、部分已知、未审核用量、可选项、混合问题、家庭人数缩放、替代换算边界、小数缺量和空清单。
模拟数据库的接口函数测试验证列表/详情字段一致及 JSON 序列化。
readiness 逻辑本身不写库、不调用模型、不改变前端展示。整合发布已在隔离 PostgreSQL 上验证食材迁移的升级、精确回退与再升级，并运行相关接口回归；UAT 迁移与部署记录见本次 PR。真机界面验收仍待 UIUX 同学接入提示后进行。

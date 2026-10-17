# 《AI-MA RAG 三层知识库数据 Schema 与元数据规范》

**版本**: v5.3（混合硬实时微内核架构 · As-Built 实装口径）
**状态**: 生产标准
**替代关系**: 本文件取代 v2.0-Modular 同名文档。所有字段名、取值范围与结构层级均取自
`knowledge_base/` 下的**实际 JSON 资产**（逐文件核对），并与 `core/kb_manager.py`、
`core/kb_service.py` 的读取逻辑一致。

---

## 0. 本版修订说明（v2.0 → v5.3）

| 项目 | v2.0 文档旧口径 | v5.3 实装口径 |
| --- | --- | --- |
| 通道取值范围 | `min_val` / `max_val` 两个字段 | **`range: [lo, hi]` 数组**（保存时自动归一化颠倒区间） |
| 通道枚举档位 | **完全缺失** | **`slots: [{v, label}]`**（图案盘/色盘/宏档位） |
| profile 顶层 | 含 `$schema` 字段 | **无 `$schema`**（实装文件里不存在该字段） |
| 场地拓扑 | 仅扁平的 `fixtures[]` | **`nodes[]` 四层拓扑**（解码器→接口→灯具→通道）为唯一事实源，`fixtures[]` 为派生的扁平视图 |
| 接口序号 | 无 | **`label` + `label_style`**（alpha / numeric / custom） |
| 共址处理 | 无 | **`allow_shared_address`**（默认 false，冲突拦截） |
| 预设内容 | 固定的 `suggested_channels` + `desc` | **`channel_values` 属性字典**（属性数量不设上限）；`suggested_channels`/`desc` 降级为**向后兼容派生字段** |
| 预设归属 | 无 | **`category_id` 强制必填**（缺失或引用不存在的分类，保存时硬拒绝） |
| 预设额外元数据 | 无 | `profile_ref` / `universal` / `transition_ms` / `summary` / `tags` / `color` / `icon` |
| 分类与属性分组 | 无 | **`_categories.json`** 与 **`_attribute_groups.json`** 两个注册表 |
| 通道类型字典 | 5 类 | **按属性分组归入 4 组**，实际在用 **24 种 type** |

---

## 1. 架构定位

知识库采用解耦的三层 JSON 架构，分别映射到现实世界中的：

1. **设备物模型物理定义** —— `profiles/`（灯具的物理通道分布与安全白名单）
2. **空间拓扑与数字孪生** —— `venues/`（安装位置、DMX 地址、四层节点拓扑、3D 坐标）
3. **艺术美学与业务预设** —— `presets/`（属性驱动的美学预设 + 分类注册表 + 属性分组注册表）

```text
knowledge_base/
├── profiles/
│   ├── martin_mac_aura_14ch.json
│   ├── beam_230w_16ch.json
│   └── gtdlighting_gtd450iibeam_13ch.json
├── venues/
│   └── venue_livehouse_hall_a.json
└── presets/
    ├── aesthetic_presets.json
    ├── _categories.json
    └── _attribute_groups.json
```

> 所有文件均可由第三方厂商独立提供，也可通过 `kb_workbench.py` 可视化生成。
> 文件均为 UTF-8 明文 JSON，**保持开放**，供 AI 助手与第三方开发工具直接读写。

---

## 2. 物理灯库规范（`knowledge_base/profiles/*.json`）

定义灯具的物理通道分布、功能类型、默认值、**合法取值范围**、**枚举档位**与安全白名单。

### 2.1 顶层结构

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `profile_id` | string | 是 | 唯一 ID，文件名通常与之一致（不含 `.json`） |
| `manufacturer` | string | 是 | 厂商 |
| `model` | string | 是 | 型号 |
| `channel_count` | int | 是 | 通道总数，应与 `channels` 长度一致 |
| `channels` | array | 是 | 通道定义数组 |

> **注意**：实装文件中**不存在** `$schema` 字段。早期文档示例里的
> `"$schema": "http://json-schema.org/draft-07/schema#"` 并非真实数据的一部分，不要照写。

### 2.2 通道结构

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `ch` | int | 是 | 通道序号，**从 1 开始** |
| `type` | string | 是 | 功能类型，见 §2.3 |
| `name` | string | 是 | 人类可读名称（中文为主） |
| `default` | int | 是 | 默认值，须落在 `range` 之内 |
| `is_safe` | bool | 是 | `false` 表示危险通道，系统强制拦截一切外部/AI 写入 |
| `range` | `[int, int]` | 是 | **合法取值范围 `[lo, hi]`**。保存时自动归一化颠倒区间（如 `[255,0]` → `[0,255]`）。**已取代早期的 `min_val`/`max_val` 两字段写法** |
| `slots` | `[{v, label}]` | 否 | **枚举档位**（图案盘、色盘、宏功能等离散值）。有档位的通道应提供，供预设编辑器以下拉方式选择 |

### 2.3 通道类型字典

RAG 与预设编辑器按 **4 个属性分组**组织通道类型。出厂四组定义在
`presets/_attribute_groups.json`，**完全可改**（可增删分组、调整归属）。

| 分组 ID | 分组名 | 包含的属性（type） |
| --- | --- | --- |
| `ag_intensity` | 亮度 | `dimmer` `intensity` `strobe` `shutter` `control` |
| `ag_color` | 颜色 | `red` `green` `blue` `white` `cct` `ctc` `cyan` `magenta` `yellow` `color_wheel` |
| `ag_beam` | 光束 | `zoom` `focus` `iris` `frost` `prism` `prism_rot` `prism_rotate` |
| `ag_gobo` | 图案 | `gobo` `gobo_rotate` `gobo2` `gobo2_rotate` |

此外，实装灯库中在用的还有：`pan` `pan_fine` `tilt` `tilt_fine` `speed`
（运动）、`macro` `effect` `reset` `lamp_control`（宏与系统）。

> **属性分组与预设的关系**：预设编辑器按分组呈现可调属性。
> **危险通道（`is_safe: false`）会被自动排除**，不出现在可选属性中。

### 2.4 完整示例

```json
{
  "profile_id": "martin_mac_aura_14ch",
  "manufacturer": "Martin",
  "model": "MAC Aura",
  "channel_count": 14,
  "channels": [
    {
      "ch": 1,
      "type": "shutter",
      "name": "频闪/快门",
      "default": 20,
      "is_safe": true,
      "range": [0, 255],
      "slots": [
        {"v": 0, "label": "关闭"},
        {"v": 64, "label": "慢速频闪"},
        {"v": 160, "label": "快速频闪"},
        {"v": 255, "label": "常开"}
      ]
    },
    {
      "ch": 2,
      "type": "dimmer",
      "name": "总调光",
      "default": 0,
      "is_safe": true,
      "range": [0, 255]
    },
    {
      "ch": 12,
      "type": "macro",
      "name": "内置宏",
      "default": 0,
      "is_safe": false,
      "range": [0, 255]
    }
  ]
}
```

> 上例中 `ch: 12` 的 `is_safe: false` 表示这是危险通道（设备复位/内置宏）。
> 系统在 `DmxMerger` 仲裁阶段会将该通道强制归零，日志记录 `ERR-MASK-TRIP`。
> 如需开放，必须在灯库中显式把 `is_safe` 改为 `true`——这是**唯一**的解锁方式。

---

## 3. 场地四层节点拓扑（`knowledge_base/venues/*.json`）

### 3.1 四层结构（v4.3 起的核心变更）

场地拓扑由**四层**构成，`nodes[]` 是**唯一事实源**：

```
解码器节点 (node)  →  接口/端口 (port)  →  灯具 (fixture)  →  通道 (channel，由 profile 定义)
```

保存时系统自动同步派生扁平的 `fixtures[]` 视图，使 `kb_manager`、RAG 检索与 DMX 引擎
**无需任何改动**即可继续工作。

### 3.2 顶层结构

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `venue_id` | string | 场地唯一 ID |
| `venue_name` | string | 场地名称 |
| `default_target_ip` | string | 默认 Art-Net 目标 IP |
| `nodes` | array | **四层拓扑根，唯一事实源** |
| `fixtures` | array | **派生**的扁平灯具列表（保存时自动生成，勿手工编辑） |

### 3.3 节点（node）结构

| 字段 | 说明 |
| --- | --- |
| `node_id` | 节点 ID，如 `node_1` |
| `name` | 节点名称，如「主解码器」 |
| `source` | 登记来源：`manual`（手动录入）/ 被动发现 / 主动扫描 |
| `ip` | 节点 IP |
| `protocol` | 协议，如 `artnet` |
| `groups` | 分组标签数组，如 `["舞台"]` |
| `discovery` | 发现态：`online` / `artpoll_reply` / `rtt_ms` / `first_seen` / `last_seen`（未探测时均为 `null`） |
| `offline_policy` | 掉线处置策略，见 §3.6 |
| `ports` | **接口（端口）数组** |

### 3.4 接口（port）结构

| 字段 | 说明 |
| --- | --- |
| `port_id` | 接口 ID，如 `p1` |
| `label` | 接口显示序号，如 `A` |
| `label_style` | 序号风格：`alpha`（A/B/C）· `numeric`（1/2/3）· `custom`（自定义） |
| `universe` | **该接口对应的 Universe**（灯具不单独存 universe，由所属接口决定） |
| `direction` | 方向，如 `out` |
| `fixtures` | 挂载在该接口下的灯具数组 |

> 界面显示形如「A口 · Universe 0」，便于在多解码器多接口现场快速定位灯具所属 Universe。

### 3.5 灯具（fixture）结构

| 字段 | 说明 |
| --- | --- |
| `id` | 灯具 ID，如 `fix_01` |
| `name` | 灯具名称，如「舞台左前一号面光」 |
| `profile_id` | 引用的灯库 `profile_id` |
| `address` | 起始 DMX 地址（1–512） |
| `tags` | 语义标签数组，供 RAG 检索（如 `["面光","舞台左侧","主唱面光"]`） |
| `allow_shared_address` | **是否允许共址**，默认 `false` |
| `position` | 3D 坐标 `{x, y, z}` |
| `semantic_desc` | 自然语言描述，供大模型理解灯具用途 |

### 3.6 掉线处置策略（`offline_policy`）

| 字段 | 取值 | 说明 |
| --- | --- | --- |
| `mode` | `threshold` / `ignore` / `manual` | 阈值触发 / 忽略 / 人工标记 |
| `liveness_source` | `artpoll`（**默认**）/ `ping` / `artdmx` | 存活判据来源 |
| `threshold_sec` | number | 判定掉线的阈值秒数 |
| `grace_period_sec` | number | 启动宽限期 |
| `severity` | `info` / `warning` / `critical` | 告警级别 |
| `actions` | array | 处置动作：`log`（强制）· `banner` · `toast` · `sound` · `fallback` |
| `auto_recover` | bool | 恢复后是否自动销警 |
| `alarm_when_never_seen` | bool | **默认 `false`**，见下方关键设计 |

> **⚠ 防告警脱敏（关键设计，勿改默认值）**
> 调音台在现场通常**只发不收**，解码器不会回传灯光数据。若把「从未收到回传」直接判为掉线，
> 每台正常设备都会在阈值后集体误报，运维人员很快对告警脱敏，反而彻底失去告警意义。因此：
> - 默认判据是 `artpoll` 主动探测，而非 `artdmx` 被动回传；
> - 该判据**从未产生过任何心跳**时，节点状态为 `unknown`（界面显示「未监测」），**不报警**；
>   只有显式设置 `alarm_when_never_seen: true` 才按掉线告警；
> - 心跳**按来源隔离**，非判据来源的心跳不会让节点"看起来在线"。

### 3.7 完整示例（节选）

```json
{
  "venue_id": "venue_livehouse_hall_a",
  "venue_name": "演艺大厅A现场",
  "default_target_ip": "192.168.3.2",
  "nodes": [
    {
      "node_id": "node_1",
      "name": "主解码器",
      "source": "manual",
      "ip": "192.168.3.2",
      "protocol": "artnet",
      "groups": ["舞台"],
      "discovery": {"online": null, "artpoll_reply": null, "rtt_ms": null,
                    "first_seen": null, "last_seen": null},
      "offline_policy": {
        "mode": "threshold",
        "liveness_source": "artpoll",
        "threshold_sec": 5,
        "grace_period_sec": 2,
        "severity": "warning",
        "actions": ["log", "banner", "toast"],
        "auto_recover": true,
        "alarm_when_never_seen": false
      },
      "ports": [
        {
          "port_id": "p1",
          "label": "A",
          "label_style": "alpha",
          "universe": 0,
          "direction": "out",
          "fixtures": [
            {
              "id": "fix_01",
              "name": "舞台左前一号面光",
              "profile_id": "martin_mac_aura_14ch",
              "address": 31,
              "tags": ["面光", "舞台左侧", "左前面光", "一号面光", "主唱面光"],
              "allow_shared_address": false,
              "position": {"x": -3.5, "y": 2.0, "z": 4.5},
              "semantic_desc": "位于舞台正前方左侧高处，主要负责主唱面部补光"
            }
          ]
        }
      ]
    }
  ]
}
```

### 3.8 地址冲突处理

| 情形 | 默认行为 | 显式放开后 |
| --- | --- | --- |
| 同 Universe 同地址 | 按 `danger` 冲突**拦截** | 勾选「允许共址」后降级为 `shared_address` 类型 + `severity: "warn"` 提示 |
| 跨 Universe 同地址 | **属正常情况，不误报** | — |

---

## 4. 艺术美学预设规范（`knowledge_base/presets/`）

### 4.1 属性驱动设计（v4.3 起的核心变更）

预设内容**不再是**固定的"颜色+动作+其他"三段式，而是开放的 **`channel_values` 属性字典**，
键为灯库通道的 `type`，**属性数量不设上限**——50 通道的灯具同样可完整描述。
动作类型同理不做枚举。

文件 `aesthetic_presets.json` 是一个**以预设 ID 为键的扁平字典**（无外层包装）。

### 4.2 预设条目字段

| 字段 | 类型 | 性质 | 说明 |
| --- | --- | --- | --- |
| `name` | string | **主字段** | 预设显示名 |
| `category_id` | string | **主字段·强制** | 所属分类。**缺失或引用不存在的分类，保存时硬拒绝** |
| `profile_ref` | string | 主字段 | 关联的灯库 `profile_id` |
| `universal` | bool | 主字段 | 是否适用于任意灯库 |
| `channel_values` | object | **主字段** | 属性字典，键为通道 `type`，值为数值 |
| `transition_ms` | int | 主字段 | 过渡时长（毫秒） |
| `summary` | string | 主字段 | 一句话摘要，供 RAG 检索 |
| `tags` | array | 主字段 | 检索标签 |
| `color` | string | 主字段 | 卡片主题色（如 `#ffbe50`） |
| `icon` | string | 主字段 | 图标标识（如 `fa-palette`） |
| `suggested_channels` | object | *派生* | **向后兼容字段**，读取时按需从 `channel_values` 派生 |
| `desc` | string | *派生* | **向后兼容字段**，由 `tags`/`summary` 派生 |
| `recommended_transition_ms` | int | *派生* | **向后兼容字段**，由 `transition_ms` 派生 |

> **【重要】派生字段的意义**：`suggested_channels` / `desc` / `recommended_transition_ms`
> 是为保持**既有 RAG 检索链路与旧调用方零改动**而在读取时派生的。
> **写入时以主字段为准**，不要只写派生字段——否则新版本读取时会得到空值。

### 4.3 预设示例

```json
{
  "sunset_gold": {
    "name": "暖阳金",
    "category_id": "cat_mv6vovv7",
    "profile_ref": "beam_230w_16ch",
    "universal": false,
    "channel_values": {"red": 255, "green": 190, "blue": 80, "white": 100},
    "transition_ms": 2000,
    "summary": "",
    "tags": ["自然", "日落", "温馨"],
    "color": "#ffbe50",
    "icon": "fa-palette",
    "suggested_channels": {"red": 255, "green": 190, "blue": 80, "white": 100},
    "desc": "自然、日落、温馨",
    "recommended_transition_ms": 2000
  }
}
```

### 4.4 分类注册表（`_categories.json`）

强制要求所有预设归属一个**用户自定义分类**。删除仍有预设引用的分类会被拒绝。

```json
{
  "categories": [
    {
      "id": "cat_mv6vovv7",
      "name": "综艺节目",
      "color": "#38bdf8",
      "order": 1,
      "icon": {"mode": "none", "builtin": "", "upload": "", "align": "inline"}
    }
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| `id` | 分类 ID |
| `name` | 分类名 |
| `color` | 主题色 |
| `order` | 排序权重 |
| `icon.mode` | 图标模式：`none`（纯文字，**默认**）· `builtin`（内置图标）· `upload`（自定义 SVG/PNG） |
| `icon.builtin` / `icon.upload` | 对应模式下的图标来源 |
| `icon.align` | 与文字的对齐方式，通过 CSS `mask` 渲染，随文字颜色变化、基线对齐、1em 大小 |

### 4.5 属性分组注册表（`_attribute_groups.json`）

```json
{
  "groups": [
    {"id": "ag_intensity", "name": "亮度", "color": "#38bdf8",
     "attrs": ["dimmer", "intensity", "strobe", "shutter", "control"]},
    {"id": "ag_color", "name": "颜色", "color": "#f43f5e",
     "attrs": ["red", "green", "blue", "white", "cct", "ctc",
               "cyan", "magenta", "yellow", "color_wheel"]},
    {"id": "ag_beam", "name": "光束", "color": "#38bdf8",
     "attrs": ["zoom", "focus", "iris", "frost", "prism", "prism_rot", "prism_rotate"]},
    {"id": "ag_gobo", "name": "图案", "color": "#38bdf8",
     "attrs": ["gobo", "gobo_rotate", "gobo2", "gobo2_rotate"]}
  ]
}
```

出厂四组（亮度/颜色/光束/图案）**预置但完全可改**——可增删分组、调整归属、改配色。

---

## 5. 校验与一致性规则速查

| 规则 | 触发时机 | 违反后果 |
| --- | --- | --- |
| `category_id` 必须存在且引用有效分类 | 保存预设（`save_preset` / `save_presets`） | **硬拒绝**（HTTP 400） |
| 不得删除仍被预设引用的分类 | 删除分类 | **硬拒绝** |
| `range` 颠倒时自动归一化 | 保存灯库 | 自动纠正为 `[lo, hi]` |
| `default` 应落在 `range` 内 | 保存灯库 | 建议修正（不硬拒） |
| 同 Universe 同地址 | 保存场地 | `danger` 冲突拦截；勾选共址后降级为 `warn` |
| 跨 Universe 同地址 | 保存场地 | **正常，不报错** |
| `is_safe: false` 的通道 | 仲裁阶段 | 强制归零 + `ERR-MASK-TRIP` |
| 灯库被场地引用时删除 | 删除灯库 | **硬拒绝** |
| `channel_count` 与 `channels` 长度 | 保存灯库 | 建议一致 |

---

## 6. 写入方须知（v5.3 特有）

1. **`fixtures[]` 是派生视图，不要手工写。** 修改灯具一律改 `nodes[].ports[].fixtures[]`，
   系统保存时会自动重新生成扁平视图。
2. **`universe` 存在接口层，不存在灯具层。** 灯具的 Universe 由所属 `port.universe` 决定。
3. **预设写入以主字段为准**（`channel_values` / `transition_ms`），
   派生字段（`suggested_channels` / `recommended_transition_ms` / `desc`）由系统生成。
4. **危险通道不出现在可选属性中**——预设编辑器按 `profile_attributes()` 输出可调属性全集，
   并自动排除 `is_safe: false` 的通道。
5. **知识库读写失败会记录 `ERR-KB-WRITE`**，请检查 `knowledge_base/` 目录权限与磁盘剩余空间。
6. **外部控台灯库导入失败会记录 `ERR-ADAPTER-IMPORT`**，常见原因是 2 类适配器插件未启用，
   或源文件（MA2 XML / GDTF）格式不受支持。

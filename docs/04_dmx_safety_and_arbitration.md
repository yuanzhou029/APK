# 《AI-MA DMX 物理安全掩码与多源仲裁策略标准》

**版本**: v5.3（混合硬实时微内核架构 · As-Built 实装口径）
**状态**: 生产标准 · 架构冻结
**替代关系**: 本文件取代 v2.0-Modular 同名文档。所有优先级常量、仲裁分支条件与安全熔断逻辑
均取自 `core/dmx_merger.py` 实装源码（113 行，逐行核对）。

---

## 0. 本版修订说明（v2.0 → v5.3）

| 项目 | v2.0 文档旧口径 | v5.3 实装口径 |
| --- | --- | --- |
| 优先级类名 | `SignalPriority` | **`PriorityLevel`** |
| 优先级成员名 | `PANIC` / `DESK_MANUAL` / `AI_SEQUENCE` / `AI_MACRO` | **`PANIC` / `MANUAL_DESK` / `AI_CUE` / `AI_MACRO`** |
| 数值 | 100 / 80 / 50 / 30 | 一致（100 / 80 / 50 / 30） |
| 仲裁语义 | 描述为"多源优先级裁决"，未说明是门控 | **门控式**：只有最高优先级的源参与合成，低优先级源**整体出局**（非逐通道比较） |
| 安全熔断旁路 | 未说明 | **`PANIC` 是唯一能写危险通道的级别**（`max_prio < PANIC` 才熔断） |
| 层级命名 | 用 `L1/L2/L3` 表示应用侧三层防御 | **与微内核的 `L1/L2/L3/L4` 槽位含义完全不同，必须区分**（见 §1.2） |
| 微内核分工 | 无（单进程） | Python 算仲裁 → 写共享内存 L4 → **Rust 微内核做最终四级槽位仲裁与物理输出** |
| 适用范围 | 未标注 | Python 侧 `DmxMerger` 固定 **4 个 Universe**（见 §7） |

---

## 1. 核心安全挑战

舞台演艺系统的控制失误可能导致不可逆后果：

1. **机械损伤**：误触发摇头灯 Reset，导致机械臂在运动中强制撞限位齿轮打滑。
2. **光源寿命劣化**：气体放电泡（HID）频繁开关导致灯泡炸裂。
3. **人身生理安全**：高频频闪（15–20Hz）可能诱发观众光敏性癫痫（Photosensitive Epilepsy）。
4. **控制权失控**：AI 自主跑宏时，现场主控调光师无法即时接管。

### 1.1 应用侧三层纵深防御（Defense in Depth）

这是**软件逻辑层**的防御，与下文的共享内存槽位无关：

```
[ 用户意图输入 ]
       │
       ▼
[ ① RAG 白名单注入 ] ── 大模型只被告知安全通道列表，危险通道被隐匿
       │
       ▼
[ ② 掩码过滤器 Mask Engine ] ── 强制熔断非法通道写入，夹紧取值边界
       │
       ▼
[ ③ 多源优先级仲裁器 DmxMerger ] ── 优先级门控 + HTP/LTP 确定性裁决
       │
       ▼
[ 写入共享内存 L4 槽位 ] ── 交给 Rust 硬实时微内核
```

### 1.2 ⚠ 命名冲突澄清（极易混淆，务必分清）

系统中存在**两套都用 L1/L2/L3/L4 命名**但含义完全不同的概念：

| 命名 | 所属层面 | 含义 |
| --- | --- | --- |
| **应用侧三层防御** | Python 软件逻辑 | ① RAG 白名单 → ② 掩码过滤 → ③ DmxMerger 仲裁（本文档 §1.1 用圆圈数字表示，**不用 L 编号**） |
| **共享内存槽位 L1/L2/L3/L4** | 微内核内存层级 | L1 安全层 · L2 设备基础层 · L3 创意层 · L4 台面层（见 §6） |

> **本文档约定**：应用侧三层一律写作「① / ② / ③」，`L1`~`L4` **专指共享内存槽位**。
> 早期文档把应用侧三层写成 L1/L2/L3，与槽位编号撞车，是排障时的常见误读来源。

---

## 2. 优先级体系（PriorityLevel · 实装常量）

```python
class PriorityLevel:
    PANIC       = 100   # 紧急安全 / 一键黑场 / 全场报警（最高级）
    MANUAL_DESK = 80    # 实体控制台 / 灯光师推杆接管
    AI_CUE      = 50    # AI 单场景或时序 Cue
    AI_MACRO    = 30    # AI 背景走马灯 / 呼吸动态宏（最低级）
```

| 常量 | 值 | 语义 | 典型来源 | 能否写危险通道 |
| --- | ---: | --- | --- | --- |
| `PANIC` | 100 | 紧急安全、一键黑场、全场报警 | `/api/lighting/panic` | **能**（唯一旁路，见 §4.2） |
| `MANUAL_DESK` | 80 | 实体控制台、灯光师推杆接管 | 外部控台 / 台面层 | 否 |
| `AI_CUE` | 50 | AI 单场景或时序 Cue | 场景直通、大模型点灯 | 否 |
| `AI_MACRO` | 30 | AI 背景特效宏 | 呼吸、走马灯等 3 类插件 | 否 |

> `submit_frame()` 的 `priority` 参数**默认值是 `AI_CUE`**。未显式指定优先级的调用方
> 会以 50 级参与竞争——这通常不是期望行为，调用时请显式传入。

---

## 3. 仲裁算法（`DmxMerger._recalculate_universe`）

### 3.1 算法全貌

每次 `submit_frame()` 或 `clear_source()` 都会触发**整帧重算**：

```
1. 若该 Universe 无任何活跃信号源 → 直接返回（保持上一帧输出，不清零）

2. max_prio = max(所有源.priority)                    ← 取出全场最高优先级

3. active_sources = [源 for 源 in 所有源 if 源.priority == max_prio]
                                                       ← 【门控】低优先级源整体出局

4. 逐通道 ch = 1..512：

   a) 安全熔断：若 ch 在危险黑名单 且 max_prio < PANIC(100)
        → out[ch] = 0        （强制归零，continue 到下一通道）

   b) HTP（最高值优先）：若 ch_type ∈ {dimmer, white}
        → out[ch] = max(active_sources[*].data[ch])

   c) LTP（最新值优先）：其余全部类型
        → out[ch] = data[ch] of max(active_sources, key=timestamp)
```

### 3.2 ⚠ 门控式优先级（最易误读的一点）

**这不是逐通道的优先级比较。** 只要存在一个 `PANIC` 源，所有 `MANUAL_DESK`、`AI_CUE`、
`AI_MACRO` 源就在**每一个通道上**被整体忽略——哪怕它们只写了 1 个通道、而 PANIC 源
有 500 个通道是 0。

这带来两个必须理解的后果：

- **好处**：安全优先级是绝对的、不可被"部分覆盖"的。PANIC 一按，全场立即完全服从。
- **代价**：控台推杆接管（80）期间，AI 宏（30）在所有通道上（包括推杆没碰的通道）全部停止输出。
  若期望"推杆只管它碰的通道、其余交给 AI"，当前实现**不满足**，需要改算法或改用同优先级源。

### 3.3 HTP / LTP 适用类型

| 算法 | 适用通道 `type` | 计算方式 | 设计理由 |
| --- | --- | --- | --- |
| **HTP**（Highest Takes Precedence） | `dimmer`、`white` | 取所有活跃源中的**最大值** | 光强是可叠加的物理量；多人同时调亮时取最大符合直觉 |
| **LTP**（Latest Takes Precedence） | **其余全部类型**（颜色、`pan/tilt`、`gobo`、`prism`、`shutter`、`macro` …） | 取**时间戳最新**的源的值 | 颜色/位置是"选择"而非"叠加"，最新指令覆盖旧指令 |

> **实现细节**：LTP 的时间戳在**每个通道上独立取最新源**，但由于 `active_sources`
> 已被优先级门控筛选，实际比较范围只在最高优先级源之间。

### 3.4 数据隔离

`submit_frame()` 会**严格克隆**输入帧（`bytearray(dmx_data_512[:512])`），
防止调用方在提交后继续修改同一 bytearray 而导致仲裁结果被外部污染。
不足 512 字节的输入会被补齐，超过 512 字节的会被截断。

---

## 4. 物理安全掩码（Safety Shield）

### 4.1 黑名单的建立

安全掩码的来源是**灯库 JSON 的 `is_safe` 字段**：

```python
merger.configure_fixture_channels(
    universe      = 0,
    start_address = 31,                      # 灯具起始地址
    channel_defs  = profile["channels"],     # 灯库通道定义
)
```

实现逻辑：对每个通道定义取 `ch`（1 基），计算绝对地址 `abs_ch = start_address + ch - 1`，
若 `1 <= abs_ch <= 512` 则登记其 `type`；若 `is_safe == False` 则加入该 Universe 的
**危险通道黑名单** `_blocked_channels`。

引擎在初始化时会调用 `_init_merger_rules()`，把**知识库中全部场地灯具**的
安全掩码一次性注册进仲裁器。

### 4.2 熔断条件与 PANIC 旁路

```python
if ch in blocked_channels[universe] and max_prio < PriorityLevel.PANIC:
    out_frame[ch - 1] = 0
    continue
```

**只有 `PANIC`（100）级别可以写入危险通道。** 这是刻意的设计——急停/复位通道必须
留一个最高特权的操作通道，否则现场无法执行"全部复位"这类必要的维护动作。

> **⚠ 安全评审要点**：这条旁路意味着**任何能以 PANIC 优先级提交帧的调用方，都能操作危险通道**。
> 新增调用方时请确认其权限来源可信（当前仅 `/api/lighting/panic` 走此路径，且需相应 RBAC 权限）。
> 危险通道被熔断时系统记录 `ERR-MASK-TRIP`，并在知识库中给出解锁指引
> （必须修改灯库把 `is_safe` 显式改为 `true`，这是唯一的解锁方式）。

---

## 5. 从仲裁到物理输出的完整链路

```
业务层调用方（场景 / 大模型 / 插件 / 台面）
        │  submit_frame(source, universe, frame, priority)
        ▼
┌──────────────────────────────────────────────┐
│ core/dmx_merger.py  DmxMerger                │
│  · 优先级门控（max_prio）                     │
│  · 安全熔断（is_safe=false → 0）              │
│  · 逐通道 HTP / LTP                           │
│  → get_final_frame(universe) → 512 字节安全帧 │
└───────────────────┬──────────────────────────┘
                    │  kernel_bridge.submit_layer("l4", u, frame, mask)
                    │  单帧耗时约 0.57µs，零拷贝写入
                    ▼
┌──────────────────────────────────────────────┐
│ Rust 硬实时微内核 aima-rt-daemon（44Hz）      │
│  · 读取 L1/L2/L3/L4 四个槽位                  │
│  · 最终四级仲裁：L1 > L4 > L3 > L2             │
│  · O(1) 安全钳位 safety_lut[64][512][256]     │
│  · sendmmsg() 批量推流 + 微突发整形             │
└───────────────────┬──────────────────────────┘
                    ▼
            物理网络输出（Art-Net 3/4 / sACN E1.31）
```

### 5.1 两层仲裁的分工（必须理解）

系统存在**两次仲裁**，职责不同、粒度不同：

| 层级 | 执行者 | 输入 | 仲裁对象 | 粒度 |
| --- | --- | --- | --- | --- |
| 第一层 | Python `DmxMerger` | 同一槽位内的多个业务信号源 | **业务来源之间**的优先级与 HTP/LTP | 通道级 |
| 第二层 | Rust 微内核 | 四个槽位（L1/L2/L3/L4） | **层级之间**的最终压制 | 通道级，帧内即时 |

第二层的规则是 `L1 > L4 > L3 > L2`：高优先级层一旦在某通道置位，立即在本帧内压制低优先级层。
这与 §2 的 `PriorityLevel` **不是同一套编号**——前者是"内存层级"，后者是"业务优先级"。

---

## 6. 共享内存槽位与权限边界

| 槽位 | 作用 | 写入方 | 对应业务优先级 |
| --- | --- | --- | --- |
| `aima_slot_l1` | **安全层**：急停、黑场、物理熔断 | Python 业务层 | `PANIC` |
| `aima_slot_l4` | **台面层**：控台接管、Crossfade 淡变 | Python 业务层 | `MANUAL_DESK` |
| `aima_slot_l3` | **创意层**：宏插件、特效、音频节拍 | 插件宿主 | `AI_MACRO` / `AI_CUE` |
| `aima_slot_l2` | **设备基础层**：静态预设、灯库底态 | Python 业务层 | 底态 |

> 3 类插件只被授予 `l3` 文件的写权限，即使被恶意构造也无法越界篡改 `l1` 安全层——
> 这是靠**操作系统文件权限**实现的物理边界，而非应用层约定。

---

## 7. 已知约束（务必知悉）

| 约束 | 说明 | 影响 |
| --- | --- | --- |
| **Python 侧仅 4 个 Universe** | `core/engine.py:37` 硬编码 `DmxMerger(universe_count=4)`，且无配置覆盖途径 | 超出 Universe 0–3 的灯具无法经 Python 仲裁路径输出。微内核 ABI 声明支持 **64** 个 Universe（`AIMA_MAX_UNIVERSES`），两侧容量不一致 |
| **`universe_count` 之外的提交被静默丢弃** | `submit_frame()` 开头 `if universe not in self._sources: return` | 传入越界 Universe 不会报错，只是无任何效果，排障时需注意 |
| **无源时保持上一帧** | `_recalculate_universe()` 在 `sources` 为空时直接返回 | 清空全部信号源**不会**导致输出归零；如需黑场请显式提交 PANIC 级别的全零帧 |
| **危险通道旁路仅 PANIC** | 见 §4.2 | 设计如此，但属安全评审重点 |

---

## 8. 测试覆盖

| 套件 | 覆盖的仲裁/安全断言 |
| --- | --- |
| `tests/verify_architecture.py` | 事件总线、**HTP/LTP 优先级仲裁**（控台 80 覆盖 AI 宏 30）、**物理安全掩码拦截**（危险复位通道强制归零）、业务侧 L4 提交链路、生命周期停机释放 |
| `tests/verify_takeover_learning.py` | 控台接管与学习链路（`DmxMerger(universe_count=2)`） |
| `tests/verify_node_alarm.py` | 掉线告警全链路（含安全回退归零策略的默认关闭校验） |

关键回归断言（`verify_architecture.py`）：

```python
# 控台推杆 (MANUAL_DESK=80) 必须压过 AI 宏 (AI_MACRO=30)
assert final_frame[31] == 200, f"优先级仲裁失败，期望 200，实际 {final_frame[31]}"

# 危险通道（Martin MAC Aura 第 13 通道）必须被强制归零
assert final_frame_after_risk[42] == 0, "安全熔断失效！危险通道未被拦截！"
```

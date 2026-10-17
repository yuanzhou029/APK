# 《AI-MA 开放式插件体系与二次开发 SDK 指南》

**版本**: SDK v3.0 · 平台 v5.3（混合硬实时微内核架构）
**状态**: 生产标准
**适用对象**: 第三方设备厂商、协议集成商、算法开发者、系统维护团队
**替代关系**: 本文件取代 v2.0-Modular 同名文档。文中所有类名、方法签名与校验规则均取自
`core/plugin_sdk.py` 实装源码（312 行，逐条核对），凡与本文件冲突之处以源码为准。

---

## 0. 本版修订说明（v2.0 → v3.0）

| 项目 | v2.0 文档旧口径 | 实装口径 |
| --- | --- | --- |
| 插件目录 | `plugins/{protocols,perception,macros,llm}` | `plugins/{system,adapters,community}` |
| 分层模型 | 无（只有 `PluginType` 功能分类） | **`PluginTier` 三层权限分级**（1/2/3 类） |
| `PluginType` 取值 | 4 种 | **6 种**（新增 `effect`、`adapter`） |
| 协议插件抽象方法 | `send_dmx(universe, dmx_data)` | **`send_universe(universe, dmx_data_512)`** |
| 宏插件抽象方法 | `render_frame(elapsed_ms, params, current_dmx)` | **`render(elapsed_ms, params, current_frame)`** |
| 感知插件抽象方法 | 文档未列 | **`get_status() -> Dict`** |
| 2 类适配插件 | **完全缺失** | `BaseAdapterPlugin`，抽象方法 `supported_extensions()` + `convert_to_profile()` |
| 合规校验器 | 未提及 | `PluginValidator`（6 项硬校验，见第 5 节） |
| 示例代码 | 放在 `plugins/macros/`，用 `render_frame` | 必须放 `plugins/community/`，用 `render` |

---

## 1. 插件设计理念

在 AI-MA 中，除微内核的实时推流骨架外，**所有业务逻辑均以插件形式存在**。第三方团队无需修改核心代码，只需基于 `core.plugin_sdk` 实现特定抽象接口，放入 `plugins/` 下**对应层级**的子目录，系统启动时即自动装载。

两个必须理解的设计：

1. **层级由目录决定，不由代码声明。** 插件放在哪个子目录，就是哪一类。这保证了权限边界是**物理的**，而不是靠约定。
2. **用户界面隐匿 ≠ 运维不可见。** 1/2 类插件不出现在插件市场，但会完整打印在启动日志的「插件生态装载总览」中，也可通过 admin 专属的 `/api/plugins/diagnostics` 查询。

---

## 2. 插件三层分级（PluginTier）

三层不是"分类标签"，而是**由物理目录决定的权限边界**。

| 层级 | 常量 | 物理目录 | 基类 | 用户可见 | 可否卸载 | 失效后果 |
| --- | --- | --- | --- | --- | --- | --- |
| **1 类·系统级** | `PluginTier.SYSTEM` = 1 | `plugins/system/` | `BaseSystemPlugin` 及其子类 | 否 | 禁止 | **致命**：无任何物理输出 |
| **2 类·适配级** | `PluginTier.ADAPTER` = 2 | `plugins/adapters/` | `BaseAdapterPlugin` | 否 | 禁止 | **严重**：无法导入控台灯库资产 |
| **3 类·表现创意** | `PluginTier.CREATIVE` = 3 | `plugins/community/` | `BaseCreativePlugin` 及其子类 | 是 | 支持热卸载 | **轻微**：仅该插件特效失效 |

现有 9 个插件的目录归属：

```text
plugins/
├── system/
│   ├── artnet_plugin.py
│   ├── sacn_plugin.py
│   ├── qwen_plugin.py
│   └── system_log_ai_repair_plugin.py
├── adapters/
│   └── ma_fixture_adapter.py
└── community/
    ├── breathing_plugin.py
    ├── marquee_plugin.py
    ├── perception_audio_beat_sim.py
    └── show_evolution_learning_plugin.py
```

> **放错层级的后果**：3 类插件若放进 `system/`，它将从用户界面与插件市场中消失（无法被安装、卸载或配置）；
> 1/2 类插件若放进 `community/`，它将暴露给用户并被允许卸载，可能导致系统丧失核心能力。
> 层级由 `PluginHost` 按目录判定，**不读取插件自报的 tier 值**。

---

## 3. 插件基类与生命周期

### 3.1 类继承体系

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List

# —— 层级基类（决定 tier，插件作者通常不直接继承它们）——
BasePlugin(ABC)                 # 默认 tier = CREATIVE(3)
├── BaseSystemPlugin            # tier = SYSTEM(1)
│   ├── BaseProtocolPlugin      # 输出协议驱动
│   └── BaseLLMPlugin           # 大模型与认知中枢
├── BaseAdapterPlugin           # tier = ADAPTER(2)
└── BaseCreativePlugin          # tier = CREATIVE(3)
    ├── BaseMacroPlugin         # 动态特效宏
    └── BasePerceptionPlugin    # 外部感知输入
```

### 3.2 PluginType 受支持类型（共 6 种，取自源码）

```python
class PluginType:
    PROTOCOL   = "protocol"     # 输出协议 (Art-Net, sACN, OSC, Telnet, Modbus)
    PERCEPTION = "perception"   # 外部感知 (音频分析, BPM 提取, 摄像头追踪, 传感器)
    MACRO      = "macro"        # 动态特效宏引擎 (走马灯, 呼吸, 矩阵彩虹)
    LLM        = "llm"          # 大语言模型与决策器适配器 (Qwen, DeepSeek, Claude)
    EFFECT     = "effect"       # 静态/动态灯光特效发生器
    ADAPTER    = "adapter"      # 外部资产与控台格式转换器 (MA2 XML, GDTF, Titan)
```

> `get_info()["type"]` 必须取自上述 6 个值之一，否则 `PluginValidator` 直接判不合规。

### 3.3 BasePlugin 抽象方法（所有插件必须实现）

```python
class BasePlugin(ABC):
    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """返回插件元信息，六字段缺一不可："""
        # {
        #     "id": "unique_plugin_id",   # 必须匹配 ^[a-z0-9_]{3,40}$
        #     "name": "插件人类可读名称",
        #     "version": "1.0.0",          # 建议语义化版本
        #     "author": "开发团队或作者",
        #     "type": PluginType.MACRO,    # 必须属于 6 种受支持类型
        #     "description": "功能简介"
        # }

    @abstractmethod
    def on_init(self, context: "CoreContext") -> bool:
        """装载时调用，注入内核上下文。返回 True 表示成功，False 将被安全跳过。"""

    @abstractmethod
    def on_enable(self) -> None:
        """激活运行时调用。可在此启动后台线程或网络监听。"""

    @abstractmethod
    def on_disable(self) -> None:
        """停用或系统关闭时调用。**必须在此释放全部套接字、线程与内存。**"""
```

> **警告**：`on_destroy()` **不是**抽象方法，无需实现（早期文档有误）。
> 遗漏上述任一方法，Python 会将该类判定为抽象类，插件将在**类发现阶段被拒收**，
> 且会出现在启动日志的失败明细中。

### 3.4 各层级专属抽象方法

| 基类 | 层级 | 必须额外实现 |
| --- | --- | --- |
| `BaseProtocolPlugin` | 1 类 | `send_universe(self, universe: int, dmx_data_512: bytearray) -> bool` |
| `BaseLLMPlugin` | 1 类 | `chat_completion(self, messages: List[Dict[str,str]], temperature: float = 0.2) -> str` |
| `BaseAdapterPlugin` | 2 类 | `supported_extensions(self) -> List[str]` · `convert_to_profile(self, file_bytes: bytes, filename: str) -> Dict[str, Any]` |
| `BaseMacroPlugin` | 3 类 | `render(self, elapsed_ms: float, params: Dict[str, Any], current_frame: bytearray) -> bytearray` |
| `BasePerceptionPlugin` | 3 类 | `get_status(self) -> Dict[str, Any]` |

> `BaseProtocolPlugin.broadcast_sync()` **已提供默认实现且不是抽象方法**，仅在需要同步帧时覆盖。

---

## 4. 内核上下文 CoreContext

插件通过 `on_init(context)` 拿到内核暴露的安全上下文：

| 属性 / 方法 | 说明 |
| --- | --- |
| `context.event_bus` | 线程安全事件总线，用于跨插件广播/订阅 |
| `context.dmx_merger` | 四级优先级仲裁器 |
| `context.kb` | 知识库管理器（**注意属性名是 `kb`，不是 `kb_manager`**） |
| `context.config` | 插件自身配置字典 |
| `context.services` | 系统注册的共享服务字典 |
| `context.get_service(name)` | 按名取服务，返回 `None` 表示不存在 |

`services` 字典是 v3.0 新增的向后兼容扩展点。例如取大模型服务：

```python
llm = context.get_service("llm")
```

> **常见陷阱**：早期模板中出现的 `self.context.backup_mgr` **不存在**。
> 需要备份能力时，请通过 `services` 字典获取，或在插件内自行实例化 `BackupManager`。

### 4.1 BasePlugin 提供的开箱即用能力

以下方法**已有默认实现，无需重写**（按需覆盖）：

| 方法 | 用途 |
| --- | --- |
| `is_enabled` (property) | 插件当前启停状态 |
| `tier` (property) | 插件所属层级 |
| `get_config_schema() -> Dict` | 声明可配置项，供 UI 动态渲染配置表单 |
| `get_config() -> Dict` | 取当前配置 |
| `update_config(new_config) -> bool` | 运行时热更新参数 |
| `set_enabled(enabled) -> bool` | 启停开关 |
| `get_ai_prompts() -> Dict[str, str]` | **专有大模型提示词隔离字典**，见下 |
| `call_ai_service(prompt_key, user_content, temperature) -> str` | 安全调用大模型中枢，自动注入本插件专属 System Prompt |
| `get_ui_extensions() -> List[Dict]` | 向宿主界面注册扩展插槽与通用自包含视窗（2 类/3 类可用） |

`get_ai_prompts()` 实现的是**提示词隔离机制**：每个插件持有独立的专业角色上下文，互不污染。

```python
def get_ai_prompts(self) -> Dict[str, str]:
    return {
        "default_system": "你是一个专职于舞台频闪特效的灯光工程师……",
        "extract_schema": "只输出 JSON，字段为 period_ms / duty_cycle……",
    }
```

### 4.2 自包含 UI 视窗机制（Generic Plugin View Host 规范）

在 AI-MA v5.3+ 中，**插件带界面无需修改宿主系统的任何 HTML/JS/CSS 文件**，实现了单文件即插即用（Self-Contained Ingress）：

- **静默插件**：保持默认 `get_ui_extensions()` 返回 `[]`，纯净运行；
- **独立看板 / 可视化监控插件**：仅需在 `get_ui_extensions()` 中声明目标插槽（如 `slot: "topbar_actions"`）并挂载 `view_html`。

```python
def get_ui_extensions(self) -> List[Dict[str, Any]]:
    return [
        {
            "slot": "topbar_actions",            # 挂载位置: 顶栏操作区
            "id": "btnMyMonitor",                # 按钮唯一 ID
            "label": "我的看板",                 # 按钮文本
            "icon": "fa-chart-network",          # 图标
            "modal_title": "实时协议看板",       # 弹窗标题
            "modal_size": "lg",                  # 弹窗宽度: sm / md / lg
            "view_html": self.render_html()      # 自包含的 HTML + JS 模板
        }
    ]
```

**宿主运行机制**：
1. 宿主前端自动扫描已启用的插件扩展，在对应插槽（如顶栏）动态生成按钮；
2. 用户点击按钮时呼出通用视窗容器（`modalGenericPluginHost`），安全载入 `view_html`；
3. 视图内内置脚本可通过 `pluginContext`（提供 `pluginId`, `api`, `setTimer` 等注入函数）与后端实时通信；
4. 插件卸载或移出目录后，界面按钮与视窗自动移除，宿主**零代码残留**。

---

## 5. PluginValidator 合规校验规则

`PluginValidator.validate_plugin_instance(plugin)` 是插件进入系统的最后一道门。以下为**逐条取自源码**的校验逻辑：

| # | 校验项 | 判定 | 失败后果 |
| --- | --- | --- | --- |
| 1 | 必须继承 `BasePlugin` | 硬性 | 直接返回 `valid: False` |
| 2 | `get_info()` 必须返回 `dict` | 硬性 | 拒绝装载 |
| 3 | 六字段齐全且非空：`id` `name` `version` `author` `type` `description` | 硬性 | 拒绝装载 |
| 4 | `id` 匹配 `^[a-z0-9_]{3,40}$`（3–40 位小写字母/数字/下划线） | 硬性 | 拒绝装载 |
| 5 | `type` 属于 6 种受支持类型 | 硬性 | 拒绝装载 |
| 6 | `version` 匹配 `^\d+\.\d+(\.\d+)?` | **仅警告** | 仍装载，但记录警告 |
| 7 | `get_config_schema()` 返回 `dict`，且每项含 `type` 与 `label` | 硬性 | 拒绝装载 |
| 8 | 存在可调用的 `on_init` / `on_enable` / `on_disable` | 硬性 | 拒绝装载 |

> **注意**：校验规则**不要求** `get_config_schema()` 的每项带 `default` 或 `description`
> ——早期文档把它们写成必需项是错的。缺 `default` 不影响装载，但会降低界面可用性，**强烈建议提供**。

返回值结构：

```python
{
    "valid": True/False,
    "errors": ["...", "..."],       # 硬性错误
    "warnings": ["..."],            # 警告（不阻断装载）
    "plugin_info": {...}            # 仅 valid=True 时返回插件元信息
}
```

---

## 6. 最小插件开发范例

以下是一个完整的、**符合上述全部契约**的 3 类宏插件。文件放至 `plugins/community/` 下：

```python
# -*- coding: utf-8 -*-
"""极简频闪脉冲宏插件 —— 3 类·表现创意"""

from core.plugin_sdk import BaseMacroPlugin, PluginType


class StrobeMacroPlugin(BaseMacroPlugin):
    """基于毫秒时钟的周期性频闪发生器。

    继承 BaseMacroPlugin 即自动获得 tier = PluginTier.CREATIVE(3)，
    因此必须放在 plugins/community/ 目录下。
    """

    def get_info(self):
        return {
            "id": "macro_strobe_pulse",          # 小写 + 下划线，3-40 位
            "name": "频闪脉冲特效宏",
            "version": "1.0.0",
            "author": "OpenLightingLab",
            "type": PluginType.MACRO,            # 必须取自 6 种受支持类型
            "description": "基于毫秒时钟的周期性频闪发生器",
        }

    def get_config_schema(self):
        # 每项必须含 type 与 label；default 强烈建议提供
        return {
            "period_ms": {"type": "number", "label": "频闪周期(ms)", "default": 100},
            "duty_cycle": {"type": "number", "label": "占空比(0-1)", "default": 0.5},
            "dimmer_channels": {"type": "list", "label": "作用通道列表", "default": [1]},
        }

    def on_init(self, context):
        self.context = context
        return True

    def on_enable(self):
        pass

    def on_disable(self):
        # 若启用了后台线程或套接字，必须在此释放
        pass

    def render(self, elapsed_ms, params, current_frame):
        """注意方法名是 render，不是 render_frame。"""
        period_ms = params.get("period_ms", 100)
        duty = params.get("duty_cycle", 0.5)
        phase = (elapsed_ms % period_ms) / period_ms
        dimmer_val = 255 if phase < duty else 0

        for ch in params.get("dimmer_channels", []):
            if 1 <= ch <= 512:
                current_frame[ch - 1] = dimmer_val   # DMX 通道从 1 开始，数组从 0 开始
        return current_frame
```

> **可选项（按需加）**：如该插件需要调用大模型，额外实现 `get_ai_prompts()` 并调用
> `self.call_ai_service("default_system", 用户内容)`；如需向界面注册按钮，
> 实现 `get_ui_extensions()`。

### 6.1 开发自检清单

提交前请逐条核对：

1. 文件是否放进了**正确层级**的目录（`system/` / `adapters/` / `community/`）？
2. 所选基类的**全部抽象方法**是否都已实现（对照 3.3 与 3.4）？
3. `get_info()` 六字段是否齐全非空，`id` 是否纯小写且长度 3–40？
4. `type` 是否取自 6 种受支持值？
5. `get_config_schema()` 每项是否都有 `type` 与 `label`？
6. `on_disable()` 是否释放了全部套接字、线程与内存？
7. 是否需要界面：若需要独立看板，是否在 `get_ui_extensions()` 中声明了自包含 `view_html`（遵循 4.2 节单文件自包含规范，严禁侵入修改宿主 `index.html`）？
8. 启动后是否在日志的「插件生态装载总览」中看到本插件？
   格式为「插件 id  中文名称  [启停状态]」。**没看到就是被拒收了**，
   请在总览末尾的失败明细中按 id 查找原因，或调用 `GET /api/plugins/diagnostics`。

### 6.2 插件开发的五条红线

1. **禁止直接写共享内存。** 插件只能通过宿主接口操作 L3 槽位，
   任何试图直接 `mmap /dev/shm/aima_slot_l1` 的行为会因文件权限被内核拒绝。
2. **禁止在 `render()` / `send_universe()` 中做阻塞 IO。** 这些回调在调度路径上，
   阻塞会直接拖慢整帧。
3. **禁止抛出宿主无法捕获的异常。** 虽有熔断隔离，但会在总览中登记为失败项。
4. **禁止绕过 PluginValidator。** id 格式、六字段、schema 每项的 `type`/`label` 都是硬性要求。
5. **大模型插件禁止自主循环触发。** 必须经阈值门禁或人工点击触发，
   输出以「待审草稿」形式呈现，由人工二次确认后落地。

---

## 7. 附：常见错误对照表

| 症状 | 根因 | 修法 |
| --- | --- | --- |
| 启动日志里看不到自己的插件 | 类仍是抽象类（漏实现抽象方法） | 对照 3.3 / 3.4 补齐；注意 `render` 不是 `render_frame`、`send_universe` 不是 `send_dmx` |
| 插件装上了但界面里找不到 | 放进了 `system/` 或 `adapters/` | 移动至 `plugins/community/` |
| 校验报「缺少必要字段」 | `get_info()` 六字段不全或值为空串 | 逐字段核对 |
| 校验报「ID 不合规」 | 含大写字母、长度不足 3 或超过 40 | 改为纯小写 + 数字 + 下划线，3–40 位 |
| 校验报「类型不在受支持列表」 | `type` 写成了自定义字符串 | 用 `PluginType` 的 6 个取值之一 |
| 配置表单渲染不出来 | schema 某项缺 `type` 或 `label` | 补齐这两项（`default` 建议但不强制） |
| 运行时 `AttributeError: backup_mgr` | 沿用了旧模板的 `context.backup_mgr` | 改用 `context.get_service("backup")` 或自行实例化 |
| 卸载后线程仍在跑 | `on_disable()` 未 join 后台线程 | 线程设 `daemon=True` 并在 `on_disable()` 中 `join(timeout=1.0)` |

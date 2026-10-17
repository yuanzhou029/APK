# 《AI-MA 异构协同与自适应灯光控制系统》总体架构规范书

**版本**: v5.3（混合硬实时微内核架构 · As-Built 实装口径）
**状态**: 生产标准已确立 · 架构冻结
**定位**: 开放式、模块化、跨领域可平移的通用端侧智能控制中枢平台
**替代关系**: 本文件取代 v4.3-Modular 同名文档。凡与代码冲突之处，以代码为准，并请回报修正。

---

## 0. 本版修订说明（v4.3 → v5.3）

v4.3-Modular 版本文档描述的目录结构、插件分层、时基频率与代码实测已严重脱节。本次逐项核对后修订：

| 项目 | v4.3 文档旧口径 | v5.3 实装口径 |
| --- | --- | --- |
| 插件目录 | `plugins/{protocols,perception,macros,llm}`（按功能平铺） | `plugins/{system,adapters,community}`（**按权限三层物理隔离**） |
| 实时时基 | `engine.py` 内 30Hz Python 主循环 | 独立 Rust 进程 `aima-rt-daemon` 44Hz 硬实时微内核 |
| 进程模型 | 单进程（Python 全包） | **双进程**：Rust 硬实时内核 + Python 业务控制台，/dev/shm 零拷贝耦合 |
| 工程根目录名 | `ai_lighting_system/` | `AI-MA5.3/` |
| 回归套件位置 | 根目录 `verify_*.py`（10 套） | `tests/` 目录（6 套 `test_*` + 17 套 `verify_*`） |
| API 路由数 | 60 条 | **90 条** |
| `core/` 模块数 | 9 个 | **15 个** + 1 个原生扩展 |
| 顶层目录数 | 8 个 | **15 个** |

> **维护纪律**：本文件的目录树由 `tools/documentation/verify_doc_tree.py` 自动比对真实文件系统。
> 修改目录结构后请同步更新本文件的目录树并重跑该校验，否则校验会报失实。

---

## 1. 架构核心愿景与开放性承诺

本系统不绑定于特定灯具型号、特定通信协议或特定大模型推理端点。微内核保持极简与确定性，外围通过标准化的 `Plugin SDK` 与开放式 `JSON Schema` 实现全生命周期热插拔与二次开发。

### 核心设计原则

1. **双进程混合微内核 (Hybrid Microkernel)**
   - **硬实时侧**：`aima-rt-daemon`（Rust，44Hz，SCHED_FIFO 优先级 98，绑定 CPU Core 3，mlockall 锁页，抖动 < 100µs）。只做四件事：恒定节奏调度、四级仲裁、O(1) 安全钳位、批量物理推流。
   - **业务侧**：`control_station.py`（Python 3.12，非实时）。承载事件总线 (`EventBus`)、多源信号仲裁状态机 (`DmxMerger`)、插件生命周期与依赖容器 (`PluginHost`)、RAG 知识库、大模型意图解析、Web 控制台。
   - **耦合方式**：**不经 Socket / HTTP / 消息队列**，而是通过 Linux `/dev/shm` 零拷贝共享内存直连。业务帧写入耗时实测约 **0.57µs**。

2. **北向/南向彻底解耦**
   - **北向（意图输入）**：自然语言意图理解（LLM）、Web 调度台、REST API、OSC 中控命令。
   - **南向（硬件驱动）**：可插拔协议驱动输出（Art-Net 3/4、sACN E1.31、GrandMA-Net 等）。

3. **分层确定性**
   - **非实时层（软时间）**：大模型意图提取、RAG 拓扑与美学检索（容忍 200ms ~ 2s）。
   - **硬实时层（工业级硬约束）**：44Hz 恒定帧率 DMX 刷新（周期 22.7ms）、微秒级 Crossfade 曲线插值、无抖动、永不断流。
   - **关键保障**：业务侧的任何卡顿（Web 请求洪峰、大模型推理、磁盘 IO）**在物理上无法影响**推流节奏——两者是不同进程，且实时进程独占隔离核心。

   > **⚠ 两个"帧率"必须分清，不可混写。**
   > **44Hz（22.7ms）是 Rust 微内核的物理推流节奏**，由内核调度器保证，恒定不变。
   > **Python 业务侧 `core/engine.py` 的 `fps` 默认值仍是 30**，它只是"业务向共享内存 L4 槽位
   > 提交合成帧"的频率（`kernel_bridge.submit_layer("l4", ...)`）。
   > 业务侧提交变慢**不会**改变物理推流节奏——微内核会持续重发最后一帧有效数据，
   > 这正是"业务卡顿不黑场"的实现方式。
   > 因此不要写成"44Hz 引擎"或"engine.py 是 44Hz"，`engine.py` 已不是时基来源。

4. **故障不传导**
   - 业务进程崩溃 → 微内核继续以最后有效帧推流，**演出不黑场**。
   - 微内核崩溃 → 业务侧运行期看门狗在数秒内发现、按预算重启，并记录 `ERR-KERNEL-DAEMON` / `ERR-KERNEL-STALL`。
   - 插件异常 → 被宿主熔断隔离，登记为装载失败项，不影响主循环。

---

## 2. 系统分层模型

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       1. 表现与交互层 (Presentation Layer)                  │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐   │
│  │ Web 监控/调度工作台  │  │ KB 独立工作台        │  │ 第三方 API       │   │
│  │ (web/, 端口 9000)    │  │ (kb_workbench.py)    │  │ (REST)           │   │
│  └──────────────────────┘  └──────────────────────┘  └──────────────────┘   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP /api/*  (统一鉴权闸门, 90 条)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│              2. 业务与意图层 (Python 3.12 · control_station.py)             │
│  ┌───────────────────┐    ┌────────────────────┐    ┌───────────────────┐   │
│  │ 意图理解 / LLM    │ ── │ RAG 三层知识检索器 │ ── │ Script-to-Cue 编排│   │
│  └───────────────────┘    └────────────────────┘    └───────────────────┘   │
│  ┌───────────────────┐    ┌────────────────────┐    ┌───────────────────┐   │
│  │ DmxMerger 仲裁    │    │ PluginHost 插件宿主│    │ 运行期内核看门狗  │   │
│  └───────────────────┘    └────────────────────┘    └───────────────────┘   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ /dev/shm 零拷贝（seqlock 双缓冲）
┌──────────────────────────────────────▼──────────────────────────────────────┐
│         3. 硬实时微内核层 (Rust · aima-rt-daemon · 44Hz / 22.7ms)           │
│  ┌────────────────────────┐  ┌────────────────────────┐  ┌──────────────┐   │
│  │ 四级仲裁               │  │ O(1) 安全钳位查找表    │  │ sendmmsg 推流│   │
│  │ L1>L4>L3>L2            │  │ safety_lut 约 8MB      │  │ + 微突发整形 │   │
│  └────────────────────────┘  └────────────────────────┘  └──────────────┘   │
└───────────────────┬──────────────────────────────────┬──────────────────────┘
                    │                                  │
┌───────────────────▼──────────────────────┐  ┌────────▼──────────────────────┐
│     4. 插件生态 (Plugin Ecosystem)        │  │    5. 硬件与协议抽象层 (HAL)  │
│  三层物理隔离：                           │  │  物理输出链路：               │
│  ┌───────────────┐ ┌───────────────┐     │  │  - Art-Net 3/4 (UDP 6454)     │
│  │ 1类 system/   │ │ 2类 adapters/ │     │  │  - sACN E1.31 (组播/单播)     │
│  │ 系统底座      │ │ 灯库资产适配  │     │  │  - 微内核直发, 44Hz 恒定      │
│  │ 用户不可见    │ │ 用户不可见    │     │  └───────────────────────────────┘
│  └───────────────┘ └───────────────┘     │
│  ┌───────────────────────────────┐       │
│  │ 3类 community/  用户可见/可热卸│       │
│  └───────────────────────────────┘       │
└──────────────────────────────────────────┘
```

---

## 3. 核心目录工程化结构

> 以下为 `AI-MA5.3/` 的真实结构（已由 `verify_doc_tree.py` 与文件系统逐条比对）。

```text
AI-MA5.3/
│
├── core/                           # Python 业务微内核（稳定层，零业务硬编码）
│   ├── plugin_sdk.py               # 开放式二次开发 SDK（基类、抽象契约、CoreContext）
│   ├── plugin_host.py              # 插件自动发现、三层装载、失败登记、诊断报告
│   ├── event_bus.py                # 线程安全发布/订阅事件总线
│   ├── dmx_merger.py               # 四级优先级仲裁与物理安全掩码
│   ├── engine.py                   # 业务侧调度与系统主上下文（已非时基来源）
│   ├── kernel_bridge.py            # ★v5.3 微内核零拷贝桥接（强依赖 numpy）
│   ├── artnet_sender.py            # Art-Net 发送器（业务侧旁路发送能力）
│   ├── auth_manager.py             # RBAC 鉴权与 root 动态 Key
│   ├── backup_manager.py           # 容灾备份与 SHA-256 快照校验
│   ├── kb_manager.py               # RAG 三层知识库检索中枢
│   ├── kb_service.py               # 知识库统一服务层
│   ├── node_discovery.py           # ArtPoll 设备发现 · 被动登记 · 掉线看门狗
│   ├── quick_cue_manager.py        # 快捷场景直通管理
│   ├── marketplace_service.py      # 插件市场服务
│   ├── diagnostics_logger.py       # 中文结构化诊断引擎（故障码 → 成因/处置）
│   └── aima_shm_sdk.pyd            # PyO3 abi3 原生扩展（根目录另有一份副本）
│
├── plugins/                        # 插件生态（三层物理隔离，权限边界由目录决定）
│   ├── system/                     # 1 类·系统级：随内核启动，用户不可见，禁止卸载
│   │   ├── artnet_plugin.py        #   protocol_artnet_standard
│   │   ├── sacn_plugin.py          #   protocol_sacn_standard
│   │   ├── qwen_plugin.py          #   llm_local_qwen_7b
│   │   └── system_log_ai_repair_plugin.py   # system_log_ai_repair
│   ├── adapters/                   # 2 类·适配级：专业人员维护，用户不可见
│   │   └── ma_fixture_adapter.py   #   adapter_ma_fixture
│   └── community/                  # 3 类·表现创意：插件市场唯一展示分类，可热卸载
│       ├── breathing_plugin.py             # macro_breathing
│       ├── marquee_plugin.py               # macro_marquee
│       ├── perception_audio_beat_sim.py    # perception_audio_beat_sim
│       └── show_evolution_learning_plugin.py  # show_evolution_learning
│
├── knowledge_base/                 # RAG 三层声明式数据资产（开放元数据）
│   ├── profiles/                   # 物理灯库物模型与安全掩码（JSON，含 range/slots）
│   ├── venues/                     # 场地四层节点拓扑（解码器→接口→灯具→通道）
│   └── presets/                    # 艺术美学预设 + 分类注册表 + 属性分组注册表
│
├── bin/                            # ★v5.3 原生二进制
│   └── aima-rt-daemon.exe          #   Rust 硬实时微内核（Linux 为无后缀 ELF）
│
├── config/                         # 现场配置（明文开放）
│   ├── users.json                  #   RBAC 用户与角色
│   ├── plugins_config.json         #   插件启停与参数
│   ├── quick_scenes.json           #   快捷场景
│   └── control_panel_layout.json   #   主控面板布局
│
├── deploy/                         # ★v5.3 部署工件
│   ├── aima-rt.service             #   微内核 systemd 单元（必须先启动）
│   ├── ai-ma.service               #   业务控制台单元（BindsTo 微内核）
│   └── debian_install.sh           #   Debian 安装脚本
│
├── docs/                           # 工程技术规范与二次开发文档
│   ├── 01_system_architecture.md            # 本文件
│   ├── 02_plugin_development_sdk.md         # 插件开发指南与 SDK 规范
│   ├── 03_data_schema_specification.md      # 知识库标准 Schema 规范
│   ├── 04_dmx_safety_and_arbitration.md     # DMX 仲裁逻辑与安全掩码策略
│   ├── 05_enterprise_security_and_debian_guide.md  # 企业安全与 Debian 部署
│   ├── 07_技术方案核心思想符合性与全量逻辑验证报告.md
│   └── ARCHITECTURE_UPGRADE_GUIDE.md        # v5.3 升级与运维速查
│
├── tests/                          # ★v5.3 全部测试与回归套件（不再散落根目录）
│   ├── test_aima53_standalone_system.py     # v5.3 静态架构准出
│   ├── test_aima53_boot_e2e.py              # v5.3 双进程端到端准出
│   ├── test_plugin_observability.py         # v5.3 插件装载可观测性
│   ├── test_auth_noise_suppression.py       # v5.3 鉴权噪音抑制
│   ├── test_kernel_watchdog.py              # v5.3 内核看门狗
│   ├── test_release_package_integrity.py    # v5.3 发布包完整性
│   ├── verify_architecture.py               # v4.x 微内核与插件生态回归
│   ├── verify_node_discovery.py             # v4.x 协议层与状态机
│   ├── verify_node_alarm.py                 # v4.x 掉线告警端到端
│   ├── verify_kb_api.py                     # v4.x 知识库 HTTP 接口
│   ├── verify_kb_console.py                 # v4.x 知识库服务层
│   ├── verify_ui_v42.py                     # v4.x 界面契约
│   ├── verify_smoke_9000.py                 # v4.x 真机烟雾测试
│   └── verify_security.py                   # v4.x 安全加固
│
├── tools/                          # 工程质量工具（非运行时依赖）
│   ├── build_release.py            #   一键发布构建（前端混淆 + 构件组装 + 完整性门禁）
│   ├── gen_root_key.py             #   root 动态 Key 生成
│   ├── audit_ui_layout.py          #   界面几何量化审计（无头浏览器实测盒模型）
│   ├── check_ui_contract.py        #   前端契约检查
│   ├── migrate_kb_v3.py            #   知识库 v3 迁移
│   ├── migrate_liveness_default.py #   存活判据默认值迁移
│   ├── render_ui_preview.py        #   离线 UI 预览渲染
│   ├── inspect_doc.py              #   文档勘察
│   └── documentation/              #   文档生成与一致性校验工具链
│
├── web/                            # 企业级前端资产层（与服务端解耦）
│   ├── login.html                  #   登录门头页（aurora 光束 + 玻璃拟态）
│   ├── index.html                  #   后台主界面（侧边导航 + 顶栏 + 功能视图）
│   ├── _preview.html               #   离线预览页
│   └── assets/                     #   theme.css / app.js
│
├── marketplace/                    # 插件市场包目录
│   └── plugin_catalog.json         #   市场包索引
│
├── dist/                           # [构建产物] 发布包输出目录
├── backups/                        # [运行数据] 容灾快照与用户备份
├── logs/                           # [运行数据] 中文结构化诊断日志
├── screenshots/                    # [工具产物] 无头渲染截图
│
├── control_station.py              # 【唯一 Web 入口】统一总控台服务（端口 9000）
├── kb_workbench.py                 # 知识库独立工作台入口
├── main.py                         # 命令行/无界面启动入口
├── VERSION                         # 版本固化文件
├── CHANGELOG.md                    # 变更日志
├── aima_shm_sdk.pyd                # PyO3 原生扩展（core/ 内另有一份）
├── 启动系统总控台.bat              # 一键启动脚本
└── 一键生成发布包.bat              # 一键发布构建脚本
```

### 3.1 关键结构变更的工程理由

| 变更 | 理由 |
| --- | --- |
| `plugins/` 由功能平铺改为三层隔离 | 原 `protocols/llm/macros/perception` 按"做什么"分类，无法表达**权限差异**。1/2 类插件是系统底座，用户误卸载会导致无物理输出或无法导入灯库；3 类是用户自制内容。改为按**谁能看见、谁能卸载**分层后，过滤可以只做在目录与接口两层。 |
| 新增 `bin/` 与 `deploy/` | v5.3 引入独立 Rust 进程，二进制与 systemd 双单元需要独立存放，不再混在 `core/`。 |
| 测试全部收进 `tests/` | 原根目录散落 10 余个 `verify_*.py`，与运行时文件混杂。现全部归入 `tests/`。 |
| 新增 `core/kernel_bridge.py` | 业务侧访问微内核的唯一入口，强依赖 numpy。 |
| 新增 `core/marketplace_service.py` | 插件市场从 `control_station.py` 内联逻辑抽离为独立服务。 |

---

## 4. 插件三层物理隔离体系

v5.3 最重要的一项架构决策。三层不是"分类标签"，而是**由目录位置决定的权限边界**。

| 层级 | 目录 | 基类 | 装载时机 | 用户可见 | 可否卸载 | 失效后果 |
| --- | --- | --- | --- | --- | --- | --- |
| **1 类·系统级** | `plugins/system/` | `BaseProtocolPlugin` / `BaseLLMPlugin` | 随内核启动，全静默 | 否 | 禁止 | **致命**：无任何物理输出 |
| **2 类·适配级** | `plugins/adapters/` | `BaseAdapterPlugin` | 随系统启动 | 否 | 禁止 | **严重**：无法导入控台灯库资产 |
| **3 类·表现创意** | `plugins/community/` | `BaseMacroPlugin` / `BasePerceptionPlugin` | 按需加载 | 是（市场唯一分类） | 支持热卸载 | **轻微**：仅该插件特效失效 |

> **设计红线**：只有 3 类插件允许出现在用户界面与 `/api/plugins/installed` 接口中。
> 过滤必须做在**接口层**——前端隐藏随时可能被绕过，接口过滤才是物理边界。
> 运维可通过 admin 专属的 `/api/plugins/diagnostics` 查看全部三层与失败明细。

### 4.1 抽象方法契约（开发者必读）

| 基类 | 层级 | 必须实现的抽象方法 |
| --- | --- | --- |
| `BasePlugin` | 根 | `get_info()` · `on_init(context)` · `on_enable()` · `on_disable()` |
| `BaseProtocolPlugin` | 1 类 | 上述四项 + `send_universe(universe, dmx_data_512)` |
| `BaseLLMPlugin` | 1 类 | 上述四项 + `chat_completion(...)` |
| `BaseAdapterPlugin` | 2 类 | 上述四项 + `supported_extensions()` · `convert_to_profile(...)` |
| `BaseMacroPlugin` | 3 类 | 上述四项 + `render(...)` |
| `BasePerceptionPlugin` | 3 类 | 上述四项 + `get_status()` |

> **注意**：`on_destroy()` 与 `start_listening()` **并非抽象方法**，早期文档有误。
> 遗漏任一抽象方法，Python 会把该类判定为抽象类，插件将在**类发现阶段被拒收**。
> 校验细节见 `02_plugin_development_sdk.md`。

### 4.2 实装插件全量清单（共 9 个）

| 层级 | 插件 id（日志检索用） | 源码文件 |
| --- | --- | --- |
| 1 类 | `protocol_artnet_standard` | `plugins/system/artnet_plugin.py` |
| 1 类 | `protocol_sacn_standard` | `plugins/system/sacn_plugin.py` |
| 1 类 | `llm_local_qwen_7b` | `plugins/system/qwen_plugin.py` |
| 1 类 | `system_log_ai_repair` | `plugins/system/system_log_ai_repair_plugin.py` |
| 2 类 | `adapter_ma_fixture` | `plugins/adapters/ma_fixture_adapter.py` |
| 3 类 | `macro_breathing` | `plugins/community/breathing_plugin.py` |
| 3 类 | `macro_marquee` | `plugins/community/marquee_plugin.py` |
| 3 类 | `perception_audio_beat_sim` | `plugins/community/perception_audio_beat_sim.py` |
| 3 类 | `show_evolution_learning` | `plugins/community/show_evolution_learning_plugin.py` |

> **排查提示**：插件 id 与源码文件名**并不相同**（如 id 为 `macro_breathing`，文件名为 `breathing_plugin.py`）。
> 查问题时用 **id 检索日志**，用 **文件名定位源码**。

---

## 5. 接口清单

### 5.1 统一总控台 API 路由（共 90 条，全部经统一鉴权闸门）

| 分组 | 条数 | 路由 |
| --- | ---: | --- |
| 会话与鉴权 | 3 | `/api/auth/login` `/api/auth/logout` `/api/auth/verify` |
| 知识库 · 灯库 | 8 | `/api/kb/profiles` `/api/kb/profile_detail` `/api/kb/profile_attributes` `/api/kb/save_profile` `/api/kb/delete_profile` `/api/kb/ai_extract_profile` `/api/kb/import_ma_xml` `/api/kb/conflicts` |
| 知识库 · 场地 | 5 | `/api/kb/venues` `/api/kb/venue_detail` `/api/kb/save_venue` `/api/kb/delete_venue` `/api/kb/switch_venue` |
| 知识库 · 预设与分类 | 9 | `/api/kb/presets` `/api/kb/save_preset` `/api/kb/save_presets` `/api/kb/delete_preset` `/api/kb/categories` `/api/kb/save_category` `/api/kb/save_categories` `/api/kb/delete_category` `/api/kb/attribute_groups` |
| 知识库 · 总览与校验 | 4 | `/api/kb/save_attribute_groups` `/api/kb/summary` `/api/kb/rag_test` `/api/kb/check_conflicts` |
| 设备发现与告警 | 7 | `/api/nodes/discovered` `/api/nodes/scan` `/api/nodes/test_connection` `/api/nodes/sync_watchdog` `/api/nodes/set_manual_state` `/api/alarms` `/api/alarms/ack` |
| 灯光输出 | 11 | `/api/scenes/list` `/api/scenes/save` `/api/scenes/delete` `/api/scenes/trigger_direct` `/api/scenes/ai_assist` `/api/scenes/capture_current` `/api/presets/apply` `/api/lighting/execute` `/api/lighting/stop_sequence` `/api/lighting/panic` `/api/dmx/universe/<n>` |
| 主控面板 | 2 | `/api/panel/layout` `/api/panel/save_layout` |
| 插件与市场 | 12 | `/api/plugins/installed` `/api/plugins/detail` `/api/plugins/save_config` `/api/plugins/toggle_enabled` `/api/plugins/uninstall` `/api/plugins/community` `/api/plugins/community/upload` `/api/plugins/ui_extensions` `/api/plugins/diagnostics` `/api/market/packages` `/api/market/install` `/api/market/verify_code` |
| 用户管理 | 6 | `/api/users/list` `/api/users/save` `/api/users/delete` `/api/users/profile` `/api/users/change_password` `/api/users/rename_admin` |
| 备份与容灾 | 11 | `/api/backups/snapshots` `/api/backups/create_snapshot` `/api/backups/restore_snapshot` `/api/backups/delete_snapshot` `/api/backups/user_pkgs` `/api/backups/save_user_backup` `/api/backups/restore_user_backup` `/api/backups/delete_user_backup` `/api/backups/download_user_backup` `/api/backups/export_user_pkg` `/api/backups/import_user_pkg` |
| 大模型与诊断 | 8 | `/api/llm/config` `/api/llm/save_config` `/api/llm/test_connection` `/api/monitor/stats` `/api/system/status` `/api/system/version` `/api/system/check_update` `/api/system/apply_update_pkg` |
| 内核与运维 | 4 | `/api/kernel/telemetry` `/api/system/shutdown` `/api/logs/stream` `/api/` |

> **两条执行路径必须分清**：
> - `/api/scenes/trigger_direct` 与 `/api/presets/apply` 是**直通路径**——请求体只带 ID，
>   服务端直接查表取出预存的 `payload` 并提交 DMX 合并器，**完全不经过大模型**，
>   点击到出光是 0 毫秒级、现场演出可预期的。
> - `/api/lighting/execute` 是**自然语言路径**——请求体带 `command` 文本，
>   走 RAG 检索 + 大模型解析后再执行，耗时与可用性取决于模型端点是否在线。
>   现场快捷键位一律走前者；后者仅用于即兴语音/文字点灯。

### 5.2 共享内存接口（微内核耦合面）

| 文件 | 用途 | 写入方 | 读取方 |
| --- | --- | --- | --- |
| `/dev/shm/aima_slot_l1` | 安全层：急停、黑场、物理熔断 | 业务层 | 微内核 |
| `/dev/shm/aima_slot_l2` | 设备基础层：静态预设、灯库底态 | 业务层 | 微内核 |
| `/dev/shm/aima_slot_l3` | 创意层：宏插件、特效、音频节拍 | 插件宿主 | 微内核 |
| `/dev/shm/aima_slot_l4` | 台面层：控台接管、Crossfade 淡变 | 业务层 | 微内核 |
| `/dev/shm/aima_core_state` | 全局只读状态：合成帧 + 8MB 安全查找表 | 微内核（独占） | 业务层（只读） |

详细 ABI 结构体定义见《v5.3 硬实时微内核架构实装白皮书》。

---

## 6. 回归验证体系

> **全部测试脚本位于 `tests/` 目录**，均为纯 Python 标准库实现，不依赖 pytest 等外部框架，
> 可直接在交付现场运行。早期版本散落在根目录的 `verify_*.py` 已全部归入该目录。

### 6.1 v5.3 准出套件（`tests/test_*.py`）

| 套件 | 断言数 | 状态 | 覆盖范围 |
| --- | ---: | --- | --- |
| `test_aima53_standalone_system.py` | 5 | 已实测通过 | 桥接可用、内核模式锁定、三层隔离、L4 写入 |
| `test_plugin_observability.py` | 31 | 已实测通过 | 分层日志、四类失败路径登记、故障码、诊断报告 |
| `test_auth_noise_suppression.py` | 28 | 已实测通过 | 注销零噪音、突发仍告警、登录失败告警、前端闩锁 |
| `test_aima53_boot_e2e.py` | 32 | 已实测通过 | 双进程启动、日志基线、鉴权、插件零泄漏、遥测、孤儿回收 |
| `test_kernel_watchdog.py` | 17 | 已实测通过 | 真杀内核后看门狗自动拉起 |
| `test_release_package_integrity.py` | 35 | 已实测通过 | 真实构建、产物强校验、真实启动发布包 |
| **合计** | **148** | **全绿（实测约 34 秒）** | |

运行方式：

```bash
python tools/documentation/run_all_tests.py    # 采集各套件自报断言数并落盘权威结果
```

> **数字来源纪律**：断言数必须取自套件**自报**的 `N/N 全部通过`。
> 用正则静态统计 `check(` 调用点是不可靠的——循环内的断言会漏算，
> 裸 `assert` 型套件会被算成 0。曾因此把总数写错。

### 6.2 v4.x 历史回归套件（`tests/verify_*.py`，共 17 套 / 414 项断言）

**实测状态：17 / 17 全部通过**（`tools/documentation/run_verify_suites.py`，总耗时约 44 秒）。

| 套件 | 断言 | 覆盖范围 | 数据风险 |
| --- | ---: | --- | --- |
| `verify_node_discovery.py` | 54 | ArtPoll 报文字节序、畸形包兜底、网段上限、看门狗三态、**AST 级"绝不发 ArtDmx"红线** | 无 |
| `verify_ui_v42.py` | 59 | 界面契约：类名/ID 完整性、视图可达性、设计标度、登录页安全入口校验 | 拉起服务端 |
| `verify_kb_api.py` | 58 | 知识库全部 HTTP 接口：CRUD、强制分类、共址降级、RBAC 403 | 写知识库（自动还原） |
| `verify_kb_console.py` | 31 | 知识库服务层：归一化、冲突检测五类型、端口标签、离线策略 | 读写知识库 |
| `verify_smoke_9000.py` | 30 | 真机烟雾测试：真实拉起服务，门禁/静态资产/路径穿越/RBAC | **占用 9000 端口** |
| `verify_v5_rbac_and_disaster_recovery.py` | 30 | RBAC 与容灾恢复、用户配置包跨用户导入 | 写配置（自动还原） |
| `verify_security.py` | 27 | PBKDF2 凭据、中文诊断、Cython 编译脚本、双 systemd 单元、发布清单 | 自清理 |
| `verify_node_alarm.py` | 26 | 真实 ArtDmx 注入驱动的掉线告警全链路 | 读写知识库（自动还原） |
| `verify_marketplace_deep.py` | 21 | 插件市场深度链路 | 读写知识库 |
| `verify_v5_backup_limits_and_debrand.py` | 16 | 备份槽位上限与去品牌化 | 备份（自动还原） |
| `verify_categories_management.py` | 15 | 分类与属性分组管理 | 读写知识库 |
| `verify_takeover_learning.py` | 12 | 控台接管与学习链路 | 读写知识库 |
| `verify_shutdown_persistence_ui.py` | 9 | 停机持久化与界面状态 | 读写知识库 |
| `verify_marketplace_features.py` | 9 | 插件市场安装/卸载/启用 | 拉起服务端 |
| `verify_architecture.py` | 8 | 事件总线、HTP/LTP 仲裁、物理安全掩码、**业务侧 L4 提交链路**、生命周期停机释放 | 无 |
| `verify_direct_scenes.py` | 5 | 快捷场景 0ms 直通（不触碰大模型） | 拉起服务端 |
| `verify_unified_station.py` | 4 | 统一总控台入口 | 拉起服务端 |
| **合计** | **414** | | |

> **⚠ 运行前必读**：上表有 **12 套会读写真实 `knowledge_base/`、`config/` 或执行删除操作**。
> 实测一轮会修改 `config/control_panel_layout.json`、`config/plugins_config.json`、
> `knowledge_base/presets/aesthetic_presets.json`，并在 `backups/auto_snapshots/` 新建并轮转快照。
> **运行前必须备份 `knowledge_base/`、`config/`、`backups/` 三个目录。**
> `run_verify_suites.py` 内置运行前后哈希快照比对，会明确报出被改动的文件。

#### 6.2.1 迁移到 `tests/` 时产生的路径损坏（已修复）

这些套件原本位于项目根目录，`BASE_DIR` 的语义是"项目根"。搬迁到 `tests/` 时**只改了一部分**，
导致 17 套 `verify_*.py` 与 `udp_receiver_test.py` 的 `BASE_DIR` 仍指向 `tests/`，
导入 `core/*` 与定位 `knowledge_base/`、`config/` 全部失败。已把 18 个文件的 `BASE_DIR`
改为双层 `dirname`；另有 3 套需额外 `sys.path.append(BASE_DIR)` 才能 `import control_station`。

#### 6.2.2 修复的三类历史失配

| 套件 | 原失败原因 | 修复方式 |
| --- | --- | --- |
| `verify_architecture.py` | 断言 Python `engine` 会广播 Art-Net 报文（注释写"30*4=120 个包"）。该前提在 v5.3 已不成立——物理发包已移至 Rust 微内核，Python 侧只写共享内存 L4 槽位 | 改为统计 `kernel_bridge.submit_layer` 的实际调用次数 |
| `verify_kb_api.py` / `verify_node_alarm.py` / `verify_smoke_9000.py` | 用 `guest`/`guest` 登录，但交付的 `config/users.json` 只有 `admin` 与 `root`（出厂默认库本含 `guest` 观察员，该文件里被删过），导致登录失败、RBAC 断言拿到 401 而非 403 | 测试开始时按需创建 `guest`(viewer) fixture，结束时删除，配置净零变化 |
| `verify_security.py` | `from build_hardener import CodeHardener` —— 该模块已移除 | 改为直接校验现行 `tools/build_release.py` 流水线 |
| `verify_ui_v42.py` | 断言登录页含 `quick-roles` 快捷身份入口，但该入口在 v5 已被**有意移除**（安全改进）；`verify_v5_rbac` 反而断言它不存在——两者曾互相矛盾 | 改为断言该危险入口确实不存在 |
| `verify_v5_rbac_and_disaster_recovery.py` | 硬编码断言版本号为 `5.0.0` | 改为自洽性断言（语义化格式 + 主号 + 与 `version_display`/`architecture` 一致） |

---

## 7. 跨领域平移能力（商业化前景）

通过替换最外层的**物模型 (Profiles)**、**空间拓扑 (Venues)** 与**输出协议插件**，系统可零改动平移至：

- **高端智能家居与全屋照明**（平移至 KNX / Matter / ZigBee 协议）
- **商业文旅沉浸式展陈**（平移至投影交互 / 中控继电器 / 激光协议）
- **工业柔性物联网控制**（平移至 Modbus-TCP / Profinet，将灯库转为 PLC 寄存器映射）

平移的关键在于：硬实时推流骨架、四级仲裁、安全钳位、RAG 检索与插件隔离体系**都与灯具协议无关**，
只需替换 1 类协议插件与 3 类表现插件即可。

---

## 附录 A：v5.3 与前版的核心差异速查

| 维度 | v4.3-Modular | v5.3 |
| --- | --- | --- |
| 实时载体 | Python `engine.py` 30Hz 循环 | Rust `aima-rt-daemon` 44Hz |
| 进程数 | 1 | 2（业务 + 实时） |
| 进程间通信 | 进程内函数调用 | `/dev/shm` 零拷贝 + seqlock |
| 抖动保证 | 无（受 GIL 与时间片影响） | < 100µs（SCHED_FIFO + Core 3 隔离 + mlockall） |
| 插件分类依据 | 功能（protocols/llm/macros/perception） | **权限层级**（system/adapters/community） |
| 插件可见性 | 全部可见 | 仅 3 类可见，1/2 类接口层过滤 |
| 安全钳位 | 分支判断 | `safety_lut[64][512][256]` O(1) 零分支 |
| 内核故障感知 | 仅启动时检查一次 | 运行期看门狗（三场景 + 重启预算） |
| 部署单元 | 单个 `ai-ma.service` | 双单元（`aima-rt.service` + `ai-ma.service`，BindsTo） |
| 测试位置 | 根目录 `verify_*.py` | `tests/` 目录 |

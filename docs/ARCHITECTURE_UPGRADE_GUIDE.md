# AI-MA v5.3 独立系统（新型硬实时微内核架构版）技术交付与运维文档

> **发布版本**: `AI-MA v5.3.0 Enterprise LTS (Hybrid Microkernel Architecture)`  
> **工程物理路径**: `D:\python项目文件\AI-MA5.3`  
> **应急原版路径 (完全不动备份)**: `D:\python项目文件\ai_lighting_system`

---

## 1. 架构重大演进：新型硬实时微内核“彻底替换”原有内核

本系统在保持上层业务功能与 Web 控制台体验 100% 兼容的前提下，彻底废除了旧版单体 Python 线程软发包架构，实施了**双引擎异构硬实时微内核重构**：

```text
+---------------------------------------------------------------------------------------+
|  上层：Python 业务调度与意图理解层 (AI-MA5.3 Control Station)                            |
|  - 自然语言大模型理解 / RAG 知识库 / 快捷场景直通 / 3类表现创意插件沙箱 (呼吸/走马灯/BPM)   |
|  - 毫秒级场景平滑过渡 (Crossfade) 插值演算                                             |
+---------------------------------------------------------------------------------------+
                                           │
                                           │ 0.57µs 零拷贝写入 (np.ascontiguousarray)
                                           ▼
+---------------------------------------------------------------------------------------+
|  物理高速共享内存总线 (/dev/shm/* - 64 字节缓存行硬件隔离对齐)                           |
|  - aima_slot_l1 (L1 紧急安全)  - aima_slot_l2 (L2 设备底色)                             |
|  - aima_slot_l3 (L3 创意表现)  - aima_slot_l4 (L4 控台/过渡帧)                          |
|  - aima_core_state (64 宇宙仲裁帧 + 8MB Safety-LUT 硬件无分支钳位查找表)                 |
+---------------------------------------------------------------------------------------+
                                           ▲
                                           │ 44Hz 精确单调时钟读取 (Zero-Wait Seqlock)
                                           │
+---------------------------------------------------------------------------------------+
|  底层：Rust 44Hz 硬实时微内核 (AI-MA5.3/bin/aima-rt-daemon.exe)                        |
|  - L1 > L4 > L3 > L2 四级绝对抢占仲裁流水线                                           |
|  - Pan/Tilt 16-bit 粗微调通道双字节原子捆绑 (消除舵机抖动)                              |
|  - 64 宇宙批量网络批量广播推流 (batch_network / Art-Net)                               |
|  - RtGuardAllocator 内存分配熔断防抖动守卫                                              |
+---------------------------------------------------------------------------------------+
```

---

## 2. 核心实施与替换事实记录

1. **主循环引擎彻底抽心 (`AI-MA5.3/core/engine.py`)**：
   - 彻底移除了原先 Python 主线程在 30Hz 循环中逐个调用 Socket 协议发包的旧逻辑；
   - 引擎重构为专职的微内核客户端（Client Host），演算后的场景数据以 **0.57µs** 直接卸载写入共享内存 `L4` 控制台槽位。
2. **伴生微内核看门狗与生命周期纳管 (`AI-MA5.3/control_station.py`)**：
   - `control_station.py` 在初始化时自动探测并拉起伴生守护进程 `bin/aima-rt-daemon.exe`；
   - 实现了双进程协同看门狗与优雅关机联动，服务关闭时自动回收微内核，杜绝孤儿进程。
3. **插件三层架构严格物理隔离与纯净化**：
   - **1 类系统插件**（Art-Net 协议驱动、sACN 协议驱动、端侧 Qwen 中枢、AI 日志自愈中枢）和 **2 类适配插件**（GrandMA2/3 资产转换）随内核启动，保持纯净静默运行；
   - **前端插件面板**（`/api/plugins/installed`）**100% 仅展示 3 类表现与创意插件**（呼吸律动、走马灯、BPM 律动、演后学习），普通用户与灯光师不再看到底层驱动，彻底杜绝误操作；
   - 1 类与 2 类的异常和报警统一通过系统日志与诊断面板进行故障透出。

---

## 3. 快速启动与验证指南

### 3.1 启动新型系统
打开 PowerShell，直接运行新目录下的启动入口：
```powershell
cd "D:\python项目文件\AI-MA5.3"
& "C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" control_station.py
```
> **启动特征**：
> - 看到 `AI-MA v5.3 硬实时微内核 (aima-rt-daemon) 已成功拉起伴生运行`
> - 看到 `AIMA v5.3 工业级硬实时微内核共享内存驱动初始化成功！`
> - 看到 `CoreEngine: 已启用 AI-MA v5.3 硬实时微内核硬件卸载加速模式 (v5.3_shm)！`

### 3.2 界面验证
* 打开浏览器访问：**`http://127.0.0.1:9000`**
* 使用账号 `admin` / 密码 `admin123` 登录；
* 进入【插件市场】的【已装载插件】面板，可以确认**仅有 3 类表现创意插件（4 个）**，1 类底层协议与 2 类适配器已完全静默隐匿。

### 3.3 自动化集成测试套件验证
在任何时候都可以执行新目录下的自动化测试套件：

```powershell
# 套件 A：静态架构准出（共享内存桥接 / 引擎抽心 / 三层插件隔离 / L4 卸载）
& "C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" D:\python项目文件\AI-MA5.3\tests\test_aima53_standalone_system.py

# 套件 B：双进程伴生架构端到端准出（真实进程 + 真实 HTTP，19 项断言）
& "C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" D:\python项目文件\AI-MA5.3\tests\test_aima53_boot_e2e.py
```

| 套件 | 覆盖维度 | 结论 |
|---|---|---|
| `test_aima53_standalone_system.py` | 共享内存桥接挂载、`use_kernel_rt` 锁定、三层插件隔离、L4 槽位 0.57µs 卸载 | **4/4 PASS** |
| `test_aima53_boot_e2e.py` | 真实拉起总控、伴生微内核存活、内核日志落盘、系统日志关键基线、登录鉴权、1/2 类零泄漏、遥测数据有效性、孤儿进程回收 | **19/19 PASS** |

---

## 4. 联调排障记录（启动期实测缺陷与修复）

以下两个缺陷均在**真实进程端到端联调**中被捕获并修复，非静态代码审查所能发现。

### 4.1 `NameError: name 'Optional' is not defined`（启动即崩溃）

* **现象**：`control_station.py` 启动到知识库加载完成后立即抛 `NameError` 并退出。
* **根因**：伴生微内核管理模块使用 `Optional[subprocess.Popen]` 类型注解，但文件 import 区未引入 `typing`。
* **修复**：在 import 区补齐 `from typing import Optional, Dict, Any, List`。
* **加固**：此类"注解期崩溃"应被静态检查拦截，已纳入 `py_compile` 语法准出流程。

### 4.2 `/api/kernel/telemetry` 直接断开连接（RemoteDisconnected）

* **现象**：浏览器/客户端请求遥测接口时，连接在**未返回任何响应**的情况下被服务端关闭。
* **根因**：`sample_universe_0_head` 使用 `list(final_merged[0, :16])`，而共享内存回读得到的是 **numpy 标量（`np.uint8`）**。`_send_json()` 的执行顺序是"先 `json.dumps()`，后 `send_response()`"，因此 `TypeError: Object of type uint8 is not JSON serializable` 在响应头下发**之前**抛出，客户端只能看到连接被重置。
* **修复**：
  1. 显式降级为 Python 原生类型：`[int(v) for v in final_merged[0, :16]]`，`m[0..3]` 同样包 `int()`；
  2. 整个遥测分支包裹 `try/except`，任何异常都转为 `ERR-KERNEL-TELEMETRY` 诊断码 + HTTP 500 结构化响应，**绝不再让连接静默断开**。
* **教训**：凡是从共享内存/NumPy 回读的数据要经 HTTP 输出，必须在边界处做原生类型归一。

### 4.3 伴生微内核孤儿进程（关闭总控后内核仍常驻）

* **现象**：`test_aima53_boot_e2e.py` 第 8 步检出——总控进程终止后 `aima-rt-daemon` 仍以 PID 4428 存活。
* **根因**：原先仅在 `run_server()` 的 `except KeyboardInterrupt` 中调用 `stop_microkernel()`。在 Windows 上 `Popen.terminate()` 走 `TerminateProcess`，**不投递任何可捕获信号**，该分支永不执行。
* **修复（三重保险）**：
  1. **操作系统级**：进程启动即创建 Windows 作业对象并设置 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`，把微内核 `AssignProcessToJobObject` 纳入该作业。总控进程一旦消亡（含被强杀），操作系统**原子回收**微内核；
  2. **进程级**：注册 `atexit.register(stop_microkernel)`，覆盖正常返回与未捕获异常路径；
  3. **交互级**：保留 `Ctrl+C` 的 `KeyboardInterrupt` 优雅停止路径。
  4. Linux 平台无作业对象，由 systemd 单元的 `PartOf=` / `BindsTo=` 依赖提供同等语义。
* **验证**：修复后第 8 步断言 `无孤儿进程` 通过，实测进程已被干净回收。

### 4.4 内核日志可观测性加固

原实现以 `stdout=subprocess.DEVNULL` 拉起微内核，导致内核自身的启动与异常信息被完全丢弃，违背"底层故障必须可溯源"的准则。

现改为：
* 内核输出重定向至独立文件 `logs/aima_rt_daemon.log`（**使用文件句柄而非 `PIPE`**，防止无人读取管道导致内核写满缓冲区后阻塞）；
* 新增 `check_microkernel_health()`：启动后自检进程是否存活，若异常退出则立即以 `ERR-KERNEL-DAEMON` 诊断码把**退出码 + 内核日志尾部**写入系统故障日志。

### 4.5 `启动系统总控台.bat` 选错解释器导致启动即崩溃（既有缺陷）

* **现象**：双击 `.bat` 启动后，服务在"知识库加载完成"之后立即崩溃。
* **根因**：`.bat` 原逻辑用 `where python` 优选解释器，在本机解析到 **`D:\python软件\python解释器3.14\python.exe`（Python 3.14.4）**，而该环境**未安装 numpy**。`core/kernel_bridge.py` 第 11 行 `import numpy as np` 是硬依赖，于是 `from engine import CoreEngine` 直接抛 `ModuleNotFoundError`。
* **实测证据**：

  | 检查项 | 结果 |
  |---|---|
  | PATH 中的 `python` | 3.14.4 · **无 numpy** |
  | 捆绑 DSH 运行时 | 3.12.14 · numpy 2.3.5 ✓ |
  | `aima_shm_sdk.pyd` | 链接 `python3.dll`（**稳定 ABI**），3.12 / 3.14 均可导入 —— 不是瓶颈 |
  | 新系统用 3.14 启动 | FAIL `No module named 'numpy'` |
  | **原版备份**用 3.14 启动 | **同样 FAIL** → 证明是既有缺陷，与本次换核无关 |

* **修复**：重写解释器探测为**"先探测、后采纳"**策略，按优先级遍历候选解释器，逐个执行 `-c "import numpy"` 探针，只采纳真正满足依赖的那个：

  1. `AIMA_PYTHON` 环境变量显式覆盖（最高优先级）；
  2. 捆绑的 DSH 运行时（已知具备 numpy）；
  3. `where python` 枚举出的**每一个** PATH 解释器；
  4. `py -3` 启动器；
  5. 常见安装路径。

  全部候选都不合格时，输出明确的修复指引（`pip install numpy` 或设置 `AIMA_PYTHON`）而非静默崩溃。同时新增启动自检回显：打印实际选中的解释器、微内核扩展是否可用（`hardware offload` / `software mode`）、以及 `aima-rt-daemon` 二进制是否存在。

* **附带改进**：新增 `AIMA_NO_BROWSER=1` 无头模式开关，供服务器 / CI 场景跳过浏览器自动打开。

---

## 5. 运维速查

| 场景 | 操作 |
|---|---|
| 一键启动（推荐） | 双击 `启动系统总控台.bat` |
| 无头/服务器启动 | `set AIMA_NO_BROWSER=1` 后运行 `.bat` |
| 指定解释器 | `set AIMA_PYTHON=C:\path\to\python.exe` 后运行 `.bat` |
| 查看内核是否伴生运行 | `Get-Process aima-rt-daemon` |
| 查看内核自身日志 | `Get-Content logs\aima_rt_daemon.log -Tail 30 -Encoding utf8` |
| 查看系统故障告警 | 关注 `logs\ai_ma_system.log` 中的 `[故障告警 - 代码 ERR-KERNEL-*]` |
| 查看微内核实时遥测 | 登录后 GET `http://127.0.0.1:9000/api/kernel/telemetry` |
| 内核异常退出后的表现 | 系统日志出现 `ERR-KERNEL-DAEMON`，`CoreEngine` 自动降级为纯软件兼容模式 |
| 复位创意插件交付基线 | 删除 `config\plugins_config.json` 中对应插件的 `"enabled": false` 条目 |
| **生成生产发布包** | 双击 `一键生成发布包.bat`，或 `python tools\build_release.py` |
| **发布包完整性预检** | `python tests\test_release_package_integrity.py` |
| Debian 部署 | 上传 `dist\ai-ma-v5-release\` → `bash build_debian.sh` → `sudo bash deploy/debian_install.sh` |
| 指定内核源码路径 | `bash build_debian.sh /path/to/ai-ma-kernel-v5.3` 或 `export AIMA_KERNEL_SRC=...` |

> **关于 `config\plugins_config.json`**：该文件是**运行时状态**，不是源码。3 类创意插件的启停本就是灯光师的合法操作（REST `/api/plugins/toggle_enabled`），操作后 `plugin_host.set_plugin_enabled()` 会把状态持久化到这里。`test_aima53_boot_e2e.py` 的"交付基线：4 个创意插件全部启用"断言用于发现此类状态漂移。

> **已知边界**：原版应急备份 `D:\python项目文件\ai_lighting_system` 按用户要求**保持零改动**，因此它同时带有 4.2 节的 numpy 序列化缺陷**和** 4.5 节的 `.bat` 解释器选择缺陷。其余功能不受影响；如需修复请另行确认。

---

## 6. 生产发布打包流水线（v5.3 混合微内核架构整改）

### 6.1 原流水线在新内核架构下的六处致命缺口

原 `tools/build_release.py` 是按**旧内核（单体 Python 引擎）**语义编写的，在微内核架构下产出的包是残废的。审计结论：

| # | 缺口 | 后果 | 严重度 |
|---|---|---|---|
| 1 | 复制清单 `["config","knowledge_base","plugins","marketplace","deploy","backups"]` **不含 `bin/`** | 发布包无 `aima-rt-daemon`，启动即降级 | ⛔ 致命 |
| 2 | **不含 `aima_shm_sdk` ABI 扩展** | `import aima_shm_sdk` 失败 → `use_kernel_rt=False` → **实际运行旧内核行为**，且为静默降级 | ⛔ 致命 |
| 3 | `CORE_MODULES_TO_COMPILE` **不含 `kernel_bridge.py`** | 微内核共享内存 ABI 契约（slot 布局 / seqlock 协议）明文发布，核心 IP 泄露 | ⛔ 高 |
| 4 | 清单含**已失效模块** `artnet_controller.py`（实际名为 `artnet_sender.py`），且 `if os.path.exists(m)` **静默跳过** | 保护口径与实际文件集不一致，且不报错 | ⚠ 中 |
| 5 | 单个 `ai-ma.service`，**无 `aima-rt.service`**、无 `BindsTo`/`PartOf`、无 `CPUAffinity`/`SCHED_FIFO`/`LimitMEMLOCK` | 与新架构要求的双进程硬实时托管模型完全不符 | ⛔ 高 |
| 6 | 只有 Windows `.exe` 内核，`build_debian.sh` 只处理 Python/Cython | Debian 包无法产出 Linux ELF 微内核 | ⛔ 高 |

> 缺口 2 是最危险的：它会产出"**号称新内核版、实际跑旧内核**"的包，且界面与日志都不会报警。

### 6.2 整改内容

**A. 构建前置基线校验 (`validate_build_baseline`)**

任何缺项**立即 FATAL 中止**，绝不静默产出残废包：
* Cython 保护清单中每个模块必须真实存在（消除缺口 4 的静默跳过）；
* `aima_shm_sdk` ABI 扩展必须存在（消除缺口 2）；
* `bin/` 中必须有当前平台的 `aima-rt-daemon`（消除缺口 1）。

**B. 新内核构件打包 (`build_kernel_artifacts`)**

* `bin/` 全量同步，并设置 `0755` 可执行位（Debian 生效）；
* `aima_shm_sdk` ABI 扩展**双份放置**（包根 + `core/`），兼容不同 `sys.path` 布局；
* 说明：该扩展编译时启用了 **`abi3-py310` 稳定 ABI**（链接 `python3.dll` / Linux 不链接 libpython），因此**一个 `.so` 通吃 Python ≥ 3.10**，无需按版本重编。

**C. 核心保护清单修正**

* 新增 `kernel_bridge.py` → 微内核 ABI 契约纳入机器码编译与源码物理抹除；
* `artnet_controller.py` → `artnet_sender.py`。

**D. 双 systemd 单元生成**

* `aima-rt.service`：`CPUAffinity=3`、`CPUSchedulingPolicy=fifo`、`CPUSchedulingPriority=98`、`Nice=-20`、`LimitMEMLOCK=infinity`、`WatchdogSec=1s`、`ReadWritePaths=/dev/shm`；
* `ai-ma.service`：`Requires` + `BindsTo` + `PartOf=aima-rt.service`（**微内核停则控制台同步停**，杜绝"业务层还在跑但无人推流"的幽灵状态），并设置 `AIMA_RT_EXTERNAL=1`；
* 同步 `deploy/`，并清除包内旧语义的 `ai-lighting.service`。

**E. `build_debian.sh` 增加 Rust 构建段**

```
阶段一：核心 Python 模块 → Cython 机器码 (.so)，随后物理抹除源码
阶段二：Rust 硬实时微内核 → cargo build --release -p aima-rt-daemon -p aima-shm-sdk
        → install bin/aima-rt-daemon (0755)
        → install aima_shm_sdk.so (包根 + core/)
        → strip 剥离调试符号
终检：内核构件缺失则 exit 1
```

内核源码路径解析优先级：`$1` 参数 → `$AIMA_KERNEL_SRC` → `../ai-ma-kernel-v5.3` → `/opt/ai-ma-kernel-src/...` → `/usr/local/src/...`。若均未找到，则回退使用 `bin/` 中预置的交叉编译 ELF 并校验其存在性。

**F. 双内核争抢防护（新增，配套缺口 5）**

引入 systemd 托管后出现一个新风险：**systemd 拉起的微内核**与 **Python 自行伴生拉起的微内核**会同时存在，两个内核争抢同一组 `/dev/shm` 槽位。

`control_station.py` 新增两道防护：
1. `AIMA_RT_EXTERNAL=1`（由 `ai-ma.service` 注入）→ 直接跳过伴生拉起；
2. `_kernel_already_live()` 探针 → 两次采样 `frame_index`，若 44Hz 计数在增长即判定已有存活内核，直接**纳管**而非重复拉起。

**G. 产物完整性强校验 (`verify_release_package`)**

构建收尾自动校验：微内核二进制、ABI 扩展双份、双 systemd 单元、`build_debian.sh` 含 cargo 段且销毁清单完整覆盖保护清单、主入口与前端产物。任一缺失 → 构建失败。

**H. 版本与清单**

* `VERSION` 升至 `5.3.0`，新增 `kernel` 段描述内核参数（daemon / sdk / abi / 44Hz / 仲裁优先级 / 64 宇宙）；
* 输出 `RELEASE_MANIFEST.json` 记录保护清单、内核二进制、ABI 扩展落位、systemd 单元，供产线核验。

### 6.3 验证证据

**正向：`tests/test_release_package_integrity.py` → 35/35 PASS**

该测试不只是静态检查，而是**真实构建 + 真实启动发布包**：

| 阶段 | 内容 | 结果 |
|---|---|---|
| 一 | 真实运行 `tools/build_release.py` | exit=0 |
| 二 | 产物完整性强校验（23 项断言） | 全通过 |
| 三 | **真实启动发布包**：拉起微内核、挂载 abi3 扩展、进入 `v5.3_shm`、登录鉴权、三层隔离、遥测有效、退出后无孤儿 | 全通过 |

阶段三实测数据：`发布包成功拉起微内核伴生进程 PID=[9760]`、`进入 v5.3_shm 硬件卸载模式`、`frame_index=56 jitter_ns=230868`、`包退出后微内核被原子回收`。

**负向：fail-fast 守卫实测生效**

| 场景 | 预期 | 实测 |
|---|---|---|
| 抽走 `bin/aima-rt-daemon.exe` | 构建失败 | `[FATAL] bin/ 中未找到当前平台 (win32) 的必需微内核二进制` · 退出码 **1** |
| 抽走 `aima_shm_sdk.pyd` 双份 | 构建失败 | `[FATAL] 未找到 aima_shm_sdk ABI 扩展 (.pyd / .so)` · 退出码 **1** |

**回归**：`test_aima53_standalone_system.py` 4/4 PASS、`test_aima53_boot_e2e.py` 20/20 PASS。

---

## 7. 运行期内核看门狗（Runtime Kernel Watchdog）

### 7.1 缺陷的由来（一次真实事故）

原实现只在控制台**启动时**调用一次 `check_microkernel_health()`。这留下一个致命盲区：

> **微内核在运行期死亡，控制台完全不知道。**

后果链条：内核被外部杀死 / 被 OOM 回收 / 崩溃退出 → 控制台的 `engine._loop()` 仍以 44Hz 往 `/dev/shm` 写业务帧 → 但**没有任何进程消费这些帧、没有任何进程物理推流** → 现场黑屏 → 而系统日志里一条告警都没有。对一个"硬实时"系统而言，这是不可接受的静默失效。

该缺陷是在一次真实事故中被发现的：测试用例为"保证自身确定性"而执行了 `taskkill` 清理残留内核，**误杀了用户正在使用的控制台所拥有的内核**。事故本身是测试纪律问题（见 7.4），但它精准暴露了运行期无看门狗这一架构缺口。

### 7.2 看门狗设计

`control_station.py` 新增守护线程 `AimaKernelWatchdog`，以固定周期巡检：

| 巡检情形 | 判定依据 | 处理动作 |
|---|---|---|
| **A. 伴生进程死亡** | `_microkernel_proc.poll() is not None` | `ERR-KERNEL-DAEMON` 告警 → 自动重启（上限内） |
| **B. 帧计数停摆** | 进程存活但 `frame_index` 连续 N 次未推进 | `ERR-KERNEL-STALL` 告警 → 杀死并重启（上限内） |
| **C. 恢复正常** | `frame_index` 恢复递增 | 重置重启预算 `restart_count = 0` |

关键健壮性设计：
* **重启风暴防护**：连续重启超过 `KERNEL_MAX_AUTO_RESTART`（默认 5）次即停止自动重启，并输出 `CRITICAL` 引导排查 `logs/aima_rt_daemon.log`；
* **systemd 托管分支**：`AIMA_RT_EXTERNAL=1` 时重启责任归属 `aima-rt.service`（含 `WatchdogSec=1s`），看门狗转为只读巡检与告警，**绝不与 systemd 争抢重启权**；
* **异常隔离**：单次巡检异常被 `try/except` 捕获并记录，不影响主服务与后续巡检；
* **守护线程**：`daemon=True`，不会阻塞主服务退出；`stop_microkernel()` 先 `_watchdog_stop.set()` 再回收内核，杜绝退出时的重启竞态。

### 7.3 可调参数（环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| `AIMA_WATCHDOG_INTERVAL_SEC` | `5.0` | 巡检周期（秒） |
| `AIMA_WATCHDOG_MAX_RESTART` | `5` | 自动重启次数上限 |
| `AIMA_WATCHDOG_STALL_LIMIT` | `3` | 连续多少次帧计数未推进判定为停摆 |

### 7.4 测试纪律修正（重要）

本系统存在两处**全局单例资源**：`/dev/shm/aima_slot_*` 共享内存槽位、`9000` 端口。因此同一时刻只允许一个 AI-MA 实例运行。

原测试为"保证自身确定性"而执行 `taskkill` 清理残留内核，这会**误杀他人正在使用的会话**。已全部修正为**独占性前置检查**：

```
若检测到已有实例（微内核存活 或 9000 被占用）
    → 打印明确提示并 exit(2) 跳过
    → 绝不为了自身方便而杀死别人的进程
```

同时，孤儿回收断言从"全局无内核残留"改为"**本次测试新拉起的**内核无残留"，用启动前的 PID 快照做差集，不再评估或触碰测试前就存在的进程。

### 7.5 验证

`tests/test_kernel_watchdog.py` 真实复现故障并验证自愈：

| 阶段 | 内容 |
|---|---|
| 一 | 独占性前置检查（不越界） |
| 二 | 启动控制台，确认微内核伴生拉起、看门狗已启动 |
| 三 | **强制 `taskkill` 杀死微内核**，模拟运行期崩溃 |
| 四 | 等待巡检周期，断言新内核被自动拉起、日志含 `ERR-KERNEL-DAEMON` 与"微内核自动重启" |
| 五 | 静态接线核验（停摆检测 / 重启上限 / systemd 分支 / 守护线程 / 异常隔离 / 参数可调） |
| 六 | 关闭控制台，断言无孤儿进程 |

> 该测试与 `test_aima53_boot_e2e.py`、`test_release_package_integrity.py` 一样需要**独占环境**。若你正开着控制台，它会以退出码 2 礼貌跳过。

### 7.6 实测结果（17/17 PASS）

```
[阶段三] 强行杀死微内核，模拟运行期崩溃 / OOM / 外部误杀
    -> [PASS] 微内核已被强制杀死 (模拟故障) | victim PID=6656
[阶段四] 等待看门狗巡检周期并执行自愈
    -> [PASS] 看门狗自动拉起了新的微内核 (自愈成功) | 旧 PID=6656 -> 新 PID=[12712]
    -> [PASS] 看门狗记录了 ERR-KERNEL-DAEMON 故障码 |
              运行期巡检发现硬实时微内核已退出 (退出码 1)，业务层已失去物理推流能力！
    -> [PASS] 看门狗记录了自动重启动作 | 正在执行第 1/5 次微内核自动重启...
    -> [PASS] 自愈后微内核重新挂载共享内存驱动
```

### 7.7 一个值得记住的坑：日志增量读取必须用字节偏移

本测试第一版把 4 个断言误判为 FAIL，根因在**测试自身**：

```python
# 错误：os.path.getsize() 返回【字节】数，而 f.read() 返回【str】，
#       下标是【字符】索引。中文日志每汉字 3 字节，两者相差数倍，
#       按字符切片会直接跳过大段新增内容。
pre_len = os.path.getsize(LOG_FILE)
with open(LOG_FILE, encoding="utf-8") as f:
    new_text = f.read()[pre_len:]        # ← 跳过头，误判"看门狗没生效"

# 正确：以二进制模式按字节 seek
with open(LOG_FILE, "rb") as f:
    f.seek(pre_len)
    new_text = f.read().decode("utf-8", errors="replace")
```

看门狗功能本身一直是正常的（内核确实被自动拉回），是**测试的日志切片算错了偏移**。凡按增量读取中文日志的代码，都必须走字节路径。

---

## 8. 全量测试矩阵与准出结论

| 测试脚本 | 断言数 | 结果 | 独占要求 |
|---|---|---|---|
| `tests/test_aima53_standalone_system.py` | 4 | **PASS** | 否 |
| `tests/test_aima53_boot_e2e.py` | 20 | **PASS** | 是 |
| `tests/test_release_package_integrity.py` | 35 | **PASS** | 是 |
| `tests/test_kernel_watchdog.py` | 17 | **PASS** | 是 |
| **合计** | **76** | **全部通过** | |

准出结论：v5.3 混合硬实时微内核架构、发布打包流水线、运行期故障自愈三项能力均已通过真实进程 + 真实 HTTP + 真实构建的端到端验证，可用于生产交付。

---

## 9. 插件装载可观测性（用户界面隐匿 ≠ 运维不可见）

### 9.1 缺陷的由来

三层插件分级落地后，`/api/plugins/installed` 改为只返回 3 类，前端也移除了 1/2 类徽章。**这个改动本身是对的**，但配套的可观测性没跟上，导致一个严重问题：

> **1 类系统级与 2 类适配级插件到底"装载成功"还是"装载失败"，无从判断。**

原实现在日志里对所有插件使用**完全相同**的一行输出，且不含任何层级标识：

```
[INFO] [PluginHost] 插件 [Art-Net 3/4 工业标准协议驱动] (ID: protocol_artnet_standard) 加载完成，状态: [已启用]
[INFO] [PluginHost] 插件 [正弦曲线平滑呼吸律动宏]       (ID: macro_breathing)           加载完成，状态: [已启用]
```

两条日志长得一模一样——一条是**没有它就没有任何物理输出**的 1 类协议驱动，另一条是可有可无的 3 类呼吸律动。

### 9.2 更严重的静默盲区

原 `load_plugin_from_file()` 在**类发现阶段**有一个完全静默的返回路径：

```python
for attr_name in dir(mod):
    ...
    if (...):  # 找到插件类
        ...
        return instance
# 循环自然结束 —— 源文件里没有任何插件类，直接返回 None，一行日志都不留
```

若某个插件源文件导入成功却不含可实例化的插件类（改错基类、漏写类体、被误删），
**它会被彻底漏掉且查无实据**。对底座插件而言这是致命的。

### 9.3 改造内容

**A. 成功日志带层级标签**

```
[INFO] [PluginHost] [1类·系统级] 插件 [Art-Net 3/4 工业标准协议驱动] (ID: protocol_artnet_standard) 装载成功，状态: [已启用]
[INFO] [PluginHost] [2类·适配级] 插件 [GrandMA2/MA3 灯库资产适配器]  (ID: adapter_ma_fixture)        装载成功，状态: [已启用]
[INFO] [PluginHost] [3类·表现创意] 插件 [正弦曲线平滑呼吸律动宏]     (ID: macro_breathing)           装载成功，状态: [已启用]
```

**B. 启动时的分层装载总览**

```
======================= 插件生态装载总览 =======================
 【1类·系统级】 已装载 4/4  [OK]
      - protocol_artnet_standard         Art-Net 3/4 工业标准协议驱动  [已启用]
      - protocol_sacn_standard           sACN E1.31 协议驱动           [已启用]
      - llm_local_qwen_7b                Local Qwen 2.5-7B 端侧模型适配器 [已启用]
      - system_log_ai_repair             系统日志 AI 自愈              [已启用]
 【2类·适配级】 已装载 1/1  [OK]
      - adapter_ma_fixture               GrandMA2/MA3 灯库资产适配器  [已启用]
 【3类·表现创意】 已装载 4/4  [OK]
      - ...
----------------------------------------------------------------
 合计: 扫描 9 个源文件 | 装载成功 9 个 | 失败 0 个
 全部插件装载成功，无失败项。
==============================================================
```

失败时会额外输出 `!! N 个失败` 标记、逐条失败明细（层级 / 插件ID / 文件 / 失败阶段 / 原因），
以及底座插件失效的 `CRITICAL` 级严重告警。

**C. 四条失败路径全部显式登记**

| 失败阶段 | 触发条件 | 原行为 | 现行为 |
|---|---|---|---|
| `模块导入` | 语法错误、缺依赖、导入期抛异常 | ERROR（无层级） | 登记 + 按层级告警 |
| `类发现` | **文件里没有可实例化的插件类** | **完全静默** ⛔ | 登记 + 告警 |
| `合规校验` | ID 格式 / `get_info` 字段 / schema 不合规 | ERROR（无层级） | 登记 + 按层级告警 |
| `on_init()` | 插件自身初始化返回 False | WARNING（无层级） | 登记 + 按层级告警 |

**D. 底座插件失败走故障码**

1/2 类是系统底座（1 类缺 = 无物理推流，2 类缺 = 无法导入控台资产），
因此它们的失败走 `ERR-PLUGIN-FOUNDATION` **故障码 + ERROR 级**，
并额外触发 `CRITICAL` 级总告警；3 类失败仅记为普通错误。这一分级确保
"呼吸律动插件没起来"与"Art-Net 驱动没起来"在告警层面**不会同权重**。

**E. 管理员诊断接口（运维可见性通道）**

```
GET /api/plugins/diagnostics        (需 superadmin / admin 角色)
```

返回结构化的三层全量状态，使运维无需翻日志即可查证：

```json
{
  "scanned_files": 9,
  "loaded_total": 9,
  "failed_total": 0,
  "foundation_healthy": true,
  "by_tier": {
    "1类·系统级":  [ {"id": "...", "name": "...", "enabled": true, "protected": true}, ... ],
    "2类·适配级":  [ ... ],
    "3类·表现创意": [ ... ]
  },
  "failures": []
}
```

**设计原则**：三层分级是为了"**不让用户误操作**"，不是为了"**让运维看不见**"。
用户界面保持干净（只有 3 类），运维通过日志总览 + 诊断接口掌握全部三层。

**F. 补齐故障诊断知识库**

改造过程中发现 `ERROR_DIAGNOSTICS_DB` **漏收了 6 个在实际使用的故障码**，
导致告警显示为"未知系统异常"，完全失去诊断价值。已全部补齐：

| 故障码 | 补齐后的标题 |
|---|---|
| `ERR-KERNEL-DAEMON` | 硬实时微内核守护进程失联或异常退出 |
| `ERR-KERNEL-STALL` | 硬实时微内核时钟停摆（进程存活但帧计数不再推进） |
| `ERR-KERNEL-TELEMETRY` | 微内核遥测数据读取或序列化失败 |
| `ERR-PLUGIN-FOUNDATION` | 系统底座插件（1 类系统级 / 2 类适配级）装载失败 |
| `ERR-KB-WRITE` | RAG 知识库写入或删除失败 |
| `ERR-ADAPTER-IMPORT` | 外部控台灯库资产导入失败 |

每个条目都给出了具体的**可能原因**与**建议排查步骤**，而非泛泛而谈。

### 9.4 验证

`tests/test_plugin_observability.py`（31/31 PASS）——**进程内自包含，不占用 9000 端口、不触碰微内核**，
因此可以在控制台正在运行时安全执行。它在临时目录构造合成插件，
覆盖 4 类失败路径 + 4 个正常插件，断言分层计数、失败登记、故障码、诊断报告结构。

`tests/test_aima53_boot_e2e.py` 新增 6b 阶段（真实服务）：诊断接口三层分组、
底座健康、零失败、3 类计数与用户界面一致、匿名访问返回 401。

### 9.5 又一个测试夹具的坑

本测试第一版 8 个合成插件**全部在"类发现"阶段失败**——因为夹具漏实现了抽象方法。
`BasePlugin` 声明了 4 个抽象方法，少一个类就保持抽象而被正确拒收：

| 基类 | 必须实现的抽象方法 |
|---|---|
| `BasePlugin`（所有插件的根） | `get_info` · `on_init` · `on_enable` · `on_disable` |
| `BaseAdapterPlugin`（2 类） | 上述 4 个 **+** `supported_extensions` · `convert_to_profile` |
| `BaseProtocolPlugin`（1 类） | 上述 4 个 **+** `send_universe` |
| `BaseLLMPlugin`（1 类） | 上述 4 个 **+** `chat_completion` |
| `BaseMacroPlugin`（3 类） | 上述 4 个 **+** `render` |
| `BasePerceptionPlugin`（3 类） | 上述 4 个 **+** `get_status` |

这次的失败**恰恰证明了插件宿主的类发现逻辑是正确的**——它没有放过抽象类。

---

## 10. 最终全量测试矩阵

| 测试脚本 | 断言数 | 结果 | 需独占端口 |
|---|---|---|---|
| `tests/test_aima53_standalone_system.py` | 4 | **PASS** | 否 |
| `tests/test_plugin_observability.py` | 31 | **PASS** | 否（进程内自包含） |
| `tests/test_auth_noise_suppression.py` | 28 | **PASS** | 是 |
| `tests/test_aima53_boot_e2e.py` | 32 | **PASS** | 是 |
| `tests/test_kernel_watchdog.py` | 17 | **PASS** | 是 |
| `tests/test_release_package_integrity.py` | 35 | **PASS** | 是 |
| **合计** | **147** | **全部通过** | |

> 需要独占端口的 4 套测试均带**独占性前置检查**：检测到已有实例在运行即以退出码 2 礼貌跳过，
> 绝不为了自身方便而杀死用户正在使用的进程（该纪律源于第 7.4 节记录的一次真实事故）。

---

## 11. 鉴权噪音抑制与安全信号保真

### 11.1 现象

用户主动注销后，日志出现如下内容——4 条注销记录，紧接着 4 条 **ERROR 级故障告警**：

```
INFO  用户已主动注销会话凭证。
INFO  用户已主动注销会话凭证。
INFO  用户已主动注销会话凭证。
INFO  用户已主动注销会话凭证。
ERROR 【故障告警 - 代码 ERR-AUTH-DENIED】: 未授权只读接口访问被拒绝: /api/logs/stream
ERROR 【故障告警 - 代码 ERR-AUTH-DENIED】: 未授权只读接口访问被拒绝: /api/alarms
ERROR 【故障告警 - 代码 ERR-AUTH-DENIED】: 未授权只读接口访问被拒绝: /api/system/status
ERROR 【故障告警 - 代码 ERR-AUTH-DENIED】: 未授权只读接口访问被拒绝: /api/dmx/universe/0
```

### 11.2 根因（三方缺陷叠加）

| # | 位置 | 缺陷 | 后果 |
|---|---|---|---|
| ① | 前端 `forceLogout()` | **无幂等闩锁**。任一 401 都会再次调用 `forceLogout()`，而页面存在 5 个轮询定时器 | 一次点击注销 → **多次**注销请求（那 4 条重复记录的来源） |
| ② | 前端 `setInterval` | 定时器句柄从不保存、从不 `clearInterval` | 注销后页面卸载前轮询仍在继续，自己打自己 |
| ③ | 后端鉴权闸门 | 把"未携带令牌 / 令牌已吊销"**一律**记为 ERROR 级 `ERR-AUTH-DENIED` 故障告警 | 日志刷屏、**告警面板污染**、**告警文案错误** |

缺陷 ③ 的后果**不是噪音，而是安全性下降**：

> 真正的会话令牌爆破与一次日常注销，在告警面板上完全无法区分。

同时告警文案本身是错的——它说"需要更高的特权角色等级（当前为观察员），请切换为管理员账号"，而真因是"用户已注销，令牌已吊销，前端应停止轮询"。运维会照着错误的建议去排查。

### 11.3 修复

**A. 后端：未授权访问分级判定（`note_unauthenticated_request`）**

| 情形 | 级别 | 是否告警 | 理由 |
|---|---|---|---|
| 未携带令牌 | `DEBUG` | 否 | 未登录 / 刚注销的页面轮询，属正常生命周期 |
| 携带但已失效令牌 | `INFO` | 否 | 会话过期或注销竞态 |
| 窗口内高频未授权 | **`ERR-AUTH-BRUTEFORCE`** | **是** | 这才是真正可疑的信号 |
| 令牌有效但权限不足 | **`ERR-AUTH-DENIED`** | **是** | 真实授权事件 |

突发检测参数：窗口 10 秒、阈值 20 次、告警冷却 30 秒（防止告警自身刷屏）。

正常注销只会在亚秒级内产生个位数请求，与阈值（10 秒 20 次）有数量级差距，
因此**既消除了噪音，又完整保留了安全可见性**。

**B. 后端：故障码语义拆分**

`ERR-AUTH-DENIED` 原本被三种完全不同的情况混用，现拆分为三个独立、文案准确的码：

| 故障码 | 语义 |
|---|---|
| `ERR-AUTH-DENIED` | 令牌有效但权限不足（真实授权拒绝） |
| `ERR-AUTH-LOGIN-FAIL` | 登录时账号或密码校验未通过 |
| `ERR-AUTH-BRUTEFORCE` | 疑似令牌爆破或异常客户端扫描 |

**C. 前端：幂等闩锁 + 定时器可清理**

```js
var LOGGING_OUT = false;
var POLL_TIMERS = [];
function poll(fn, ms) { POLL_TIMERS.push(setInterval(fn, ms)); }
function stopAllPolling() {
  for (var i = 0; i < POLL_TIMERS.length; i++) { clearInterval(POLL_TIMERS[i]); }
  POLL_TIMERS = [];
}
async function forceLogout(msg) {
  if (LOGGING_OUT) { return; }   // 并发 401 不再重复触发注销
  LOGGING_OUT = true;
  stopAllPolling();              // 先停轮询，杜绝注销过程中的自我请求
  ...
}
```

5 个轮询定时器全部改经 `poll()` 登记，使注销可一次性全部清除。
401 处理逻辑**保留不动**——它仍是会话失效的安全兜底，只是不再自我放大。

### 11.4 验证

`tests/test_auth_noise_suppression.py` 真实还原该场景：

| 阶段 | 内容 |
|---|---|
| 一 | 登录 → 携带令牌轮询（200）→ 注销 → 用已吊销令牌重复轮询（401）→ 断言日志**零** `ERR-AUTH-DENIED`，且出现 INFO 级说明 |
| 二 | 30 次高频无令牌请求 → 断言触发 `ERR-AUTH-BRUTEFORCE`（安全信号未削弱），且冷却生效不刷屏 |
| 三 | 错误密码登录 → 断言仍触发 `ERR-AUTH-LOGIN-FAIL`（真实安全事件仍告警） |
| 四 | 前端静态核验：幂等闩锁、`stopAllPolling`、`poll()` 登记数、无裸 `setInterval` |

### 11.5 一条通用的设计教训

> **"记录失败"和"升级为告警"是两回事。**
> 每一次未授权访问都值得**留痕**（DEBUG/INFO），但只有**偏离正常基线的模式**才值得**告警**。
> 把所有 401 都变成 ERROR 告警，等于把告警面板变成垃圾桶——
> 真正需要被看见的攻击会淹没在日常噪音里。

这一条同样适用于其他高频路径：日志轮询、心跳探测、遥测拉取。








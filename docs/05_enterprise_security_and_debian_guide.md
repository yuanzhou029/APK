# 《AI-MA 生产级安全加固、RBAC 权限体系、中文诊断日志与 Debian 部署规范》

**版本**: v5.3（混合硬实时微内核架构 · As-Built 实装口径）
**状态**: 生产标准已确立 · 架构冻结
**目标操作系统**: Debian 12/13 (Linux 64-bit) + PREEMPT_RT / Windows 混合开发环境
**替代关系**: 本文件取代 v2.1-Enterprise 同名文档。角色常量、权限映射、故障码与 systemd 单元
均取自 `core/auth_manager.py`、`core/diagnostics_logger.py`、`tools/build_release.py` 实装源码。

---

## 0. 本版修订说明（v2.1 → v5.3）

| 项目 | v2.1 文档旧口径 | v5.3 实装口径 |
| --- | --- | --- |
| 角色数量 | 3 个（Admin / Engineer / Viewer） | **4 个**（**新增 `SUPERADMIN`**，即 root 底层维护者） |
| 角色常量名 | 未给出 | `Role.SUPERADMIN` / `ADMIN` / `ENGINEER` / `VIEWER` |
| 权限模型 | 文字描述"权限等级 L1/L2/L3" | **9 项显式权限字符串**，`SUPERADMIN` 具全权穿透 |
| 心跳频率 | "30Hz 心跳引擎" | **44Hz 为 Rust 微内核物理推流节奏**；`engine.py` 的 Python 侧 `fps` 默认 **30** |
| 故障码数量 | 5 个 | **14 个**（`ERROR_DIAGNOSTICS_DB` 全量登记） |
| 鉴权噪音策略 | 无（每次 401 都记 ERROR） | **分级判定**（DEBUG/INFO/ERROR），防告警脱敏 |
| systemd 单元 | 单个 `ai-lighting.service` | **双单元** `aima-rt.service` + `ai-ma.service`（`BindsTo` 强绑定） |
| 部署路径 | 未明确 | `/opt/ai-ma` |
| 运行用户 | 建议非 root 的 `lighting` 用户 + setcap | **实装单元为 `User=root`**（见 §7.2 说明与差异） |
| 编译加固 | 描述 Stage 1/2/3 | 实装为 `tools/build_release.py`：前端 AST 混淆 + Cython 机器码编译 + 发布清单 |

---

## 1. 安全加固与知识产权架构

本系统采用「**外放内敛、分级加固**」战略：

```text
┌────────────────────────────────────────────────────────────┐
│ 外部开放层（明文，赋能第三方）                                │
│   plugins/  ·  knowledge_base/  ·  config/  ·  marketplace/ │
└───────────────────────┬────────────────────────────────────┘
                        │ 通过抽象接口隔离
┌───────────────────────▼────────────────────────────────────┐
│ 核心保护层（编译加固）                                        │
│   core/ 业务微内核（仲裁、引擎、桥接、鉴权、备份、市场服务）    │
│   control_station.py 主入口                                  │
│   ├─ Stage 1  前端全量无断点 AST 混淆 + 字符串池加密           │
│   ├─ Stage 2  Cython 编译为 .so 机器码，物理抹除 .py 源码      │
│   └─ Stage 3  发布清单 RELEASE_MANIFEST.json（构件与校验摘要） │
└────────────────────────────────────────────────────────────┘
```

### 1.1 编译加固范围

由 `tools/build_release.py` 的 `CORE_MODULES_TO_COMPILE` 常量定义，**共 8 个模块**：

| 序号 | 模块 | 保护目标 |
| ---: | --- | --- |
| 1 | `dmx_merger.py` | 四级仲裁状态机与物理安全掩码 |
| 2 | `engine.py` | 业务主循环与 Crossfade 插值器 |
| 3 | `kernel_bridge.py` | 微内核零拷贝桥接 |
| 4 | `auth_manager.py` | RBAC 鉴权与 root 动态 Key |
| 5 | `artnet_sender.py` | Art-Net 发送器 |
| 6 | `node_discovery.py` | 节点发现与掉线看门狗 |
| 7 | `backup_manager.py` | 容灾备份与 SHA-256 快照校验 |
| 8 | `marketplace_service.py` | 插件市场服务 |

> **注意**：早期文档写作 `artnet_controller.py`（该文件**不存在**），且漏列
> `kernel_bridge.py` 与 `marketplace_service.py`。以上清单已与代码逐一对齐。

### 1.2 保持开放的生态资产

| 目录 | 理由 |
| --- | --- |
| `plugins/` | 允许用户与第三方查看源码、调试并扩展插件 |
| `knowledge_base/` | 纯 JSON 数据资产，运维人员需随时修改维护 |
| `config/` | 现场配置（用户、插件启停、快捷场景、面板布局） |
| `marketplace/` | 插件市场包索引 |
| `deploy/` | 部署工件，便于现场核查 |
| `backups/` | 容灾快照与用户备份 |

---

## 2. RBAC 用户角色与鉴权体系

基于 **PBKDF2-HMAC-SHA256** 加盐密码哈希 + **UUID 会话 Token**（默认有效期 **24 小时**）。

### 2.1 角色定义（实装 4 个）

```python
class Role:
    SUPERADMIN = "superadmin"   # 系统超级维护者（root，最高底层权限）
    ADMIN      = "admin"        # 系统主管理员（全权控制、知识库与插件运维、用户管理）
    ENGINEER   = "engineer"     # 主控灯光师（可调光、控场、编排、修改预设）
    VIEWER     = "viewer"       # 现场观察员（只读看板、日志与 DMX 监视）
```

> **出厂默认账号**（首次启动自动创建，见 `AuthManager._load_users`）：
> `root`（superadmin，**密码为随机 UUID，不可用密码登录，只能通过动态应急 Key 激活**）、
> `admin`（admin，默认密码 `admin123`）、`engineer`（engineer，默认密码 `123456`）、
> `guest`（viewer，默认密码 `guest`）。
>
> ⚠ **首次部署必须立刻修改 `admin` / `engineer` / `guest` 的默认密码。**

### 2.2 权限矩阵（`ROLE_PERMISSIONS` · 实装 9 项权限）

| 权限 | SUPERADMIN | ADMIN | ENGINEER | VIEWER |
| --- | :---: | :---: | :---: | :---: |
| `manage_users` 用户管理 | ✅ | ✅ | — | — |
| `manage_backups` 备份管理 | ✅ | ✅ | ✅ | — |
| `view_dashboard` 查看看板 | ✅ | ✅ | ✅ | ✅ |
| `operate_lights` 控光操作 | ✅ | ✅ | ✅ | — |
| `edit_kb` 知识库编辑 | ✅ | ✅ | ✅ | — |
| `panic_control` 紧急熔断 | ✅ | ✅ | ✅ | — |
| `manage_plugins` 插件管理 | ✅ | ✅ | — | — |
| `system_config` 系统配置 | ✅ | ✅ | — | — |
| `view_logs` 查看日志 | ✅ | ✅ | ✅ | ✅ |

### 2.3 鉴权校验逻辑

```python
def check_permission(self, token: str, required_perm: str) -> bool:
    session = self.verify_token(token)
    if not session:
        return False
    # 超级管理员具有全权穿透权限
    if session.get("role") == Role.SUPERADMIN:
        return True
    perms = session.get("permissions", [])
    return required_perm in perms
```

> **要点**：`SUPERADMIN` 是**硬编码穿透**，不读权限列表。这意味着即使 `ROLE_PERMISSIONS`
> 被误改，root 仍保有全部权限——这是有意的"最后一道保险"，避免权限配置错误把系统锁死。

### 2.4 会话令牌

| 项目 | 实装值 |
| --- | --- |
| Token 格式 | `token_<uuid4 hex>`（root 应急会话为 `root_emerg_<uuid4 hex>`） |
| 有效期 | `session_ttl_sec = 24 * 3600`（24 小时） |
| 传输方式 | `Authorization: Bearer <token>` 请求头，或 `HttpOnly` 会话 Cookie |
| Cookie 属性 | `Path=/; HttpOnly; SameSite=Strict` |
| 注销 | `POST /api/auth/logout`，令牌立即失效 |

---

## 3. 鉴权噪音抑制（v5.3 关键安全改进）

**问题**：曾把每一次 401 都记为 ERROR 级 `ERR-AUTH-DENIED` 故障告警。前端有 5 个轮询定时器，
用户正常注销后在途请求陆续收到 401，一次注销产生数十条 ERROR 告警。
后果**不是噪音问题，而是安全性下降**——真正的令牌爆破与一次日常注销在告警面板上无法区分，
运维人员很快对告警脱敏。

**修复**：改为分级判定。

| 情形 | 日志级别 | 是否告警 |
| --- | --- | --- |
| 未携带会话令牌（未登录或刚注销的页面轮询） | `DEBUG` | 否（DEBUG 低于持久化级别 INFO，不落盘） |
| 携带但已失效的令牌（会话过期、注销竞态） | `INFO` | 否 |
| 10 秒内超过 **20 次**未授权访问 | `ERROR` | 是，`ERR-AUTH-BRUTEFORCE`（**30 秒冷却**防告警自身刷屏） |
| 登录账号或密码错误 | `ERROR` | 是，`ERR-AUTH-LOGIN-FAIL` |
| 令牌有效但权限不足 | `ERROR` | 是，`ERR-AUTH-DENIED`（真实授权事件） |

判定参数（`control_station.py` 模块级常量）：

| 常量 | 默认值 | 含义 |
| --- | ---: | --- |
| `_UNAUTH_WINDOW_SEC` | 10.0 | 暴破判定时间窗（秒） |
| `_UNAUTH_BURST_THRESHOLD` | 20 | 窗口内触发告警的访问次数 |
| `_UNAUTH_ALARM_COOLDOWN_SEC` | 30.0 | 告警冷却（秒） |

**配套前端修复**：`forceLogout()` 增加幂等闩锁（并发 401 不再重复触发注销）；
5 个轮询定时器统一经 `poll()` 登记，注销瞬间由 `stopAllPolling()` 一次性清除。

---

## 4. 全链路中文结构化日志与故障诊断

### 4.1 日志输出规范

| 目标 | 说明 |
| --- | --- |
| **终端输出 (stdout)** | 彩色清晰中文日志，供现场实施人员查看 |
| **持久化文件 (`logs/`)** | 按大小自动轮转（`RotatingFileHandler`） |
| **Web 实时流（内存环形缓冲）** | 总控台无刷新实时推流，含过滤与级别搜索 |

> **级别纪律**：所有诊断码 handler 均设为 `setLevel(logging.INFO)`，
> 因此 **DEBUG 级日志不会落盘**。这是 §3 分级策略能生效的技术前提——
> 无令牌访问记 DEBUG 就意味着"留痕但不污染告警面板"。

### 4.2 故障码知识库（`ERROR_DIAGNOSTICS_DB` · 实装 14 个）

**未登记知识库的故障码会在日志中显示为「未知系统异常」，因此新增故障码时必须同步登记知识库。**

| 故障码 | 名称 | 触发机理 | 处置要点 |
| --- | --- | --- | --- |
| `ERR-NET-6454` | Art-Net 通信端口绑定失败 | UDP 6454 被其他控台软件占用，或缺少绑定特权 | `sudo lsof -i :6454` 查占用；必要时 `setcap` |
| `ERR-LLM-CONN` | 大模型端点连接超时或服务离线 | 本地推理服务未启动，或防火墙阻止 | 确认端点在线；浏览器测试 `/v1/models` |
| `ERR-DMX-OVERFLOW` | DMX 通道地址越界溢出 | 起始地址 + 通道数 > 512 | 重排起始地址或迁移至下一个 Universe |
| `ERR-AUTH-DENIED` | 安全鉴权被拒绝（令牌有效但权限不足） | 当前角色不具备所需权限 | 切换为具备权限的账号 |
| `ERR-AUTH-LOGIN-FAIL` | 登录鉴权失败 | 账号不存在或密码不匹配 | 确认账号密码；关注是否伴随暴破告警 |
| `ERR-AUTH-BRUTEFORCE` | 疑似会话令牌爆破或异常扫描 | 短时大量未授权访问，远超正常轮询频率 | 先排除正常注销在途轮询；判定恶意则网络层封禁 |
| `ERR-MASK-TRIP` | 物理安全掩码触发硬件熔断 | 向 `is_safe:false` 的危险通道写入非安全值 | 系统已自动归零；如需开放须改灯库 `is_safe` |
| `ERR-NODE-OFFLINE` | Art-Net 解码器节点掉线 | 心跳超阈值未上报 | 查电源链路；确认存活判据设置 |
| `ERR-KERNEL-DAEMON` | 硬实时微内核失联或异常退出 | 内核进程被杀死、OOM、二进制缺失或 ABI 不匹配 | 查 `logs/aima_rt_daemon.log`；确认 `bin/aima-rt-daemon` |
| `ERR-KERNEL-STALL` | 微内核时钟停摆（进程存活但帧计数不推进） | 主线程阻塞/死锁、CPU 核心被抢占、内存换页 | 查核心占用；确认 `isolcpus/nohz_full` 与 `LimitMEMLOCK` |
| `ERR-KERNEL-TELEMETRY` | 微内核遥测读取或序列化失败 | 共享内存未初始化、结构体布局不一致、numpy 标量未转原生类型 | 确认内核已启动；确认 SDK 与内核版本一致 |
| `ERR-PLUGIN-FOUNDATION` | 系统底座插件（1/2 类）装载失败 | 语法错误、缺依赖、未过合规校验、`on_init` 返回 False | 查启动日志「插件生态装载总览」或 `/api/plugins/diagnostics` |
| `ERR-KB-WRITE` | RAG 知识库写入或删除失败 | 目录无写权限、JSON 被占用、磁盘不足、结构不合规 | 检查 `knowledge_base/` 权限与磁盘空间 |
| `ERR-ADAPTER-IMPORT` | 外部控台灯库资产导入失败 | 格式不受支持的适配器处理，或适配器未启用 | 确认 2 类适配器已启用；校验源文件格式 |

---

## 5. Debian 生产部署

### 5.1 双 systemd 单元（v5.3 架构要求）

系统由**两个独立单元**组成，存在强绑定关系。单元内容由 `tools/build_release.py`
统一生成（`AIMA_RT_SERVICE` / `AI_MA_SERVICE` 模板常量），同时输出到发布包根目录与 `deploy/`。

**单元 1：`aima-rt.service`（硬实时微内核，必须最先启动）**

| 配置项 | 值 | 作用 |
| --- | --- | --- |
| `Type` | `simple` | — |
| `Before` | `ai-ma.service` | 保证微内核先于业务层启动 |
| `ExecStart` | `/opt/ai-ma/bin/aima-rt-daemon` | — |
| `CPUAffinity` | `3` | 绑定 CPU Core 3 |
| `CPUSchedulingPolicy` | `fifo` | SCHED_FIFO 实时调度 |
| `CPUSchedulingPriority` | `98` | 实时优先级 98 |
| `Nice` | `-20` | 最高调度权重 |
| `IOSchedulingClass` | `realtime` | 实时 IO 调度类 |
| `IOSchedulingPriority` | `0` | IO 最高优先级 |
| `LimitMEMLOCK` | `infinity` | 锁定全部内存页，杜绝换页抖动 |
| `LimitNOFILE` | `65535` | — |
| `WatchdogSec` | `1s` | 秒级心跳守护 |
| `ReadWritePaths` | `/dev/shm` | 共享内存必须可读写 |
| `NoNewPrivileges` | `true` | 沙箱加固 |
| `ProtectHome` / `ProtectKernelTunables` | `true` | 沙箱加固 |
| `PrivateTmp` | `false` | 保持 tmp 可见 |

**单元 2：`ai-ma.service`（Python 业务控制台）**

| 配置项 | 值 | 作用 |
| --- | --- | --- |
| `Requires` / `BindsTo` / `PartOf` | `aima-rt.service` | 内核停则控制台停，重启联动 |
| `Environment` | `AIMA_RT_EXTERNAL=1` | **告知 Python 层微内核已由 systemd 托管** |
| `ExecStart` | `/usr/bin/python3 /opt/ai-ma/control_station.py` | — |
| `Restart` / `RestartSec` | `always` / `3s` | 崩溃自动拉起 |
| `TimeoutStopSec` | `10s` | 优雅停机窗口 |
| `ProtectSystem` | `full` | 根文件系统只读 |
| `NoNewPrivileges` / `ProtectHome` | `true` | 沙箱加固 |

> **⚠ 致命陷阱**：`AIMA_RT_EXTERNAL=1` 必须设置。若 Python 层不知道微内核已由 systemd 托管，
> 它会自行再拉起一个微内核进程，**两个内核争抢同一组 `/dev/shm` 槽位**，
> 将造成灾难性的数据错乱与随机闪灯。

### 5.2 部署命令（顺序不可颠倒）

```bash
sudo cp aima-rt.service ai-ma.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now aima-rt.service    # 微内核先行
sudo systemctl enable --now ai-ma.service
sudo systemctl status aima-rt.service ai-ma.service
```

### 5.3 PREEMPT_RT 内核参数（保证抖动 < 100µs）

```text
GRUB_CMDLINE_LINUX_DEFAULT="isolcpus=domain,managed_irq,3 nohz_full=3 rcu_nocbs=3 irqaffinity=0-2 max_cstate=0"
```

| 参数 | 作用 |
| --- | --- |
| `isolcpus=domain,managed_irq,3` | 隔离 Core 3，并把硬件中断（IRQ）移离该核 |
| `nohz_full=3` | 关闭 Core 3 的时钟滴答中断，消除操作系统自身抖动 |
| `rcu_nocbs=3` | 把 RCU 软中断回调移出 Core 3 |
| `irqaffinity=0-2` | 所有硬件中断绑定到 Core 0–2 |
| `max_cstate=0` | 禁用 CPU 节能降频，保持最高标称频率 |

> 未配置上述参数时微内核仍可运行，但**抖动无法保证在 100µs 以内**，
> 高负载场景下可能出现可见闪烁。交付前请用 `cat /proc/cmdline` 核验。

### 5.4 路径与权限规范

1. **路径规范**：所有路径处理使用 `os.path`，不硬编码 Windows 反斜杠或盘符。
2. **安装根目录**：`INSTALL_ROOT = /opt/ai-ma`。
3. **共享内存目录**：两个单元均声明 `ReadWritePaths=/dev/shm`。
4. **低特权端口**：若需以非 root 绑定 UDP 6454 或 HTTP 端口，通过 Linux Capabilities 授权：
   `sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3`
   （**注意**：实装单元以 `User=root` 运行，见 §5.5）

### 5.5 ⚠ 已知差异：实装单元以 root 运行

`build_release.py` 生成的**两个单元均为 `User=root`**，与本节早期建议的
"以专用普通用户运行、绝不使用 root"存在差异。原因与取舍：

| 方面 | 说明 |
| --- | --- |
| 微内核为何需要 root | `SCHED_FIFO` 优先级 98、`mlockall` 锁页、`CPUAffinity` 绑定隔离核心，均需要 `CAP_SYS_NICE` / `CAP_IPC_LOCK` 等特权。生产上更稳妥的做法是给非 root 用户授予精确 capability 并设置 `AmbientCapabilities` |
| 业务层为何仍为 root | 需读取 `/dev/shm` 共享内存、访问 `/opt/ai-ma` 全量文件 |
| 沙箱缓解 | 两个单元均已启用 `NoNewPrivileges=true`、`ProtectHome=true`、`ProtectSystem=full`（业务单元）、`ProtectKernelTunables=true`（微内核单元），限制了提权与文件系统影响面 |
| **建议** | 若合规要求禁止 root 运行，需改造单元为专用用户 + `AmbientCapabilities=CAP_SYS_NICE CAP_IPC_LOCK`，并同步调整 `/dev/shm` 属主与 `plugins/`、`knowledge_base/`、`logs/` 目录权限。此项属**待评估改造**，尚未实装 |

---

## 6. Windows 混合开发环境

| 差异点 | Windows | Debian |
| --- | --- | --- |
| 微内核二进制 | `bin/aima-rt-daemon.exe` | `bin/aima-rt-daemon`（无后缀） |
| 原生扩展 | `aima_shm_sdk.pyd`（由 `.dll` 改名） | `libaima_shm_sdk.so` |
| 共享内存 | 由 SDK 内部实现（`/dev/shm` 语义由扩展层屏蔽） | 真实 `/dev/shm/*` |
| 实时调度 | **不支持** SCHED_FIFO / CPU 亲和性隔离 | 完整支持 |
| 部署 | 直接运行 `启动系统总控台.bat` | systemd 双单元 |

> **重要**：Windows 上**不具备硬实时保证**，抖动无法达到 100µs 量级。
> Windows 仅用于开发与功能验证；生产部署必须使用 Debian + PREEMPT_RT。
> `.bat` 文件必须保持 **ASCII-only**，否则简体中文 cmd.exe 会解析失败。

---

## 7. 安全注意事项汇总（交付前逐条确认）

| # | 事项 | 检查方式 |
| --- | --- | --- |
| 1 | **修改全部默认密码**（`admin123` / `123456` / `guest`） | `config/users.json` 中确认密码哈希非默认 |
| 2 | 确认 `root` 账号**无可用密码**，仅能通过动态应急 Key 激活 | `password_hash` 由随机 UUID 派生 |
| 3 | `AIMA_RT_EXTERNAL=1` 已设置，无双内核风险 | `systemctl cat ai-ma.service` |
| 4 | 仅 3 类插件出现在用户界面 | `GET /api/plugins/installed` 中无 1/2 类 id |
| 5 | 危险通道 `is_safe: false` 未被误改为 `true` | 逐个灯库 profile 核对 |
| 6 | `PANIC` 级调用方权限受控（唯一能写危险通道的通道） | 审查 `/api/lighting/panic` 的 RBAC |
| 7 | `NoNewPrivileges` / `ProtectHome` / `ProtectSystem` 未被放宽 | `systemctl cat` 两个单元 |
| 8 | 用 `cat /proc/cmdline` 确认 PREEMPT_RT 隔离参数已生效 | 缺参数则抖动无保证 |
| 9 | `knowledge_base/`、`config/`、`backups/` 权限最小化 | 仅运行用户可写 |
| 10 | 新增故障码已同步登记 `ERROR_DIAGNOSTICS_DB` | 否则日志显示「未知系统异常」 |

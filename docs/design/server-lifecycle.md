# 设计文档：OpenCode Server 生命周期管理

> **适用范围**：`witty` CLI 对 `opencode serve` 的自动启动、检测、发现与安全隔离

---

## 1. 背景与动机

### 1.1 当前问题

当前 `witty` 依赖用户**提前手动启动** `opencode serve --port 4096`。这带来三个体验问题：

1. **两步操作**：用户必须先启动 server，再使用 `witty ask`，认知负担重。
2. **终端关闭后失效**：终端退出后 server 仍然运行，用户下次启动 `witty` 时不知道"我的 server 还在不在"。
3. **错误提示不友好**：当前 hint 是 `ensure 'opencode serve --port 4096' is running and reachable`，对人不友好。

### 1.2 目标

- **自动启动**：`witty` 首次使用时自动启动 `opencode serve`，无需用户手动操作。
- **自动检测**：`witty` 启动时自动检测是否已有可用 server，优先复用。
- **跨会话复用**：`witty` 退出后 server 继续运行，下次启动 `witty` 时无缝复用。
- **多用户隔离**：同一台 openEuler 服务器上，不同用户的 server 互相隔离，无法互相访问。
- **安全可控**：用户可以通过配置关闭自动启动，保持向后兼容。

---

## 2. 调研结论

### 2.1 OpenCode 不具备 Server 发现能力

经过对 OpenCode CLI（v1.17.9）、SQLite 数据库（`opencode.db`）、OpenAPI 端点、mDNS 机制的全面调查：

| 机制 | 是否存在 | 结论 |
| ---- | -------- | ---- |
| `opencode list` / `opencode servers` 命令 | ❌ | 不存在 |
| `/global/*` REST 端点（list instances） | ❌ | 只有 health/event/config/dispose/upgrade |
| SQLite 数据库 server 表 | ❌ | 只有 session/message/project 等业务表 |
| PID 文件 | ❌ | 不写任何 pidfile |
| mDNS 服务发现 | ⚠️ | `--mdns` flag 存在，但需要 avahi-daemon（openEuler 默认不安装），且要求 hostname≠127.0.0.1 |

**结论：Witty 必须自己实现 Server 发现和生命周期管理。**

### 2.2 业界先例：`opencode-mcp`

社区 `opencode-mcp`（如 [AlaeddineMessadi/opencode-mcp](https://github.com/AlaeddineMessadi/opencode-mcp)）已经做到了自动启动，但它们的实现路径与 Witty 不同：

- **探测机制相同**：启动时 probing `OPENCODE_BASE_URL/global/health`，可达则复用。
- **启动方式不同**：不可达时通过 `@opencode-ai/sdk` 的 `createOpencodeServer()` **进程内启动** HTTP server——不 spawn 独立子进程，不依赖 `opencode` 二进制。
- **Witty 的差异**：Witty 是 Go 项目，无法直接使用 TypeScript SDK。因此 Witty 采用 `os/exec` spawn `opencode serve` 子进程的方式——这是 Go 生态下等效且合理的替代方案。

---

## 3. 整体设计

### 3.1 核心状态文件

```text
~/.config/witty/
├── config.toml           # 用户配置
├── server-state.json     # Server 状态（权限 0600）  ← 新增
└── session.json          # 当前 session 状态
```

**`server-state.json` 结构**：

```json
{
  "port": 4097,
  "password": "f1a8b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
  "pid": 12345,
  "started_at": "2026-06-24T10:30:00+08:00",
  "last_used": "2026-06-24T10:45:00+08:00"
}
```

| 字段 | 用途 |
| ---- | ---- |
| `port` | Server 实际监听端口 |
| `password` | HTTP Basic Auth 密码（`OPENCODE_SERVER_PASSWORD`） |
| `pid` | OS 进程 ID，快速判断进程存活 |
| `started_at` | 调试/诊断用 |
| `last_used` | 可选：用于 idle timeout 清理（暂不实现） |

### 3.2 密码的双重作用

`password` 不仅是安全措施，也是**身份识别**机制：

```text
B 的 witty 启动时探测 4096：
├─ /global/health 返回 200
├─ 用 B 的 password 尝试请求
│   ├─ 200 → 对方是 B 的 server（复用）✅
│   └─ 401 → 对方是 A 的 server（隔离）→ 换端口
└─ 端口空闲 → 启动新 server
```

### 3.3 启动流程

```mermaid
flowchart TD
    A["witty 启动"] --> B{"读取 ~/.config/witty/server-state.json"}
    
    B -->|"文件存在"| C{"PID 存活?"}
    C -->|"是"| D{"端口 + password 可用?"}
    C -->|"否"| E["删除 state file"]
    
    B -->|"文件不存在"| G{"探测 4096 端口"}
    E --> G
    
    D -->|"是"| F["复用已有 server ✅"]
    D -->|"否"| G
    
    G -->|"端口空闲"| H["启动 opencode serve --port 4096<br/>+ OPENCODE_SERVER_PASSWORD"]
    G -->|"端口占用"| I{"/global/health?"}
    
    I -->|"是 OpenCode"| J{"有已知 password?"}
    I -->|"非 OpenCode"| K["报错: 端口被占用"]
    
    J -->|"有且可用"| F
    J -->|"无或失败"| L["找下一个可用端口<br/>4097, 4098..."]

    H --> M["写 state file"]
    L --> M
    M --> N["正常使用"]
```

### 3.4 端口选择策略

1. **优先**：state file 中记录的端口（上次使用的）
2. **次选**：4096（默认端口）
3. **兜底**：逐个尝试 4097, 4098, … 4096+N（最多 10 个）

并发保护：两个 `witty` 进程同时启动时，通过 `O_EXCL` 创建 lock file 或使用 file-based advisory lock 避免竞态。

### 3.5 witty 退出策略：守护模式

```text
witty CLI 进程生命周期 ≠ opencode serve 进程生命周期
```

- witty 退出时**不杀** server 子进程（守护模式）
- opencode serve 作为孤儿进程被 init (PID 1) 收养，继续运行
- 下次启动 witty 时通过 state file 复用

**唯一停止 server 的场景**：

- 用户显式执行 `witty server stop`（未来命令）
- OS 重启 / 用户登出（进程自然终止）

---

## 4. 安全设计

### 4.1 威胁模型

同一台 openEuler 服务器上，用户 A（UID 1001）和用户 B（UID 1002）同时使用 witty。

| 威胁 | 严重程度 | 缓解措施 |
| ---- | -------- | -------- |
| B 连接 A 的 server | 🔴 高 | HTTP Basic Auth password + state file 隔离 |
| A 读取 B 的 API key | 🔴 高 | Server password 阻止未认证请求 |
| A 扫描 B 的端口 | 🟡 中 | state file 权限 0600，端口不可预测 |
| 磁盘上的 state file 泄露 | 🟡 中 | 文件权限 0600，不同 UID 无法读取 |

### 4.2 防御层次

```text
Layer 1: 文件系统权限（state file 0600）
Layer 2: Server Password（随机生成，不可猜测）
Layer 3: 非固定端口（降低被扫描命中概率）
```

### 4.3 其他安全考虑

- password 通过 `crypto/rand` 生成，32 字节 hex 编码
- password 仅通过环境变量 `OPENCODE_SERVER_PASSWORD` 传递给子进程，不出现在命令行参数中（`/proc` 安全）
- 日志中不输出 password
- `.agents/config.yaml` 不记录 password（已在 .gitignore 中）

---

## 5. 配置设计

### 5.1 新增配置项

`~/.config/witty/config.toml`:

```toml
[server]
auto_start = true           # 默认开启自动启动
port = 0                    # 0 = 自动选择端口，正整数 = 固定端口
hostname = "127.0.0.1"      # 绑定地址
startup_timeout_seconds = 10 # 等待 server 启动的最大时间
```

### 5.2 环境变量覆盖

| 环境变量 | 对应配置 | 说明 |
| -------- | -------- | ---- |
| `WITTY_SERVER_AUTO_START` | `server.auto_start` | `true`/`false` |
| `WITTY_SERVER_PORT` | `server.port` | 端口号 |
| `WITTY_SERVER_HOSTNAME` | `server.hostname` | 绑定地址 |

### 5.3 向后兼容

- `auto_start = false`（或环境变量 `WITTY_SERVER_AUTO_START=false`）时，行为完全回退到当前模式（需要手动启动 server）
- 新增字段不影响现有配置文件的解析

---

## 6. 模块设计：`internal/server`

### 6.1 模块职责

管理 `opencode serve` 进程的完整生命周期：启动、检测、复用、停止。

### 6.2 接口设计

```go
// package server

// Manager 管理 opencode serve 进程的生命周期。
type Manager interface {
    // Ensure 确保 server 可用。如果已有可用 server，直接返回其地址和认证信息；
    // 否则启动一个新的 server 进程。
    Ensure(ctx context.Context) (Connection, error)

    // Stop 停止由 Manager 管理的 server 进程。
    // 如果 server 不是由当前 witty 进程启动的（从 state file 恢复），则不做任何操作。
    Stop(ctx context.Context) error

    // Status 返回当前 server 的状态信息，用于诊断。
    Status(ctx context.Context) Status
}

// Connection 描述一个可用的 server 连接信息。
type Connection struct {
    URL      string // 完整 URL，例如 http://127.0.0.1:4097
    Password string // HTTP Basic Auth 密码
}

// Status 描述 server 的运行时状态。
type Status struct {
    Running   bool   // server 是否在运行
    Port      int    // 监听端口
    PID       int    // 进程 ID（如果是本进程管理的）
    Managed   bool   // 是否由当前 witty 进程启动（false = 从 state file 恢复）
    StartedAt string // 启动时间
}

// Options 配置 Manager。
type Options struct {
    StateDir            string        // state file 目录（默认 ~/.config/witty）
    AutoStart           bool          // 是否自动启动
    PreferredPort       int           // 首选端口（0 = 自动选择）
    Hostname            string        // 绑定地址
    StartupTimeout      time.Duration // 等待 server 就绪的最大时间
    OpenCodeBinaryPath  string        // opencode 二进制路径（默认 "opencode"）
}
```

### 6.3 子组件

```text
internal/server/
├── server.go         # Manager 接口 + 构造函数
├── manager.go        # 核心生命周期逻辑
├── state.go          # state file 读写
├── discovery.go      # 端口探测 + health 检查
├── process.go        # 子进程管理（spawn + PID 追踪）
├── password.go       # 随机密码生成
├── server_test.go    # 单元测试
└── export_test.go    # 测试辅助
```

### 6.4 与应用层的集成

在 `internal/app/wiring.go` 中：

```go
serverMgr, err := server.NewManager(server.Options{
    StateDir:           wittyStateDir,
    AutoStart:          cfg.Server.AutoStart,
    PreferredPort:      cfg.Server.Port,
    Hostname:           cfg.Server.Hostname,
    StartupTimeout:     time.Duration(cfg.Server.StartupTimeoutSeconds) * time.Second,
    OpenCodeBinaryPath: "opencode",
})
// Ensure 在 transport client 创建之前调用
conn, err := serverMgr.Ensure(ctx)
// 用 conn.URL 创建 transport client
// 如果设置了 conn.Password，在 transport 中添加 Authorization header
```

---

## 7. 边界情况与错误处理

| 场景 | 处理方式 |
| ---- | -------- |
| **首次启动** | 没有 state file，走完整探测→启动流程 |
| **Server 崩溃（witty 不在运行）** | 下次启动时 PID 检测失败 → 删旧 state → 重新启动 |
| **State file 被误删但 server 还活着** | 端口探测找到 server 但无 password 可用 → 生成新密码重启（或降级为无密码连接 + warn） |
| **目标端口被非 OpenCode 进程占用** | 端口连通但 `/global/health` 返回非预期 → 报错并提示端口冲突 |
| **磁盘满，state file 写失败** | 降级为"本次会话有效"模式（内存中的 connection info），warn 用户 |
| **opencode 二进制不在 PATH** | 报明确错误，提示安装 opencode |
| **`opencode serve` 启动超时** | 等 startup_timeout_seconds 秒后 health check 仍失败 → 报错退出 |
| **并发启动（两个 witty 进程同时启动）** | 文件锁 + coalesce 防御，防止 spawn 两个 server |

---

## 8. 开发路线图

### Phase 1（本阶段）：核心自动启动

- [ ] `internal/server` 模块骨架 + 接口定义
- [ ] state file 读写
- [ ] 端口探测 + health check
- [ ] 子进程启动（`os/exec`）
- [ ] PID 验证
- [ ] 配置文件 `server.auto_start` 字段
- [ ] `internal/app/wiring.go` 集成
- [ ] 单元测试（mock opencode binary）

### Phase 2（后续）：安全加固

- [ ] 随机 password 生成 + HTTP Basic Auth
- [ ] 密码认证探测（区分"我的"和"别人的" server）
- [ ] 非固定端口自动选择
- [ ] 并发启动的 coalesce 防御

### Phase 3（后续）：运维能力

- [ ] `witty server status` 诊断命令
- [ ] `witty server stop` 停止命令
- [ ] idle timeout + 自动清理
- [ ] `witty doctor` 增强（显示 server 管理状态）

---

## 9. 参考

- [OpenCode Server 文档](https://opencode.ai/docs/server/)
- [opencode-mcp 自动启动实现（in-process SDK）](https://github.com/AlaeddineMessadi/opencode-mcp)
- [opencode-mcp 架构文档](https://github.com/AlaeddineMessadi/opencode-mcp/blob/main/docs/architecture.md)
- [OpenCode CLI 文档](https://opencode.ai/docs/cli/)

# Witty Daemon 设计文档

## 1. 动机

### 1.1 当前问题

| 问题 | 表现 | 影响 |
| ---- | ---- | ---- |
| 配置不热加载 | 安装/卸载 agent/skill 包后，opencode server 不重启，配置变更不生效 | 用户需手动重启 VM 或 `witty server restart` |
| idle timeout 非真正 proactive | idle check 仅在下次 witty CLI 调用 `Ensure()` 时触发 | server 可能已 idle 很久但未及时回收 |
| 生命周期分散 | server 的 start/stop/idle 管理嵌入在 CLI 进程中 | CLI 退出后 server 仍在后台，但没有守护进程保障 |

### 1.2 目标

设计一个最小化守护进程 `wittyd`：

1. **开机自启**：作为 systemd 服务，随系统启动
2. **管理 opencode server 生命周期**：启动、健康监控、停止
3. **配置感知重启**：检测 `/etc/opencode/opencode.json` 变更后自动重启 server
4. **真正的 idle timeout**：主动定时检查，idle 超时后立即停止 server
5. **精简 witty CLI**：移除被 daemon 接管的功能

---

## 2. 架构

### 2.1 总体结构

```text
┌──────────────────────────────────────────────────────────────────┐
│                           systemd                                │
│                                                                  │
│  wittyd.service                                   witty CLI     │
│  ┌─────────────────────────┐         ┌─────────────────────────┐ │
│  │  wittyd                 │         │  witty ask/agent/...    │ │
│  │  ┌───────────────────┐  │  unix   │  ┌───────────────────┐  │ │
│  │  │ ServerSupervisor  │◄─┼─────────┼──│ server.Discover() │  │ │
│  │  │  - start          │  │  socket │  │ (只发现，不启动)   │  │ │
│  │  │  - stop           │  │         │  └───────────────────┘  │ │
│  │  │  - restart        │  │         │                         │ │
│  │  │  - health check   │  │         │  witty server stop      │ │
│  │  ├───────────────────┤  │         │  ┌───────────────────┐  │ │
│  │  │ ConfigWatcher     │  │         │  │ → sends RPC to    │  │ │
│  │  │  - fsnotify       │  │         │  │   daemon socket   │  │ │
│  │  ├───────────────────┤  │         │  └───────────────────┘  │ │
│  │  │ IdleMonitor       │  │         │                         │ │
│  │  │  - tick & check   │  │         │  witty server restart   │ │
│  │  │  - last_used      │  │         │  ┌───────────────────┐  │ │
│  │  └───────────────────┘  │         │  │ → sends RPC to    │  │ │
│  └──────────┬──────────────┘         │  │   daemon socket   │  │ │
│             │ spawn/monitor          │  └───────────────────┘  │ │
│             ▼                        └─────────────────────────┘ │
│  ┌─────────────────────┐                                        │
│  │  opencode serve     │                                        │
│  │  127.0.0.1:4096-4105│                                        │
│  └─────────────────────┘                                        │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 进程边界

```text
wittyd (PID 1 的子进程，由 systemd 管理)
  └── opencode serve (daemon fork + Setpgid 的子进程)
        └── 脱离 daemon 独立存活（daemon exit 时 server 不退出）

witty CLI (独立进程，发起即退出)
  └── 通过 Unix socket 与 daemon 通信
  └── 通过 HTTP 与 opencode server 通信
```

### 2.3 通信协议

Unix domain socket 位于 `/run/wittyd/wittyd.sock`（root 运行）或 `$XDG_RUNTIME_DIR/wittyd.sock`（user 模式）。

协议为**换行分隔的 JSON**（每行一条消息，服务端逐行回复）：

#### 2.3.1 请求

| Method | 参数 | 说明 |
| ------ | ---- | ---- |
| `PING` | — | 心跳/存活检查 |
| `STATUS` | — | 返回当前 server 状态 |
| `TOUCH` | — | 刷新 last_used 时间戳（witty transport 每次请求成功后调用） |
| `STOP` | — | 停止 opencode server |
| `RESTART` | — | 停止并重新启动 opencode server |

请求格式：

```json
{"method": "TOUCH"}
```

#### 2.3.2 响应

| 状态 | 格式 |
| ---- | ---- |
| 成功 | `{"ok":true, "data":{...}}` |
| 错误 | `{"ok":false, "error":"message"}` |

STATUS 响应 data：

```json
{
  "running": true,
  "port": 4099,
  "pid": 12345,
  "started_at": "2026-07-06T15:00:00+08:00",
  "last_used": "2026-07-06T15:05:00+08:00"
}
```

RESTART 响应 data：

```json
{
  "url": "http://127.0.0.1:4099",
  "port": 4099
}
```

#### 2.3.3 客户端实现

witty CLI 中新增轻量级 `internal/daemon/client.go`，提供：

```go
type Client interface {
    Ping(ctx context.Context) error
    Status(ctx context.Context) (DaemonStatus, error)
    Touch(ctx context.Context) error
    Stop(ctx context.Context) error
    Restart(ctx context.Context) (Connection, error)
}
```

失败策略：如果 daemon socket 不可达（daemon 未运行），TOUCH 静默降级（忽略），STOP/RESTART 返回明确错误提示用户启动 daemon。

---

## 3. 组件详设

### 3.1 ServerSupervisor

```text
internal/daemon/supervisor.go
```

封装对 opencode server 的启停管理，复用现有 `internal/server/` 中的核心逻辑：

- **初始化**：加载 state file → 发现已有 server 则接管；否则 auto-start
- **startServer**：复用 `internal/server/process.go` 中的 `startServer()`（spawn + health check）
- **stopServer**：复用 `internal/server/manager.go` 中的 `Stop()`（dispose → SIGTERM fallback）
- **healthLoop**：每 30s ping `/global/health`，失败后尝试重启（最多 3 次）

```go
type Supervisor struct {
    state    *stateStore       // 复用 internal/server/state.go
    opts     SupervisorOptions
    mu       sync.Mutex
    proc     *os.Process       // 当前管理的 server 进程
    lastUsed time.Time
}

type SupervisorOptions struct {
    StateDir      string
    Hostname      string
    PreferredPort int
    Password      string
    BinaryPath    string
}
```

### 3.2 ConfigWatcher

```text
internal/daemon/config_watcher.go
```

使用 `fsnotify` 监听配置文件变更：

- 监听文件：`/etc/opencode/opencode.json`
- 监听目录（IN_CREATE | IN_DELETE | IN_MOVED_TO | IN_MOVED_FROM）：`/usr/share/witty/opencode/config.d/`
- **防抖**：文件变更后等待 2s（debounce），避免 RPM 事务触发多次重启
- 触发动作：调用 `Supervisor.Restart()`

```go
type ConfigWatcher struct {
    supervisor *Supervisor
    watcher    *fsnotify.Watcher
    debounce   time.Duration  // 默认 2s
}
```

#### 3.2.1 Hook 集成时机

```text
RPM 事务:
  %posttrans / %transfiletriggerin
    └── run-managed-config-hook.sh
          └── rebuild-managed-config.mjs
                └── 写入 /etc/opencode/opencode.json
                      │
                      ▼ (fsnotify IN_MODIFY)
                ConfigWatcher 感知
                      │
                      ▼ (debounce 2s)
                Supervisor.Restart()
```

### 3.3 IdleMonitor

```text
internal/daemon/idle_monitor.go
```

**真正 proactive 的 idle 管理**：

- 每 `checkInterval`（默认 60s）检查一次
- 比较 `time.Since(supervisor.LastUsed())` 与 `IdleTimeout`
- 超时则调用 `Supervisor.Stop()`
- idle timeout 可通过 daemon 配置设置（默认 30min），设为 0 禁用

```go
type IdleMonitor struct {
    supervisor   *Supervisor
    idleTimeout  time.Duration
    tickInterval time.Duration  // 默认 60s
}

func (m *IdleMonitor) Run(ctx context.Context) {
    ticker := time.NewTicker(m.tickInterval)
    defer ticker.Stop()
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            if m.idleTimeout > 0 &&
               time.Since(m.supervisor.LastUsed()) > m.idleTimeout {
                m.supervisor.Stop()
            }
        }
    }
}
```

**与当前实现的区别**：

| 维度 | 当前（CLI 内 idleMonitor） | 新（daemon IdleMonitor） |
| ---- | ------------------------ | ---------------------- |
| 触发方式 | 仅下次 CLI 调用 `Ensure()` 时检查 | 后台定时主动检查 |
| 运行进程 | witty CLI（可能已退出） | wittyd（始终运行） |
| 及时性 | 取决于用户何时下次使用 witty | 最多 60s 延迟 |

### 3.4 主循环

```text
cmd/wittyd/main.go
```

```go
func main() {
    cfg := loadDaemonConfig()

    supervisor := daemon.NewSupervisor(...)

    // 信号处理
    ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
    defer cancel()

    // 启动 opencode server
    if err := supervisor.Ensure(ctx); err != nil {
        log.Fatal("failed to start server:", err)
    }

    // 启动子组件
    var wg sync.WaitGroup

    // Config watcher
    cw := daemon.NewConfigWatcher(supervisor, daemon.ConfigWatcherOptions{
        ConfigFile: "/etc/opencode/opencode.json",
        ConfigDir:  "/usr/share/witty/opencode/config.d",
    })
    wg.Add(1)
    go func() { defer wg.Done(); cw.Run(ctx) }()

    // Idle monitor
    im := daemon.NewIdleMonitor(supervisor, cfg.IdleTimeout)
    wg.Add(1)
    go func() { defer wg.Done(); im.Run(ctx) }()

    // IPC server
    ipc := daemon.NewIPCServer(supervisor, cfg.SocketPath)
    wg.Add(1)
    go func() { defer wg.Done(); ipc.Serve(ctx) }()

    <-ctx.Done()

    // Graceful shutdown
    ipc.Shutdown()
    supervisor.Stop(context.Background())
    wg.Wait()
}
```

---

## 4. 配置

### 4.1 Daemon 配置

`/etc/witty/daemon.toml`（由 RPM 安装，`%config(noreplace)`）：

```toml
# wittyd configuration

# Unix socket path for witty CLI communication
socket_path = "/run/wittyd/wittyd.sock"

# opencode server settings
[server]
# Preferred port (0 = auto-select from 4096)
port = 0
# Bind hostname
hostname = "127.0.0.1"
# Auto-start server on daemon startup
auto_start = true

# Idle timeout: stop server after this duration of no activity
# Set to 0 to disable
idle_timeout_minutes = 30

# Config file to watch for changes (triggers graceful restart)
config_watch_file = "/etc/opencode/opencode.json"
# Config directory to watch for agent/skill additions or removals
config_watch_dir = "/usr/share/witty/opencode/config.d"
```

### 4.2 witty CLI 配置变更

`server.auto_start` 和 `server.idle_timeout_minutes` 从 witty 的用户配置中**移除**，移至 daemon 配置。

witty CLI 的 `[server]` 段仅保留：

```toml
[server]
# Preferred port (0 = auto)
port = 0
# Bind hostname
hostname = "127.0.0.1"
# Startup timeout
startup_timeout_seconds = 10
```

---

## 5. witty CLI 变更

### 5.1 移除的功能

| 功能 | 原位置 | 去向 |
| ---- | ------ | ---- |
| server auto-start | `server.Manager.Ensure()` → `autoStart()` | daemon Supervisor |
| idle timeout 监控 | `server.Manager.idleMonitor()` | daemon IdleMonitor |
| `server.idle_timeout_minutes` 配置 | `config.Config.Server.IdleTimeoutMinutes` | daemon 配置 |
| `server.auto_start` 配置 | `config.Config.Server.AutoStart` | daemon 配置 |

### 5.2 保留的功能

| 功能 | 实现方式 |
| ---- | ------- |
| server 发现 | `ServerManager.Ensure()` → scan existing ports, reuse state file |
| `witty server status` | 优先通过 daemon socket 查询；回退到直接读 state file |
| `witty server stop` | 通过 daemon socket 发送 STOP RPC；回退到直接 Stop |
| `witty server restart` | 通过 daemon socket 发送 RESTART RPC |
| TouchLastUsed | 通过 daemon socket 发送 TOUCH RPC；失败时静默降级 |
| `witty doctor` | 保持现状，展示 daemon 状态信息 |

### 5.3 变更后的 `ServerManager.Ensure()`

```go
func (m *manager) Ensure(ctx context.Context) (Connection, error) {
    // 1. 尝试通过 daemon socket 查询
    if conn, ok := m.tryDaemonSocket(ctx); ok {
        return conn, nil
    }

    // 2. 回退：直接扫描发现已有的 server
    //    （不再 auto-start，由 daemon 负责）
    conn, err := m.discoverExisting(ctx)
    if err != nil {
        return Connection{}, fmt.Errorf(
            "no opencode server found and wittyd is not running; "+
            "start wittyd or set --server-url", err)
    }
    return conn, nil
}
```

### 5.4 依赖变更

新增依赖：

- `github.com/fsnotify/fsnotify` — 文件系统事件监听（仅 daemon 使用）

---

## 6. systemd 集成

### 6.1 Unit 文件

`/usr/lib/systemd/system/wittyd.service`（由 RPM 安装）：

```ini
[Unit]
Description=Witty OpenCode Server Daemon
Documentation=https://gitee.com/openeuler/euler-copilot-shell
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/bin/wittyd
ExecStop=/usr/bin/witty server stop
Restart=on-failure
RestartSec=5s

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/etc/opencode /run/wittyd /var/lib/witty
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

### 6.2 RPM 集成

在 `witty` 子包的 `%post` 中 enable + start daemon：

```spec
%post -n witty
%systemd_post wittyd.service

%preun -n witty
%systemd_preun wittyd.service

%postun -n witty
%systemd_postun_with_restart wittyd.service
```

---

## 7. 文件变更清单

### 7.1 新增文件

```text
cmd/wittyd/
  main.go                          # daemon 入口

internal/daemon/
  supervisor.go                    # ServerSupervisor
  config_watcher.go                # ConfigWatcher (基于 fsnotify)
  idle_monitor.go                  # IdleMonitor (proactive)
  ipc.go                           # Unix socket IPC server
  client.go                        # IPC client (供 witty CLI 使用)

packaging/
  wittyd.service             # systemd unit
  daemon.toml                      # daemon 默认配置

docs/design/
  witty-daemon.md                  # 本文档
```

### 7.2 修改文件

```text
internal/server/
  manager.go     # 移除 autoStart、idleMonitor；新增 discoverExisting()
  process.go     # （不变，daemon 通过 supervisor 复用）
  server.go      # 移除 Manager 接口中不再需要的方法
  state.go       # 增加 LastUsed 字段的 daemon 端写支持

internal/config/
  config.go      # 移除 Server.AutoStart、Server.IdleTimeoutMinutes

internal/cli/
  server.go      # stop/restart 改为 IPC client 调用

internal/app/
  wiring.go      # 移除 idleTimeout 传参；daemon client 初始化

internal/transport/
  client.go      # OnRequestSuccess → daemon IPC client.Touch()

go.mod           # 新增 fsnotify
```

### 7.3 修改文件（packaging）

```text
packaging/
  euler-copilot-shell.spec  # 新增 wittyd binary；systemd unit；daemon.toml
  profile.d/witty.sh        # （不变）
```

---

## 8. 兼容性

### 8.1 降级场景

如果 daemon 未运行（用户禁用了 systemd 服务，或手动 kill），witty CLI 的行为：

| 操作 | 降级行为 |
| ---- | ------- |
| `witty ask` | 扫描发现已有 server → 正常使用（不变） |
| `witty server stop` | daemon socket 不可达 → 回退到直接 `server.Stop()`（不变） |
| `witty server restart` | daemon socket 不可达 → 回退到 stop + 提示用户手动重启 |
| TOUCH | 静默忽略 |
| 新 server 启动 | **不再执行**（无 daemon 时不会 auto-start） |

### 8.2 迁移

从旧版本升级到含 daemon 的版本后：

1. `dnf update` 安装新 RPM
2. `systemctl enable --now wittyd`（`%post` 自动执行）
3. daemon 启动时发现已有 server 在运行 → 接管管理
4. 行为上对用户透明

---

## 9. 实现阶段

| 阶段 | 内容 | 验证方式 |
| ---- | ---- | ------- |
| Phase 1 | 创建 `cmd/wittyd/`，实现 Supervisor 和主循环 | `wittyd` 能启动并管理 opencode server |
| Phase 2 | 实现 IdleMonitor（proactive timeout） | server 在 idle 后自动停止 |
| Phase 3 | 实现 ConfigWatcher（fsnotify） | 安装/卸载 agent 包后 server 自动重启 |
| Phase 4 | 实现 IPC（Unix socket + 协议） | `witty server status/stop/restart` 通过 daemon |
| Phase 5 | 修改 witty CLI，移除被接管的逻辑 | 所有现有测试通过；新功能正常 |
| Phase 6 | systemd unit + RPM spec 集成 | `systemctl start wittyd` 正常工作 |

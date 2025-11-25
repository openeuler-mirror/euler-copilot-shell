# TUI 应用模块设计

## 方案设计

### 整体方案设计

TUI 应用模块基于 Textual 框架构建，提供智能终端的用户界面。采用组件化设计，支持动态界面切换和事件驱动的交互模式。

#### 模块架构

```mermaid
graph TB
    subgraph "主应用层"
        A[IntelligentTerminal<br/>主应用容器] --> B[CommandInput<br/>命令输入]
        A --> C[FocusableContainer<br/>输出容器]
        A --> D[Header/Footer<br/>界面框架]
    end
    
    subgraph "MCP 交互组件"
        E[MCPConfirmWidget<br/>工具确认] --> F[确认按钮组]
        G[MCPParameterWidget<br/>参数收集] --> H[动态表单]
    end
    
    subgraph "对话框组件"
        I[AgentSelectionDialog<br/>智能体选择] --> J[智能体列表]
        K[SettingsScreen<br/>设置界面] --> L[配置表单]
        M[DeploymentScreen<br/>部署助手] --> N[流程向导]
    end
    
    subgraph "事件处理层"
        O[TUIMCPEventHandler<br/>MCP事件处理] --> E
        O --> G
        P[Textual消息系统] --> A
    end
    
    subgraph "输出组件"
        Q[OutputLine<br/>纯文本输出]
        R[MarkdownOutput<br/>富文本输出]
        S[MCPProgressBlock<br/>进度块]
        T[MCPWaitingBlock<br/>交互提示]
    end
    
    A --> E
    A --> G
    A --> I
    A --> K
    A --> M
    C --> Q
    C --> R
    C --> S
    C --> T
```

#### 核心组件

1. **主界面组件** (`tui.py`)
   - 应用主窗口和布局管理
   - 异步任务管理和状态控制
   - 快捷键绑定和焦点控制（支持 Ctrl+C 中断当前会话）
   - MCP 模式切换机制与进度行跟踪

2. **MCP 交互组件** (`mcp_widgets.py`)
   - 工具确认界面和风险展示
   - 参数收集界面和表单验证
   - 用户交互结果回传

3. **对话框组件** (`dialogs/`)
   - 智能体选择和状态管理
   - 设置界面和配置持久化
   - 模态对话框基类

4. **部署助手** (`deployment/`)
   - 配置收集和验证界面
   - 部署进度实时显示
   - 状态监控和错误处理

### 详细设计

#### 主应用类设计

```mermaid
classDiagram
    class IntelligentTerminal {
        +title: str
        +processing: bool
        +background_tasks: set[Task]
        +current_agent: tuple[str, str]
        +mcp_mode: str
        +current_mcp_task_id: str
        +config_manager: ConfigManager
        +llm_client: LLMClientBase
        +compose() ComposeResult
        +handle_input(event: Input.Submitted) None
        +get_llm_client() LLMClientBase
        +action_settings() None
        +action_request_quit() None
        +action_reset_conversation() None
        +action_choose_agent() None
        +action_toggle_focus() None
        +action_interrupt() None
        +refresh_llm_client() None
    }
    
    class FocusableContainer {
        +can_focus: bool
        +on_key(event: KeyEvent) None
        +scroll_up() None
        +scroll_down() None
    }
    
    class OutputLine {
        +text_content: str
        +update(content: str) None
        +get_content() str
    }
    
    class MarkdownOutputLine {
        +current_content: str
        +update_markdown(content: str) None
        +get_content() str
        +_get_code_theme() str
    }
    
    IntelligentTerminal --> FocusableContainer
    FocusableContainer --> OutputLine
    FocusableContainer --> MarkdownOutputLine
```

#### MCP 组件交互流程

```mermaid
sequenceDiagram
    participant S as HermesStreamEvent
    participant H as TUIMCPEventHandler
    participant T as IntelligentTerminal
    participant C as MCPConfirmWidget
    participant P as MCPParameterWidget
    participant U as 用户

    S->>H: step.waiting_for_start
    H->>T: SwitchToMCPConfirm 消息
    T->>T: _replace_input_with_mcp_widget
    T->>C: 创建确认组件
    C->>U: 显示确认界面
    U->>C: 点击确认/取消
    C->>T: MCPConfirmResult 消息
    T->>T: _restore_normal_input
    T->>T: _send_mcp_response
    
    Note over S,T: 参数输入流程类似
    S->>H: step.waiting_for_param
    H->>T: SwitchToMCPParameter 消息
    T->>P: 创建参数组件
    P->>U: 显示参数表单
    U->>P: 填写参数
    P->>T: MCPParameterResult 消息
```

#### 界面状态机

```mermaid
stateDiagram-v2
    [*] --> Normal: 应用启动
    
    Normal --> Processing: 用户输入命令
    Processing --> MCPConfirm: 等待工具确认
    Processing --> MCPParameter: 等待参数输入
    Processing --> Normal: 处理完成
    
    MCPConfirm --> MCPExecute: 用户确认
    MCPConfirm --> Normal: 用户取消
    MCPParameter --> MCPExecute: 参数提供
    MCPParameter --> Normal: 用户取消
    MCPExecute --> Normal: 执行完成
    
    Normal --> Settings: Ctrl+S
    Settings --> Normal: 保存/取消
    Normal --> AgentSelection: Ctrl+T
    AgentSelection --> Normal: 选择完成
    
    Normal --> [*]: 退出应用
```

#### 消息系统设计

```mermaid
classDiagram
    class Message {
        <<abstract>>
    }
    
    class SwitchToMCPConfirm {
        +event: HermesStreamEvent
    }
    
    class SwitchToMCPParameter {
        +event: HermesStreamEvent
    }
    
    class MCPConfirmResult {
        +task_id: str
        +confirmed: bool
    }
    
    class MCPParameterResult {
        +task_id: str
        +params: dict|None
    }
    
    class ContentChunkParams {
        +content: str
        +is_llm_output: bool
        +current_content: str
        +is_first_content: bool
    }
    
    Message <|-- SwitchToMCPConfirm
    Message <|-- SwitchToMCPParameter
    Message <|-- MCPConfirmResult
    Message <|-- MCPParameterResult
```

#### 组件布局结构

```mermaid
flowchart TD
    A[IntelligentTerminal] --> B[Header]
    A --> C[FocusableContainer#output-container]
    A --> D[Container#input-container]
    A --> E[Footer]
    
    D --> F[CommandInput]
    D --> G[MCPConfirmWidget]
    D --> H[MCPParameterWidget]
    
    C --> I[OutputLine.command-line]
    C --> J[OutputLine]
    C --> K[MarkdownOutputLine]
    
    subgraph "对话框层"
        L[SettingsScreen]
        M[AgentSelectionDialog]
        N[BackendRequiredDialog]
        O[ExitDialog]
    end
    
    A -.-> L
    A -.-> M
    A -.-> N
    A -.-> O
```

#### 异步任务管理

```mermaid
flowchart TD
    A[用户输入] --> B[创建处理任务]
    B --> C[添加到 background_tasks]
    C --> D[异步执行命令处理]
    
    D --> E[处理命令流]
    E --> F[实时更新界面]
    F --> G[处理完成]
    
    G --> H[任务完成回调]
    H --> I[从 background_tasks 移除]
    I --> J[重置 processing 标志]
    
    subgraph "异常处理"
        K[捕获异常]
        L[记录日志]
        M[显示错误信息]
    end
    
    D --> K
    K --> L
    L --> M
    M --> H
```

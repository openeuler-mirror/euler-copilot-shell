# openEuler Intelligence 智能体使用手册

## 1. 引言

本手册介绍的 OE 智能体系列，是 **openEuler Intelligence 生态的核心工具集**，专为基于 openEuler 开展开发、运维工作，或负责 openEuler 系统管理的用户设计，覆盖物理机、虚拟机、容器集群等主流部署形态，无需依赖第三方工具即可在 openEuler 生态内完成全流程操作。

这一系列工具的核心价值，在于解决 openEuler 环境下的运维痛点：无需切换多工具、记忆复杂指令，就能高效应对“日常运维、异构智算、通用计算、容器虚拟化”四大核心场景，既降低新手入门门槛，也提升资深用户的工作效率。

它的核心特点有三个：一是**场景化聚焦**，针对不同工作需求提供专用助手，而非“万能工具”；二是**生态深度适配**，完全贴合 openEuler 系统特性，避免兼容性问题；三是**操作轻量化**，支持简单交互即可完成复杂任务，无需深入底层技术细节。

整套系列包含五套核心智能助手，也是本手册即将详细介绍的内容：

1. **OE-智能运维助手**：负责 openEuler 日常运维，搞定网络监控、性能分析、硬件查询、文件管理和传输等基础操作；
2. **OE-智算调优助手**：适配 openEuler 异构智算场景，监控 GPU/NPU 状态、追踪 AI 训练任务、排查调优问题；
3. **OE-通算调优助手**：针对 openEuler 通用计算（尤其 NUMA 架构服务器），做架构优化、性能诊断调优，解决瓶颈；
4. **OE-容器镜像助手**：管理 openEuler 容器与虚拟化环境，覆盖 Docker 运维、QEMU 虚拟机管控、容器性能优化。
5. **智能问答**：操作系统使用通用知识解答，支持多轮对话式交互。

后续章节将围绕这五套助手，逐一讲解其适用场景、核心能力、操作流程与实操案例，所有内容均贴合 openEuler 实际工作需求，侧重“能落地、可复用”，帮助您快速上手并发挥工具价值。

### 默认智能体总汇表

| Agent 名称 | 核心适用场景 | 核心能力模块 |
|------------|--------------|--------------|
| [**OE-智能运维助手**](#OE-智能运维助手) | 全场景通用系统运维（日常监控、基础操作、网络管理） | 1. 网络状态监控（流量统计、连接排查、带宽分析）与防火墙规则管控（端口访问、安全策略配置）<br>2. 系统性能分析（CPU/内存/进程负载监控）与硬件信息查询（节点配置、硬件型号采集）<br>3. 存储管理（内存/Swap 管控、磁盘数据同步）与文件操作（内容编辑、跨节点传输、批量管理） |
| [**OE-智算调优助手**](#OE-智算调优助手) | AI/GPU/NPU 异构智算场景（模型训练、异构硬件监控） | 1. 异构硬件状态监控（GPU 负载/显存/温度、NPU 算力/内存占用实时采集）<br>2. 智算任务系统追踪（运行轨迹、资源消耗统计）与问题排查（显存溢出、进程异常定位）<br>3. 基础运维支持（后台任务启动、日志跟踪、配置文件编辑、跨节点数据传输）<br>4. AI 训练任务性能分析与优化建议（基于全栈跟踪数据，识别 Host bound、算子慢、CPU 抢占等性能瓶颈，提供针对性调优方向，降低故障导致的训练成本浪费） |
| [**OE-通算调优助手**](#OE-通算调优助手) | 通用计算场景（NUMA 架构优化、性能瓶颈诊断） | 1. NUMA 架构分析（节点拓扑、CPU/内存关联）与进程绑定优化（启动绑定、动态调整、容器 NUMA 管控）<br>2. CPU 热点追踪（高频函数定位）、缓存损耗诊断（L1/L2/L3 缓存未命中率分析）与系统调用排查（I/O 瓶颈、中断影响）<br>3. 系统性能指标采集（CPU/内存/IOPS 周期性记录）与调优效果验证（性能基线对比、优化方案生成）<br>4. 智能参数调优与效果验证（基于系统、微架构、应用等多维度指标采集，借助大语言模型与定制化 Prompt 工程生成应用可调参数推荐，通过 benchmark 运行对比基线数据，量化性能提升值，实现调优方案的精准落地） |
| [**OE-容器镜像助手**](#OE-容器镜像助手) | 容器与虚拟化环境管理（Docker 运维、QEMU 管理） | 1. Docker 容器生命周期管理（创建/启动/停止/删除）与镜像运维（导出/导入、跨节点迁移）<br>2. QEMU 虚拟化环境管控（虚拟机创建、资源配置、网络模式设置、运行状态监控）<br>3. 容器 NUMA 绑定优化（内存访问模式分析、跨节点损耗降低、性能提升配置） |

> [!NOTE] 说明
> 
> 1. **关键 MCP 工具**：聚焦各 Agent 差异化能力，仅该场景需依赖的工具，是选择 Agent 的核心判断依据；
> 2. **基础通用工具**：覆盖日常运维高频操作，所有 Agent 均集成，确保无需跨 Agent 即可完成基础操作；
> 3. **场景匹配建议**：日常网络/硬件监控选「OE-智能运维助手」，AI 异构计算选「OE-智算调优助手」，NUMA 架构优化选「OE-通算调优助手」，容器/虚拟化管理选「OE-容器镜像助手」。

<a id="OE-智能运维助手"></a>

## 2. OE-智能运维助手

OE-智能运维助手是 openEuler Intelligence 体系下的**全场景通用运维智能体**，聚焦企业级服务器日常运维的“监控-排查-处理-管理”全流程需求，整合 42 个标准化 MCP 工具（覆盖网络、进程、硬件、存储、文件等核心维度），实现“单智能体替代多工具切换”的高效运维模式。

其核心优势在于**低门槛、全闭环、跨环境适配**：支持自然语言与标准化指令双交互，新手运维无需记忆复杂命令即可完成操作；从“异常发现（如 CPU 高负载、网络卡顿）”到“问题定位（如进程追踪、流量分析）”再到“故障处理（如进程终止、配置修改）”，无需跨模块即可完成闭环；兼容物理机、虚拟机、云服务器等多种部署环境，是企业日常运维的“一站式工具中枢”。

### 2.1 MCP 服务矩阵

OE-智能运维助手通过 42 个标准化 MCP 工具，构建“基础信息与命令执行-进程与系统监控-网络监控与安全-硬件与存储管理-文件与文本操作”五大核心能力模块，覆盖日常运维 95% 以上高频场景，具体服务与工具映射如下：

| 服务分类 | MCP 工具名称（带锚点） | 核心功能定位 | 默认端口 |
|----------|------------------------|--------------|----------|
| 一、基础信息与命令执行 | [remote_info_mcp](#remote_info_mcp) | 获取本地/远程节点基础信息（系统版本、硬件型号） | 12100 |
| | [shell_generator_mcp](#shell_generator_mcp) | 生成并执行 Shell 命令，支撑自然语言指令解析 | 12101 |
| 二、进程与系统监控 | [kill_mcp](#kill_mcp) | 终止进程、查看进程信号量含义，处理异常进程 | 12111 |
| | [nohup_mcp](#nohup_mcp) | 后台启动进程，避免终端退出导致进程中断 | 12112 |
| | [strace_mcp](#strace_mcp) | 跟踪进程系统调用，分析异常进程的行为逻辑 | 12113 |
| | [top_mcp](#top_mcp) | 查看 CPU/内存/进程负载，识别高占用资源进程 | 12110 |
| | [perf_interrupt_mcp](#perf_interrupt_mcp) | 定位高频中断源，分析中断导致的 CPU 占用 | 12220 |
| | [flame_graph_mcp](#flame_graph_mcp) | 生成 CPU 耗时火焰图，可视化函数调用栈瓶颈 | 12222 |
| 三、网络监控与安全 | [iftop_mcp](#iftop_mcp) | 实时监控指定网卡流量，按连接/主机统计带宽占用 | 12116 |
| | [nload_mcp](#nload_mcp) | 可视化展示网卡入/出带宽变化，识别带宽瓶颈 | 12117 |
| | [netstat_mcp](#netstat_mcp) | 查看网络连接状态、端口占用、协议统计，排查连接异常 | 12118 |
| | [lsof_mcp](#lsof_mcp) | 定位文件占用冲突、网络连接对应的进程，解决资源争抢 | 12119 |
| | [ifconfig_mcp](#ifconfig_mcp) | 查看/配置网络接口 IP、MAC 地址，诊断网卡基础问题 | 12120 |
| | [ethtool_mcp](#ethtool_mcp) | 查询网卡特性（速率/双工模式），配置网卡参数 | 12121 |
| | [tshark_mcp](#tshark_mcp) | 捕获网络数据包，分析协议异常（如丢包、延迟） | 12122 |
| | [firewalld_mcp](#firewalld_mcp) | 配置防火墙规则、Zone，管控端口访问权限 | 12130 |
| | [iptables_mcp](#iptables_mcp) | 配置 iptables 包过滤与 NAT 规则，强化网络安全 | 12131 |
| | [nmap_mcp](#nmap_mcp) | 扫描目标 IP 存活状态、开放端口，排查网络可达性 | 12135 |
| 四、硬件与存储管理 | [lscpu_mcp](#lscpu_mcp) | 采集 CPU 架构、核心数、NUMA 节点等静态信息 | 12202 |
| | [free_mcp](#free_mcp) | 查看系统内存、Swap 整体使用状态，识别内存不足 | 13100 |
| | [sync_mcp](#sync_mcp) | 将内存缓冲区数据强制写入磁盘，避免数据丢失 | 13103 |
| | [swapon_mcp](#swapon_mcp) | 启用 Swap 设备/文件，扩展虚拟内存 | 13104 |
| | [swapoff_mcp](#swapoff_mcp) | 停用 Swap 设备/文件，释放磁盘资源 | 13105 |
| | [fallocate_mcp](#fallocate_mcp) | 快速创建指定大小的 Swap 文件，应急扩展内存 | 13106 |
| 五、文件与文本操作 | [file_content_tool_mcp](#file_content_tool_mcp) | 对文件内容进行增、删、改、查，处理文本类需求 | 12125 |
| | [file_transfer_mcp](#file_transfer_mcp) | 本地与远程节点间文件传输、下载，支持批量操作 | 12136 |
| | [find_mcp](#find_mcp) | 按名称/大小/修改时间等条件查找文件 | 13107 |
| | [touch_mcp](#touch_mcp) | 创建空文件、修改文件访问/修改时间 | 13108 |
| | [mkdir_mcp](#mkdir_mcp) | 创建单个/多级文件夹，支持权限设置 | 13109 |
| | [rm_mcp](#rm_mcp) | 删除文件/文件夹，支持强制删除 | 13110 |
| | [mv_mcp](#mv_mcp) | 移动文件到指定路径，或修改文件名称 | 13111 |
| | [ls_mcp](#ls_mcp) | 查看目录下文件/文件夹名称、权限、大小 | 13112 |
| | [head_mcp](#head_mcp) | 查看文件前 N 行内容（默认前 10 行） | 13113 |
| | [tail_mcp](#tail_mcp) | 查看文件后 N 行内容，支持实时跟踪（-f） | 13114 |
| | [cat_mcp](#cat_mcp) | 查看文件全部内容，支持多文件合并查看 | 13115 |
| | [chmod_mcp](#chmod_mcp) | 修改文件/文件夹的读、写、执行权限 | 13117 |
| | [chown_mcp](#chown_mcp) | 修改文件/文件夹的所有者（用户/用户组） | 13116 |
| | [tar_mcp](#tar_mcp) | 打包/解包文件，支持 gzip/bzip2 压缩 | 13118 |
| | [zip_mcp](#zip_mcp) | 压缩/解压 zip 格式文件，支持密码保护 | 13119 |
| | [grep_mcp](#grep_mcp) | 按关键词搜索文件内容，支持正则匹配 | 13120 |
| | [sed_mcp](#sed_mcp) | 批量替换、删除文本内容，支持流处理 | 13121 |
| | [echo_mcp](#echo_mcp) | 将文本内容写入文件（覆盖/追加模式） | 13125 |

### 2.2 使用案例

以下按“网络问题排查、系统资源监控、文件操作、异常进程处理、硬件信息查询”五大高频运维场景分类，提供自然语言交互 Prompt 格式，直接替换 IP、网卡名、文件路径等关键信息即可使用，所有场景均贴合企业内部运维实际需求。

- 场景 1：服务器网络卡顿排查（eth0 网卡，访问内网服务延迟高）

  ```text
  本地服务器访问内网 192.168.2.5 的业务服务时延迟超 300ms，eth0 网卡存在卡顿，帮我排查：
    1. 查看 eth0 网卡的实时流量（按源/目的 IP 统计）、入/出带宽占用峰值；
    2. 找出当前与 192.168.2.5 的网络连接数，及对应进程 PID 与名称，排查是否有异常连接；
    3. 检查 firewalld 对 192.168.2.0/24 网段的访问规则，是否有端口拦截，最后给出优化建议。
  ```

- 场景 2：远程节点资源持续监控（192.168.1.100，监控业务高峰期负载）

  ```text
  帮我持续监控 192.168.1.100 节点（业务高峰期 10:00-12:00，每 5 秒刷新 1 次）：
    1. 查看 CPU 1/5/15 分钟平均负载、内存使用前 5 的进程（显示进程名、PID、已用内存占比）；
    2. 监控磁盘根分区（/）的使用率，若超过 85% 实时提醒；
    3. 记录监控周期内的 CPU 最高负载、内存最大占用率，生成简易统计报告。
  ```

- 场景 3：跨节点文件传输与配置修改（本地 → 192.168.1.101，业务配置更新）

  ```text
  帮我完成两项操作：
    1. 将本地 /usr/local/app/conf/new_app.conf 文件传输到 192.168.1.101 的 /opt/app/conf/ 目录，覆盖旧文件前先备份为 app.conf.bak；
    2. 修改 192.168.1.101 上 /opt/app/conf/app.ini 文件中 "max_connection" 的值为 500，"timeout" 的值为 300，修改后验证配置文件语法正确性。
  ```

- 场景 4：异常进程处理与后台重启（本地 “api-service” 进程 CPU 高占用）

  ```text
  本地 "api-service" 进程（PID 约 2345）占用 CPU 长期超 90% 且接口响应超时，帮我处理：
    1. 先查看该进程的系统调用情况（重点看 I/O 相关调用），再用 SIGKILL 信号强制终止进程；
    2. 用 nohup 后台重启进程，指定启动参数 "--config /etc/api-service/config.yaml"，日志输出到 /var/log/api-service/run.log；
    3. 重启后检查进程 PID、监听端口（8080）是否正常，及前 10 条日志是否有报错。
  ```

- 场景 5：远程节点硬件与系统信息采集（192.168.1.102，新节点入网检测）

  ```text
  帮我采集 192.168.1.102 新入网节点的硬件与系统基础信息：
    1. 查看 CPU 详细信息（架构、物理核心数、逻辑核心数、NUMA 节点分布、主频范围）；
    2. 获取系统版本、内核版本、主机名、IP 地址列表；
    3. 查看物理内存总大小、内存通道数、单条内存容量与频率，及磁盘分区布局（重点看 /data 分区大小与文件系统类型），结果以结构化格式返回。
  ```

<a id="OE-智算调优助手"></a>

## 3. OE-智算调优助手

OE-智算调优助手是 openEuler Intelligence 体系下的**异构智算场景专属智能体**，聚焦 AI 训练、推理等核心场景，为 GPU（NVIDIA）、NPU 异构计算环境提供“硬件监控-任务诊断-运维调优”一体化能力。其核心价值在于解决智算场景三大痛点：**异构硬件状态难掌握、任务性能瓶颈难定位、复杂操作门槛高**，即使是非专业运维人员，也能通过自然语言指令快速管控智算资源、排查任务问题，大幅降低智算环境运维成本。

该智能体深度适配 GPU 服务器集群、AI 工作站等部署环境，可实现“实时资源监控-异常自动告警-调优建议生成”的全流程闭环，覆盖从模型训练启动到推理服务稳定运行的全生命周期需求。

### 3.1 MCP 服务矩阵

OE-智算调优助手基于 28 个标准化 MCP 工具，构建“异构硬件监控-智算任务诊断-基础运维支撑”三大核心模块，精准匹配智算场景从“硬件状态感知”到“任务问题解决”的全流程需求，具体服务与工具映射如下：

| 服务分类 | MCP 工具名称（带锚点） | 核心功能定位 | 默认端口 |
|----------|------------------------|--------------|----------|
| 一、异构硬件监控 | [nvidia_mcp](#nvidia_mcp) | 实时监控 NVIDIA GPU 状态（负载、显存占用、温度、驱动版本），支持多卡同时查看 | 12114 |
| | [npu_mcp](#npu_mcp) | 监控 NPU 资源使用情况（算力利用率、内存占用），配置 NPU 任务绑定参数 | 12115 |
| 二、智算任务诊断 | [strace_mcp](#strace_mcp) | 跟踪智算任务进程的系统调用，定位 I/O 瓶颈（如数据读取超时、网络请求阻塞） | 12113 |
| | [top_mcp](#top_mcp) | 查看智算节点 CPU/内存/进程负载，识别抢占 GPU 资源的异常进程 | 12110 |
| 三、智算任务运维 | [shell_generator_mcp](#shell_generator_mcp) | 生成智算场景专属命令（如 GPU 任务绑定指令、模型训练启动脚本） | 12101 |
| | [nohup_mcp](#nohup_mcp) | 后台启动长时智算任务（如 AI 模型训练），避免终端退出导致任务中断 | 12112 |
| | [kill_mcp](#kill_mcp) | 终止异常智算任务（如显存溢出的训练进程、无响应的推理服务） | 12111 |
| 四、网络与安全管控 | [firewalld_mcp](#firewalld_mcp) | 配置智算节点防火墙规则，开放 AI 服务端口（如 TensorBoard 6006 端口、推理服务 8080 端口） | 12130 |
| | [iptables_mcp](#iptables_mcp) | 管控智算节点网络访问，限制未授权设备连接 GPU 节点，保障数据安全 | 12131 |
| 五、文件与数据管理 | [file_transfer_mcp](#file_transfer_mcp) | 传输智算任务数据（如模型文件、训练数据集、checkpoint 文件），支持跨节点批量传输 | 12136 |
| | [file_content_tool_mcp](#file_content_tool_mcp) | 编辑智算任务配置文件（如模型参数 yaml、训练超参 json），支持批量修改 | 12125 |
| | [find_mcp](#find_mcp) | 查找智算节点上的目标文件（如指定版本的模型文件、训练日志） | 13107 |
| | [cat_mcp](#cat_mcp) | 查看智算任务日志（如训练报错日志、推理服务运行日志） | 13115 |
| | [tail_mcp](#tail_mcp) | 实时跟踪智算任务日志，监控训练进度（如 loss 变化、epoch 完成情况） | 13114 |
| 六、基础系统操作 | [ls_mcp](#ls_mcp) | 查看智算任务目录内容（如训练输出文件夹、模型权重文件列表） | 13112 |
| | [rm_mcp](#rm_mcp) | 删除智算节点冗余文件（如过期训练日志、损坏的 checkpoint 文件） | 13110 |
| | [mv_mcp](#mv_mcp) | 移动智算任务文件（如将训练完成的模型文件迁移到存储目录） | 13111 |
| | [touch_mcp](#touch_mcp) | 创建智算任务所需空文件（如日志记录文件、任务标记文件） | 13108 |
| | [mkdir_mcp](#mkdir_mcp) | 创建智算任务目录（如按日期划分的训练输出目录） | 13109 |
| 七、压缩与权限管理 | [tar_mcp](#tar_mcp) | 打包/解包智算任务数据（如压缩训练数据集、解压模型文件包） | 13118 |
| | [zip_mcp](#zip_mcp) | 压缩智算日志文件（如训练全量日志），减少存储占用 | 13119 |
| | [chmod_mcp](#chmod_mcp) | 修改智算任务文件权限（如给模型文件设置只读权限、给启动脚本设置执行权限） | 13117 |
| | [chown_mcp](#chown_mcp) | 修改智算任务文件所有者（如将模型文件授权给训练用户） | 13116 |
| 八、文本处理与同步 | [grep_mcp](#grep_mcp) | 搜索智算日志中的关键词（如 "error" "out of memory" 报错信息） | 13120 |
| | [sed_mcp](#sed_mcp) | 批量替换智算配置文件内容（如修改所有训练脚本的 batch size 参数） | 13121 |
| | [echo_mcp](#echo_mcp) | 将文本内容写入智算任务文件（如向日志文件添加任务标记） | 13125 |
| | [sync_mcp](#sync_mcp) | 将智算任务内存数据强制写入磁盘（如训练 checkpoint 临时文件），避免数据丢失 | 13103 |
| | [head_mcp](#head_mcp) | 查看智算文件前 N 行内容（如快速预览训练配置文件） | 13113 |
| 九、AI 慢节点检测 | [systrace_mcp](#systrace_mcp) | AI 训练任务性能分析与优化建议（基于全栈跟踪数据，识别 Host bound、算子慢、CPU 抢占等性能瓶颈，提供针对性调优方向，降低故障导致的训练成本浪费） | 12145 |

### 3.2 使用案例

以下按“GPU 训练监控、NPU 推理部署、显存溢出排查、跨节点资源对比、训练日志分析”五大智算高频场景分类，提供自然语言交互 Prompt 格式，直接替换节点 IP、任务名、文件路径等关键信息即可使用，所有场景均贴合企业 AI 训练与推理实际运维需求。

- 场景 1：GPU 模型训练实时监控（BERT 预训练任务，GPU 0/1 双卡）

  ```text
  本地正在用 GPU 0/1 双卡运行 BERT 模型预训练（进程名：bert-train），帮我实时监控：
  1. 每 3 秒刷新一次 GPU 0/1 的负载（%）、已用显存/总显存（如 8192MiB/16384MiB）、核心温度；
  2. 跟踪训练日志 /data/train_logs/bert-train-202501.log，当出现 "epoch" "loss" 关键词时，实时输出最新 15 行日志；
  3. 若任一 GPU 温度超 88℃ 或显存占用超 90%，立即触发提醒并给出临时降载建议。
  ```

- 场景 2：NPU 推理服务部署与状态验证（192.168.3.20 NPU 节点）

  ```text
  帮我在 192.168.3.20 NPU 节点部署图像分类推理服务：
  1. 先查看 NPU 0/1 的资源使用情况（算力利用率、内存占用），筛选空闲率超 80% 的 NPU 设备；
  2. 用 nohup 后台启动 "img-cls-infer" 服务，绑定空闲 NPU 设备，指定配置文件 /etc/infer/img-cls.conf，日志输出到 /var/log/infer/img-cls.log；
  3. 启动后检查服务进程 PID、监听端口（9000）是否正常，发送测试请求验证推理响应是否正常。
  ```

- 场景 3：GPU 训练显存溢出问题定位与优化（YOLOv8 训练任务）

  ```text
  本地 YOLOv8 目标检测训练任务（PID：3456）报“CUDA out of memory”后中断，帮我排查优化：
  1. 查看当前所有 GPU 的显存占用详情，定位占用最高的进程及关联任务；
  2. 用 strace 跟踪该任务中断前的系统调用，分析是否存在异常内存申请（如重复加载数据集）；
  3. 结合任务配置给出优化方案（如调整 batch size、启用梯度 checkpoint、使用混合精度训练），并生成修改后的启动命令。
  ```

- 场景 4：跨 GPU 节点资源对比与任务分配（192.168.3.10/11 节点）

  ```text
  需新增 Transformer 模型训练任务，帮我对比 192.168.3.10 和 192.168.3.11 两台 GPU 节点：
  1. 查看两台节点的 GPU 型号、数量、单卡总显存及当前整体显存占用率；
  2. 对比两台节点已运行任务的 GPU 平均负载（10分钟内）、CPU 空闲核心数；
  3. 结合新任务（预计单卡显存占用 12GiB，负载 70%），判断哪台节点更适合部署，并给出任务绑定 GPU 的建议。
  ```

- 场景 5：智算训练日志批量分析与问题定位（多节点训练日志）

  ```text
  192.168.3.10/11/12 三台 GPU 节点的分布式训练任务频繁中断，帮我分析日志：
  1. 批量获取三台节点的训练日志（路径 /data/dist-train/logs/train.log），传输到本地 /tmp/analysis/ 目录；
  2. 搜索所有日志中的 "error" "timeout" "crash" 关键词，统计各错误出现频次及对应节点；
  3. 提取错误前后各 20 行日志内容，定位是否存在节点间通信超时或硬件资源不足问题，生成分析报告。
  ```
  
- 场景 6：AI训练任务慢节点检测

  ```text
  1. 在ai训练任务机器上部署 systrace 采集部件，并完成数据采集 ,参考 https://gitee.com/openeuler/sysTrace/blob/master/docs/0.quickstart.md
  ```

  ```text
  2. 修改/etc/systrace/config 目录下的配置文件，参考 https://gitee.com/openeuler/sysTrace/blob/master/systrace_mcp/README.md
  ```

  ```text
  3. 使用智能体进行对话：帮我分析 ip 机器的 ai 训练情况。
  ```

  <a id="OE-通算调优助手"></a>

## 4. OE-通算调优助手

OE-通算调优助手是 openEuler Intelligence 体系下的**通用计算场景性能优化智能体**，聚焦 NUMA 架构服务器、通用计算节点的性能瓶颈突破，核心能力覆盖“NUMA 资源管控、系统热点追踪、缓存效率分析、全链路性能调优”四大维度。其核心价值在于解决通用计算场景三大痛点：**NUMA 跨节点访问损耗、CPU 性能瓶颈定位难、系统资源调度效率低**，通过智能化工具链整合，让运维与开发人员无需深入掌握底层技术细节，即可实现通用计算任务的性能提升（平均优化幅度可达 10%-30%）。

该智能体深度适配基于 x86/ARM 架构的 NUMA 服务器、通用计算集群，可广泛应用于数据库、大数据处理、高并发服务等通用计算场景，提供从“性能基线采集-瓶颈定位-优化实施-效果验证”的全流程闭环能力。

### 4.1 MCP 服务矩阵

OE-通算调优助手基于 46 个标准化 MCP 工具，构建“NUMA 架构优化-系统性能诊断-通用计算运维-调优效果验证”四大核心模块，精准匹配通用计算场景从“硬件拓扑感知”到“性能持续优化”的全流程需求，具体服务与工具映射如下：

| 服务分类 | MCP 工具名称（带锚点） | 核心功能定位 | 默认端口 |
|----------|------------------------|--------------|----------|
| 一、NUMA 架构优化 | [numa_topo_mcp](#numa_topo_mcp) | 采集 NUMA 硬件拓扑（节点分布、CPU/内存绑定关系）与系统配置，生成拓扑图 | 12203 |
| | [numa_bind_proc_mcp](#numa_bind_proc_mcp) | 启动时将进程绑定到指定 NUMA 节点，避免跨节点内存访问损耗 | 12204 |
| | [numa_rebind_proc_mcp](#numa_rebind_proc_mcp) | 动态调整已运行进程的 NUMA 绑定，实时优化资源分配 | 12205 |
| | [numa_container_mcp](#numa_container_mcp) | 监控 Docker 容器的 NUMA 内存访问模式，优化容器化应用性能 | 12214 |
| | [numastat_mcp](#numastat_mcp) | 统计系统整体 NUMA 内存访问情况（本地/远程访问比例），识别跨节点访问过高问题 | 12210 |
| | [numa_cross_node_mcp](#numa_cross_node_mcp) | 定位导致跨节点内存访问过高的进程，量化性能损耗 | 12211 |
| | [numa_perf_compare_mcp](#numa_perf_compare_mcp) | 对比不同 NUMA 绑定策略下的任务性能（响应时间、吞吐量），筛选最优方案 | 12208 |
| | [numa_diagnose_mcp](#numa_diagnose_mcp) | 通过 NUMA 绑定控制变量法，定位硬件级性能异常（如内存控制器瓶颈） | 12209 |
| 二、系统性能诊断 | [hotspot_trace_mcp](#hotspot_trace_mcp) | 快速定位系统/进程的 CPU 热点函数（基于 perf 采样），识别计算瓶颈 | 12216 |
| | [cache_miss_audit_mcp](#cache_miss_audit_mcp) | 分析 CPU 缓存失效（L1/L2/L3）原因，量化缓存损耗对性能的影响 | 12217 |
| | [func_timing_trace_mcp](#func_timing_trace_mcp) | 精准测量函数执行时间与调用栈，定位耗时过长的关键路径 | 12218 |
| | [strace_syscall_mcp](#strace_syscall_mcp) | 跟踪进程系统调用频率与耗时，排查不合理的 I/O 或网络调用 | 12219 |
| | [perf_interrupt_mcp](#perf_interrupt_mcp) | 分析高频中断源（如网卡、定时器）对 CPU 的占用，定位中断导致的性能下降 | 12220 |
| | [flame_graph_mcp](#flame_graph_mcp) | 生成 CPU 火焰图/内存火焰图，可视化展示函数调用栈与性能瓶颈分布 | 12222 |
| 三、通用计算监控 | [lscpu_mcp](#lscpu_mcp) | 采集 CPU 架构细节（核心数、主频、缓存大小、NUMA 节点关联） | 12202 |
| | [top_mcp](#top_mcp) | 实时监控 CPU/内存/进程负载，聚焦通用计算任务的资源占用趋势 | 12110 |
| | [vmstat_mcp](#vmstat_mcp) | 采集系统资源交互指标（上下文切换、IOPS、Swap 使用），识别瓶颈点 | 13101 |
| | [sar_mcp](#sar_mcp) | 周期性记录系统性能数据（CPU 使用率、内存页交换、网络吞吐量），支持历史回溯 | 13102 |
| | [free_mcp](#free_mcp) | 查看系统内存/Swap 整体使用状态，识别内存不足对通用计算的影响 | 13100 |
| 四、调优任务运维 | [shell_generator_mcp](#shell_generator_mcp) | 生成 NUMA 绑定、性能测试等场景的专属命令（如 numactl 启动指令） | 12101 |
| | [nohup_mcp](#nohup_mcp) | 后台启动长时性能测试任务（如压力测试、基准测试），避免终端中断 | 12112 |
| | [kill_mcp](#kill_mcp) | 终止异常性能测试进程（如资源耗尽的压力测试任务） | 12111 |
| | euler-copilot-tune_mcp | 调用 Euler 调优模型，生成基于场景的自动化调优建议（如内核参数调整） | 12147 |
| 五、文件与配置管理 | [file_transfer_mcp](#file_transfer_mcp) | 传输性能测试数据、调优配置文件（如基准测试结果、NUMA 绑定脚本） | 12136 |
| | [file_content_tool_mcp](#file_content_tool_mcp) | 编辑系统配置文件（如内核参数 sysctl.conf、应用性能配置） | 12125 |
| | [grep_mcp](#grep_mcp) | 搜索性能日志中的关键指标（如 "cache miss" "numa node"） | 13120 |
| | [sed_mcp](#sed_mcp) | 批量修改调优配置文件（如全局调整应用的内存分配策略） | 13121 |
| | [cat_mcp](#cat_mcp) | 查看性能测试日志、系统监控报告（如 sar 历史数据） | 13115 |
| | [tail_mcp](#tail_mcp) | 实时跟踪性能测试日志（如压力测试的 QPS 变化） | 13114 |
| 六、基础系统操作 | [ls_mcp](#ls_mcp) | 查看性能测试目录、调优工具路径（如 perf 报告存放目录） | 13112 |
| | [mkdir_mcp](#mkdir_mcp) | 创建性能测试工作目录（如按日期划分的基准测试结果目录） | 13109 |
| | [rm_mcp](#rm_mcp) | 删除冗余性能日志、过期测试数据 | 13110 |
| | [mv_mcp](#mv_mcp) | 归档性能测试结果（如将调优前后的对比数据移动到归档目录） | 13111 |
| | [sync_mcp](#sync_mcp) | 将性能测试临时数据写入磁盘（如基准测试中间结果），避免数据丢失 | 13103 |
| 七、压缩与权限管理 | [tar_mcp](#tar_mcp) | 打包性能测试日志（如全量 sar 监控数据），减少存储空间占用 | 13118 |
| | [zip_mcp](#zip_mcp) | 压缩调优配置文件包，便于跨节点分发 | 13119 |
| | [chmod_mcp](#chmod_mcp) | 修改性能测试工具、调优脚本的执行权限 | 13117 |
| | [chown_mcp](#chown_mcp) | 授权调优用户访问性能监控数据文件 | 13116 |
| 八、远程与网络管控 | [remote_info_mcp](#remote_info_mcp) | 获取远程通用计算节点的基础信息（系统版本、硬件配置） | 12100 |
| | [firewalld_mcp](#firewalld_mcp) | 配置性能监控工具的端口访问规则（如允许远程访问 sar 数据端口） | 12130 |
| | [iptables_mcp](#iptables_mcp) | 管控通用计算节点的网络访问，保障性能测试环境安全 | 12131 |

### 4.2 使用案例

以下按“NUMA 绑定优化、CPU 缓存问题诊断、系统调优效果验证”三大高频场景分类，提供自然语言交互 Prompt 格式，直接替换进程名、节点信息、阈值等关键信息即可使用。

- 场景 1：MySQL 数据库 NUMA 绑定优化（进程名：mysqld）

  ```text
  192.168.3.10 这台 MySQL 服务器查询延迟高，帮我做 NUMA 优化：
  1. 查看这台服务器的 NUMA 拓扑和各节点内存使用率；
  2. 将 mysqld 进程绑定到 NUMA 节点 0，避免跨节点访问；
  3. 优化后对比查询延迟是否降低，给出优化效果数据。
  ```

- 场景 2：CPU 缓存未命中率过高问题诊断（应用名：order-service）

  ```text
  本地运行的“order-service”应用吞吐量低，怀疑是缓存问题：
  1. 审计该应用进程的 L3 缓存未命中率，若超过 5% 标记为异常；
  2. 定位导致缓存未命中的高频调用函数；
  3. 给优化建议（如数据预加载、函数逻辑调整）。
  ```

- 场景 3：容器化应用 NUMA 内存访问监控（容器名：payment-container）

  ```text
  帮我监控 Docker 容器“payment-container”：
  1. 查看该容器当前的 NUMA 节点内存访问分布；
  2. 统计跨节点内存访问的占比，若超过 10% 提醒；
  3. 给出容器 NUMA 绑定的配置方案。
  ```

- 场景 4：NUMA 调优效果对比（调优前后）

  ```text
  已给 192.168.4.12 节点的“user-service”应用做 NUMA 绑定（绑定节点 1），帮我验证效果：
  1. 对比调优前/后该应用的 CPU 使用率（峰值/平均）、接口响应时间（P95/P99）；
  2. 查看调优后 NUMA 节点 1 的内存访问命中率（目标提升至 90% 以上）及跨节点访问量；
  3. 模拟 2000 并发请求压测，对比调优前/后的服务吞吐量、错误率，生成可视化对比报告（含关键指标趋势图）。
  ```

- 场景 5：通用计算节点高频中断导致 CPU 占用诊断（192.168.4.13 节点）

  ```text
  192.168.4.13 通用计算节点的空闲 CPU 使用率超 30%，怀疑高频中断问题：
  1. 定位该节点的高频中断源（如网卡中断、时钟中断），统计各中断源的 CPU 占用率；
  2. 分析高频中断对通用计算任务（如数据处理服务）的影响（如任务上下文切换次数增加、执行延迟变长）；
  3. 给出中断优化方案（如网卡中断队列绑定到独立 NUMA 节点 CPU、调整时钟中断频率），并验证优化后空闲 CPU 使用率是否降至 15% 以下。
  ```

- 场景 6：通用euler-copilot-tune对mysql服务进行调优

  ```text
  1. 修改 /etc/euler-copilot-tune/config 目录下的 .env.yaml 和 app_config.yaml 文件，配置目标服务器和调优服务，参考 https://gitee.com/openeuler/A-Tune/tree/euler-copilot-tune/#%E9%85%8D%E7%BD%AE%E6%96%87%E4%BB%B6%E5%87%86%E5%A4%87，并重启调优 MCP 服务（systemctl restart tune-mcpserver）；
  2. 在智能体中使用：帮我采集 mysql 服务的性能数据、分析性能瓶颈、进行参数推荐、开始调优。
  ```

  <a id="OE-容器镜像助手"></a>

## 5. OE-容器镜像助手

OE-容器镜像助手是 openEuler Intelligence 体系下的**容器与虚拟化全生命周期管理智能体**，聚焦 Docker 容器运维、QEMU 虚拟化管控、容器 NUMA 优化三大核心场景，提供“镜像管理-容器调度-虚拟化部署-性能优化”一体化能力。其核心价值在于解决容器虚拟化环境三大痛点：**多工具切换效率低、容器与硬件资源适配难、虚拟化部署操作复杂**，通过标准化 MCP 工具链整合，让运维人员无需掌握多套技术栈，即可实现容器与虚拟化环境的高效管控。

该智能体深度适配 Docker 19.03+、QEMU 5.0+ 版本，可广泛应用于容器化应用部署（如微服务）、轻量级虚拟化测试（如多系统环境）、容器 NUMA 性能优化（如高并发容器服务）等场景，覆盖从“镜像拉取-容器运行-虚拟化部署-资源调优”的全流程需求。

### 5.1 MCP 服务矩阵

OE-容器镜像助手基于 28 个标准化 MCP 工具，构建“Docker 容器管理-QEMU 虚拟化管控-容器 NUMA 优化-基础运维支撑”四大核心模块，精准匹配容器与虚拟化场景的全生命周期管理需求，具体服务与工具映射如下：

| 服务分类               | MCP 工具名称（带锚点）       | 核心功能定位                                   | 默认端口  |
|------------------------|-----------------------------|------------------------------------------------|-----------|
| 一、Docker 容器管理    | [docker_mcp](#docker_mcp)    | 实现 Docker 容器全生命周期操作（创建/启动/停止/删除/重启），支持端口映射、数据卷挂载、重启策略配置 | 12133     |
|                        | [numa_bind_docker_mcp](#numa_bind_docker_mcp) | 为 Docker 容器配置 NUMA 节点绑定，优化容器内存访问性能，避免跨节点损耗 | 12206     |
|                        | [strace_mcp](#strace_mcp)    | 跟踪容器进程的系统调用，定位容器异常（如启动失败、资源访问报错） | 12113     |
| 二、QEMU 虚拟化管控    | [qemu_mcp](#qemu_mcp)        | 管理 QEMU 虚拟机（创建/启动/关闭/销毁），支持虚拟机配置（CPU 核心数、内存大小、磁盘挂载） | 12134     |
|                        | [file_transfer_mcp](#file_transfer_mcp) | 实现本地与 QEMU 虚拟机、Docker 容器间的文件传输（如虚拟机镜像文件、容器配置文件） | 12136     |
| 三、镜像与配置管理     | [file_content_tool_mcp](#file_content_tool_mcp) | 编辑容器/虚拟机配置文件（如 Docker Compose yaml、QEMU 启动脚本），支持批量修改 | 12125     |
|                        | [grep_mcp](#grep_mcp)        | 搜索容器日志、虚拟机运行日志中的关键词（如“error”“timeout”“numa”） | 13120     |
|                        | [sed_mcp](#sed_mcp)          | 批量替换容器/虚拟机配置参数（如全局调整容器内存限制、虚拟机网络配置） | 13121     |
|                        | [cat_mcp](#cat_mcp)          | 查看容器日志（如容器启动日志、应用运行日志）、QEMU 虚拟机状态信息 | 13115     |
|                        | [tail_mcp](#tail_mcp)        | 实时跟踪容器日志（如微服务容器的请求日志）、QEMU 虚拟机启动过程日志 | 13114     |
| 四、容器运维辅助       | [shell_generator_mcp](#shell_generator_mcp) | 生成容器/虚拟化场景专属命令（如 Docker 容器 NUMA 绑定指令、QEMU 虚拟机启动命令） | 12101     |
|                        | [kill_mcp](#kill_mcp)        | 终止异常容器进程、无响应的 QEMU 虚拟机进程 | 12111     |
|                        | [remote_info_mcp](#remote_info_mcp) | 获取远程容器节点、虚拟化节点的基础信息（系统版本、Docker/QEMU 版本、硬件配置） | 12100     |
| 五、网络与安全管控     | [firewalld_mcp](#firewalld_mcp) | 配置容器/虚拟机节点的防火墙规则，开放容器服务端口（如 8080 应用端口）、虚拟机远程访问端口（如 22 SSH 端口） | 12130     |
|                        | [iptables_mcp](#iptables_mcp)  | 管控容器网络访问（如限制容器对外连接、设置虚拟机网络转发规则），保障环境安全 | 12131     |
| 六、基础文件操作       | [ls_mcp](#ls_mcp)            | 查看容器目录内容（如容器内应用文件列表）、QEMU 虚拟机镜像文件目录 | 13112     |
|                        | [mkdir_mcp](#mkdir_mcp)      | 创建容器数据目录、QEMU 虚拟机镜像存储目录（如按容器名称、虚拟机编号划分） | 13109     |
|                        | [rm_mcp](#rm_mcp)            | 删除冗余容器、过期 QEMU 虚拟机、无用镜像文件（如未使用的 Docker 镜像、损坏的虚拟机磁盘文件） | 13110     |
|                        | [mv_mcp](#mv_mcp)            | 移动容器数据卷、QEMU 虚拟机镜像文件（如将备份的虚拟机镜像迁移到存储目录） | 13111     |
|                        | [touch_mcp](#touch_mcp)      | 创建容器/虚拟机所需空文件（如容器启动标记文件、虚拟机配置模板文件） | 13108     |
|                        | [sync_mcp](#sync_mcp)        | 将容器内存数据、QEMU 虚拟机临时数据强制写入磁盘（如容器数据卷缓存、虚拟机内存快照），避免数据丢失 | 13103     |
| 七、压缩与权限管理     | [tar_mcp](#tar_mcp)          | 打包/解包容器数据卷、QEMU 虚拟机镜像文件（如压缩容器备份数据、解压虚拟机镜像包） | 13118     |
|                        | [zip_mcp](#zip_mcp)          | 压缩容器日志、虚拟机配置文件，减少存储空间占用 | 13119     |
|                        | [chmod_mcp](#chmod_mcp)      | 修改容器数据卷、虚拟机文件的权限（如给容器配置文件设置读写权限、给虚拟机启动脚本设置执行权限） | 13117     |
|                        | [chown_mcp](#chown_mcp)      | 修改容器目录、虚拟机文件的所有者（如将容器数据卷授权给容器运行用户） | 13116     |
| 八、文件内容查看       | [head_mcp](#head_mcp)        | 查看容器配置文件、QEMU 启动脚本的前 N 行内容（如快速预览 Docker Compose 配置） | 13113     |
|                        | [find_mcp](#find_mcp)        | 查找容器相关文件（如指定名称的容器日志、Docker 镜像文件）、QEMU 虚拟机镜像（如按大小、修改时间筛选） | 13107     |
|                        | [echo_mcp](#echo_mcp)        | 向容器配置文件、虚拟机日志文件写入内容（如向容器启动脚本添加环境变量、向虚拟机日志添加标记） | 13125     |

### 5.2 使用案例

以下按“Docker 容器管理、QEMU 虚拟机管控、容器 NUMA 优化”三大高频场景分类，提供自然语言交互 Prompt 格式，直接替换容器名、虚拟机名、节点 IP 等关键信息即可使用。

- 场景 1：Docker 容器部署与日志监控（容器名：web-app，镜像名：nginx:1.24）

  ```text
  帮我在本地部署 Nginx 容器并监控：
  1. 拉取 nginx:1.24 镜像，创建名为“web-app”的容器，暴露 80 端口并挂载 /home/nginx/html 到容器内 /usr/share/nginx/html；
  2. 启动容器后，实时跟踪容器日志，筛选“error”关键词；
  3. 查看容器的 CPU/内存使用情况，确认是否正常运行。
  ```

- 场景 2：QEMU 虚拟机创建与配置（虚拟机名：test-vm，内存：4G，CPU：2 核）

  ```text
  帮我创建 QEMU 虚拟机：
  1. 基于 /data/images/euleros.qcow2 镜像创建名为“test-vm”的虚拟机，配置 2 核 CPU、4G 内存、100G 磁盘；
  2. 启动虚拟机并查看其运行状态；
  3. 配置虚拟机网络为桥接模式，确保能访问外网。
  ```

- 场景 3：容器 NUMA 绑定优化（容器名：db-container，NUMA 节点：1）

  ```text
  192.168.4.10 宿主机上的“db-container”容器（MySQL 服务）响应慢，帮我优化：
  1. 查看该宿主机的 NUMA 拓扑，确认节点 1 的 CPU/内存资源；
  2. 给“db-container”配置 NUMA 绑定，指定使用节点 1 的资源；
  3. 优化后查看容器的内存访问延迟是否降低。
  ```

- 场景 4：容器镜像跨节点迁移（源节点：192.168.4.10，目标节点：192.168.4.11，镜像名：app:v1.0）

  ```text
  帮我迁移容器镜像：
  1. 在 192.168.4.10 上导出“app:v1.0”镜像为 /data/backups/app-v1.0.tar；
  2. 将该 tar 包传输到 192.168.4.11 的 /data/images 目录；
  3. 在目标节点导入该镜像并验证是否可用。
  ```

## 6. MCP 总览

当前已集成 **50+ 核心功能模块**，能力覆盖运维全场景，具体包含七大方向：

1. 硬件信息采集：支持 CPU 架构解析、NUMA 拓扑查询、GPU 负载监控，为底层资源分析提供数据基线；
2. 系统资源监控：实时采集内存使用状态、CPU 负载变化、网络流量数据，动态捕捉资源瓶颈；
3. 进程与服务管控：实现进程启停控制、信号量含义查询、后台进程稳定执行，保障服务运行可控；
4. 文件操作管理：覆盖文件增删改查、压缩解压（tar/zip 格式）、权限与所有权配置，满足文件全生命周期需求；
5. 性能诊断优化：**内置火焰图生成能力**（基于系统原生 `perf` 工具封装）、系统调用排查、CPU 缓存失效定位，无需额外部署独立性能分析工具，即可助力深度性能调优；
6. 虚拟化与容器辅助：支持 Docker 容器 NUMA 绑定、QEMU 虚拟机管理，适配虚拟化运维场景；
7. 网络扫描探测：可执行 IP/网段探测、端口识别，快速完成网络基础巡检。

上述能力仅依赖系统原生基础工具（如 `perf`），无需额外部署第三方独立运维套件，即可满足从基础运维到深度性能优化的全流程需求。

在部署与迭代层面，具备两大核心优势：

- **双模式适配**：支持本地直接调用与远程 SSH 管控，兼顾单机运维与多节点集群管理场景；
- **高稳定性与可扩展性**：单个模块的升级、维护不影响整体运行；开源特性允许社区开发者参与功能迭代与 Bug 修复，持续丰富模块能力，适配更多新兴运维场景。

### 6.1 MCP_Server列表

| 端口号 | 服务名称 | 目录路径 | 简介 |
|--------|----------|----------|------|
| 12100 | [remote_info_mcp](#remote_info_mcp) | mcp_center/servers/remote_info_mcp | 获取端点信息 |
| 12101 | [shell_generator_mcp](#shell_generator_mcp) | mcp_center/servers/shell_generator_mcp | 生成 & 执行 shell 命令 |
| 12110 | [top_mcp](#top_mcp) | mcp_center/servers/top_mcp | 获取系统负载信息 |
| 12111 | [kill_mcp](#kill_mcp) | mcp_center/servers/kill_mcp | 控制进程 & 查看进程信号量含义 |
| 12112 | [nohup_mcp](#nohup_mcp) | mcp_center/servers/nohup_mcp | 后台执行进程 |
| 12113 | [strace_mcp](#strace_mcp) | mcp_center/servers/strace_mcp | 跟踪进程信息，可用于异常情况分析 |
| 12114 | [nvidia_mcp](#nvidia_mcp) | mcp_center/servers/nvidia_mcp | GPU 负载信息查询 |
| 12115 | [npu_mcp](#npu_mcp) | mcp_center/servers/npu_mcp | NPU 的查询和控制 |
| 12116 | [iftop_mcp](#iftop_mcp) | mcp_center/servers/iftop_mcp | 网络流量监控 |
| 12117 | [nload_mcp](#nload_mcp) | mcp_center/servers/nload_mcp | Nload 带宽监控 |
| 12118 | [netstat_mcp](#netstat_mcp) | mcp_center/servers/netstat_mcp | netstat 网络连接监控 |
| 12119 | [lsof_mcp](#lsof_mcp) | mcp_center/servers/lsof_mcp | 快速排查文件占用冲突、网络连接异常及进程资源占用问题 |
| 12120 | [ifconfig_mcp](#ifconfig_mcp) | mcp_center/servers/ifconfig_mcp | ifconfig 网络接口信息监控 |
| 12121 | [ethtool_mcp](#ethtool_mcp) | mcp_center/servers/ethtool_mcp | ethtool 网卡信息查询，特性情况，网卡设置 |
| 12122 | [tshark_mcp](#tshark_mcp) | mcp_center/servers/tshark_mcp | 捕获、显示和分析网络流量 |
| 12125 | [file_content_tool_mcp](#file_content_tool_mcp) | mcp_center/servers/file_content_tool_mcp | 文件内容增删改查 |
| 12130 | [firewalld_mcp](#firewalld_mcp) | mcp_center/servers/firewalld_mcp | Firewalld 网络防火墙管理工具 |
| 12131 | [iptables_mcp](#iptables_mcp) | mcp_center/servers/iptables_mcp | iptables 防火墙管理工具 |
| 12133 | [docker_mcp](#docker_mcp) | mcp_center/servers/docker_mcp | docker 工具 |
| 12134 | [qemu_mcp](#qemu_mcp) | mcp_center/servers/qemu_mcp | Qemu 虚拟机管理工具 |
| 12135 | [nmap_mcp](#nmap_mcp) | mcp_center/servers/nmap_mcp | Nmap 扫描 IP |
| 12136 | [file_transfer_mcp](#file_transfer_mcp) | mcp_center/servers/file_transfer_mcp | 文件传输/下载 |
| 12145 | [systrace_mcp](#systrace_mcp) | mcp_center/servers/systrace/systrace_mcp | 开启 MCP Server 服务 |
| 12146 | systrace_openapi_mcp | mcp_center/servers/systrace/systrace_mcp | 开启 OpenAPI Server 服务 |
| 12147 | [euler-copilot-tune_mcp](#euler-copilot-tune_mcp) | mcp_center/servers/euler-copilot-tune_mcp | 调优 MCP 服务 |
| 12202 | [lscpu_mcp](#lscpu_mcp) | mcp_center/servers/lscpu_mcp | CPU 架构等静态信息收集 |
| 12203 | [numa_topo_mcp](#numa_topo_mcp) | mcp_center/servers/numa_topo_mcp | 查询 NUMA 硬件拓扑与系统配置 |
| 12204 | [numa_bind_proc_mcp](#numa_bind_proc_mcp) | mcp_center/servers/numa_bind_proc_mcp | 启动时绑定进程到指定 NUMA 节点 |
| 12205 | [numa_rebind_proc_mcp](#numa_rebind_proc_mcp) | mcp_center/servers/numa_rebind_proc_mcp | 修改已启动进程的 NUMA 绑定 |
| 12206 | [numa_bind_docker_mcp](#numa_bind_docker_mcp) | mcp_center/servers/numa_bind_docker_mcp | 为 Docker 容器配置 NUMA 绑定 |
| 12208 | [numa_perf_compare_mcp](#numa_perf_compare_mcp) | mcp_center/servers/numa_perf_compare_mcp | 用 NUMA 绑定控制测试变量 |
| 12209 | [numa_diagnose_mcp](#numa_diagnose_mcp) | mcp_center/servers/numa_diagnose_mcp | 用 NUMA 绑定定位硬件问题 |
| 12210 | [numastat_mcp](#numastat_mcp) | mcp_center/servers/numastat_mcp | 查看系统整体 NUMA 内存访问状态 |
| 12211 | [numa_cross_node_mcp](#numa_cross_node_mcp) | mcp_center/servers/numa_cross_node_mcp | 定位跨节点内存访问过高的进程 |
| 12214 | [numa_container_mcp](#numa_container_mcp) | mcp_center/servers/numa_container_mcp | 监控 Docker 容器的 NUMA 内存访问 |
| 12216 | [hotspot_trace_mcp](#hotspot_trace_mcp) | mcp_center/servers/hotspot_trace_mcp | 快速定位系统/进程的 CPU 性能瓶颈 |
| 12217 | [cache_miss_audit_mcp](#cache_miss_audit_mcp) | mcp_center/servers/cache_miss_audit_mcp | 定位 CPU 缓存失效导致的性能损耗 |
| 12218 | [func_timing_trace_mcp](#func_timing_trace_mcp) | mcp_center/servers/func_timing_trace_mcp | 精准测量函数执行时间（含调用栈） |
| 12219 | [strace_syscall_mcp](#strace_syscall_mcp) | mcp_center/servers/strace_syscall_mcp | 排查不合理的系统调用（高频/耗时） |
| 12220 | [perf_interrupt_mcp](#perf_interrupt_mcp) | mcp_center/servers/perf_interrupt_mcp | 定位高频中断导致的 CPU 占用 |
| 12222 | [flame_graph_mcp](#flame_graph_mcp) | mcp_center/servers/flame_graph_mcp | 火焰图生成：可视化展示性能瓶颈 |
| 13100 | [free_mcp](#free_mcp) | mcp_center/servers/free_mcp | 获取系统内存整体状态 |
| 13101 | [vmstat_mcp](#vmstat_mcp) | mcp_center/servers/vmstat_mcp | 系统资源交互瓶颈信息采集 |
| 13102 | [sar_mcp](#sar_mcp) | mcp_center/servers/sar_mcp | 系统资源监控与故障诊断 |
| 13103 | [sync_mcp](#sync_mcp) | mcp_center/servers/sync_mcp | 内存缓冲区数据写入磁盘 |
| 13104 | [swapon_mcp](#swapon_mcp) | mcp_center/servers/swapon_mcp | 查看 swap 设备状态 |
| 13105 | [swapoff_mcp](#swapoff_mcp) | mcp_center/servers/swapoff_mcp | swap 设备停用 |
| 13106 | [fallocate_mcp](#fallocate_mcp) | mcp_center/servers/fallocate_mcp | 临时创建并启用 swap 文件 |
| 13107 | [find_mcp](#find_mcp) | mcp_center/servers/find_mcp | 文件查找 |
| 13108 | [touch_mcp](#touch_mcp) | mcp_center/servers/touch_mcp | 文件创建与时间校准 |
| 13109 | [mkdir_mcp](#mkdir_mcp) | mcp_center/servers/mkdir_mcp | 文件夹创建 |
| 13110 | [rm_mcp](#rm_mcp) | mcp_center/servers/rm_mcp | 文件删除 |
| 13111 | [mv_mcp](#mv_mcp) | mcp_center/servers/mv_mcp | 文件移动或重命名 |
| 13112 | [ls_mcp](#ls_mcp) | mcp_center/servers/ls_mcp | 查看目录内容 |
| 13113 | [head_mcp](#head_mcp) | mcp_center/servers/head_mcp | 文件开头内容查看工具 |
| 13114 | [tail_mcp](#tail_mcp) | mcp_center/servers/tail_mcp | 文件末尾内容查看工具 |
| 13115 | [cat_mcp](#cat_mcp) | mcp_center/servers/cat_mcp | 文件内容查看工具 |
| 13116 | [chown_mcp](#chown_mcp) | mcp_center/servers/chown_mcp | 文件所有者修改工具 |
| 13117 | [chmod_mcp](#chmod_mcp) | mcp_center/servers/chmod_mcp | 文件权限修改工具 |
| 13118 | [tar_mcp](#tar_mcp) | mcp_center/servers/tar_mcp | 文件压缩解压工具 |
| 13119 | [zip_mcp](#zip_mcp) | mcp_center/servers/zip_mcp | 文件压缩解压工具 |
| 13120 | [grep_mcp](#grep_mcp) | mcp_center/servers/grep_mcp | 文件内容搜索工具 |
| 13121 | [sed_mcp](#sed_mcp) | mcp_center/servers/sed_mcp | 文本处理工具 |
| 13125 | [echo_mcp](#echo_mcp) | mcp_center/servers/echo_mcp | 文本写入工具 |

### 6.2 MCP_Server 详情

本部分将针对核心 MCP 服务模块展开详细说明，通过“服务-工具-功能-参数-返回值”的结构化表格，清晰呈现每个 MCP_Server 的具体能力：包括其包含的工具列表、各工具的核心作用、调用时需传入的关键参数，以及执行后返回的结构化数据格式。旨在为运维人员提供“即查即用”的操作指南，确保能快速理解服务功能、正确配置参数、高效解析返回结果，满足日常运维、性能分析与故障排查的实际需求。

#### remote_info_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | top_collect_tool | 获取目标设备（本地/远程）中**内存占用排名前 k 个**的进程信息，k 支持自定义配置 | - `host`：远程主机名/IP（本地采集可不填）<br>- `k`：需获取的进程数量（默认 5） | 进程列表（含 `pid` 进程 ID、`name` 进程名称、`memory` 内存使用量（MB）） |
| | get_process_info_tool | 查询指定 PID 进程的**详细运行信息**，支持本地与远程进程信息获取 | - `host`：远程主机名/IP（本地查询可不填）<br>- `pid`：需查询的进程 ID（必传，且为正整数） | 进程详细字典（含 `status` 状态、`create_time` 创建时间、`cpu_times` CPU 时间、`memory_info` 内存信息、`open_files` 打开文件列表、`connections` 网络连接等） |
| | change_name_to_pid_tool | 根据进程名称反向查询对应的**PID 列表**，解决"已知进程名查 ID"的场景需求 | - `host`：远程主机名/IP（本地查询可不填）<br>- `name`：需查询的进程名称（必传，不能为空） | 以空格分隔的 PID 字符串（如 "1234 5678"） |
| **remote_info_mcp** | get_cpu_info_tool | 采集目标设备的 CPU 硬件与使用状态信息，包括核心数、频率、核心使用率 | - `host`：远程主机名/IP（本地采集可不填） | CPU 信息字典（含 `physical_cores` 物理核心数、`total_cores` 逻辑核心数、`max_frequency` 最大频率（MHz）、`cpu_usage` 各核心使用率（%）等） |
| | memory_anlyze_tool | 分析目标设备的内存使用情况，计算总内存、可用内存及使用率 | - `host`：远程主机名/IP（本地采集可不填） | 内存信息字典（含 `total` 总内存（MB）、`available` 可用内存（MB）、`used` 已用内存（MB）、`percent` 内存使用率（%）等） |
| | get_disk_info_tool | 采集目标设备的磁盘分区信息与容量使用状态，过滤临时文件系统（tmpfs/devtmpfs） | - `host`：远程主机名/IP（本地采集可不填） | 磁盘列表（含 `device` 设备名、`mountpoint` 挂载点、`fstype` 文件系统类型、`total` 总容量（GB）、`percent` 磁盘使用率（%）等） |
| | get_os_info_tool | 获取目标设备的操作系统类型与版本信息 | - `host`：远程主机名/IP（本地采集可不填） | 操作系统信息字符串（如 "openEuler 22.03 LTS"） |
| | get_network_info_tool | 采集目标设备的网络接口信息，包括 IP 地址、MAC 地址、接口启用状态 | - `host`：远程主机名/IP（本地采集可不填） | 网络接口列表（含 `interface` 接口名、`ip_address` IP 地址、`mac_address` MAC 地址、`is_up` 接口是否启用（布尔值）等） |
| | write_report_tool | 将系统信息分析结果写入本地报告文件，自动生成带时间戳的文件路径 | - `report`：报告内容字符串（必传，不能为空） | 报告文件路径字符串（如 "/reports/system_report_20240520_153000.txt"） |
| | telnet_test_tool | 测试目标主机指定端口的 Telnet 连通性，验证端口开放状态 | - `host`：远程主机名/IP（必传）<br>- `port`：端口号（1-65535，必传） | 连通性结果（布尔值：`True` 成功，`False` 失败） |
| | ping_test_tool | 测试目标主机的 ICMP Ping 连通性，验证主机网络可达性 | - `host`：远程主机名/IP（必传） | 连通性结果（布尔值：`True` 成功，`False` 失败） |
| | get_dns_info_tool | 采集目标设备的 DNS 配置信息，包括 DNS 服务器列表与搜索域 | - `host`：远程主机名/IP（本地采集可不填） | DNS 信息字典（含 `nameservers` DNS 服务器列表、`search` 搜索域列表） |
| | perf_data_tool | 采集目标设备的实时性能数据，支持"指定进程"或"全系统"性能监控 | - `host`：远程主机名/IP（本地采集可不填）<br>- `pid`：进程 ID（全系统监控可不填） | 性能数据字典（含 `cpu_usage` CPU 使用率（%）、`memory_usage` 内存使用率（%）、`io_counters` I/O 统计信息） |

---

#### shell_generator_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **shell_generator** | cmd_generator_tool | 1. 系统信息采集：指定 `host` 则通过 SSH 获取远程主机信息（系统发行版、运行时间、根分区/内存使用、Top5 内存进程），不指定则采集本机信息；2. LLM 命令生成：将系统信息与用户需求传入大语言模型，生成符合场景的 Linux shell 命令；3. 格式校验：提取 LLM 返回的 YAML 格式命令块，输出有效命令字符串 | - `host`（可选）：远程主机名/IP，需提前在配置文件配置主机 IP、端口、用户名、密码，不提供则操作本机<br>- `goal`（必填）：用户运维需求描述（如"查询根分区使用率""查看内存占用最高的 3 个进程"） | 符合场景的 Linux shell 命令字符串（经格式校验后的有效命令） |
| | cmd_executor_tool | 1. 多场景命令执行：支持本地或远程主机执行 shell 命令；2. 远程执行：通过 SSH 连接远程主机（基于配置文件信息），执行命令并捕获标准输出/错误输出，执行后关闭连接；3. 本地执行：通过 `subprocess` 模块执行命令，返回结果；4. 错误处理：命令执行出错（权限不足、命令不存在等）时，返回具体错误信息 | - `host`（可选）：远程主机名/IP，需与配置文件信息匹配，不提供则操作本机<br>- `command`（必填）：需执行的 Linux shell 命令字符串（建议由 `cmd_generator_tool` 生成） | 1. 命令执行成功：返回命令标准输出内容；2. 命令执行失败：返回具体错误信息（如"权限不足：Permission denied""命令不存在：command not found"） |

---

#### top_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **top_mcp** | top_collect_tool | 获取目标设备（本地/远程）中**内存占用排名前 k 个**的进程信息，k 支持自定义配置 | - `host`：远程主机名/IP（本地采集可不填）<br>- `k`：需获取的进程数量（默认 5） | 进程列表（含 `pid` 进程 ID、`name` 进程名称、`memory` 内存使用量（MB）） |
| | top_servers_tool | 通过 `top` 命令获取指定目标（本地/远程服务器）的负载信息，涵盖 CPU、内存、磁盘、网络及进程状态，为运维、性能分析和故障排查提供数据支持 | - `host`：远程主机名/IP（本地采集可不填）<br>- `dimensions`：需采集的维度（可选值：cpu、memory、disk、network）<br>- `include_processes`：是否包含进程信息（布尔值）<br>- `top_n`：需返回的进程数量（整数） | - `server_info`：服务器基本信息<br>- `metrics`：请求维度的统计结果（如 CPU 使用率、内存占用率）<br>- `processes`：进程列表（仅 `include_processes`=True 时返回）<br>- `error`：错误信息（如连接失败，无错误则为 null） |

---

#### kill_mcp

| MCP_Server 名称 | 工具名称 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|----------|----------|--------------|--------------|
| **kill_mcp** | `kill_process` | 通过 `kill` 指令发送信号终止进程（支持本地/远程，默认 SIGTERM(15)） | - `pid`：需终止的进程 PID（正整数，必填）<br>- `signal`：信号量（整数，可选，常用值：9(SIGKILL)、15(SIGTERM)）<br>- `host`：远程主机名/IP（字符串，本地操作可不填，需与配置文件匹配） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（字符串）<br>- `data`：包含操作详情的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP（本地为 `localhost`）<br>&nbsp;&nbsp;- `pid`：被操作的进程 PID<br>&nbsp;&nbsp;- `signal`：发送的信号量编号 |
| | `pause_process` | 通过 `kill` 指令发送 `SIGSTOP` 信号暂停进程（支持本地/远程） | - `pid`：需暂停的进程 PID（正整数，必填）<br>- `host`：远程主机名/IP（字符串，本地操作可不填，需与配置文件匹配） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（字符串）<br>- `data`：包含操作详情的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP（本地为 `localhost`）<br>&nbsp;&nbsp;- `pid`：被暂停的进程 PID |
| | `resume_process` | 通过 `kill` 指令发送 `SIGCONT` 信号恢复进程（支持本地/远程） | - `pid`：需恢复的进程 PID（正整数，必填）<br>- `host`：远程主机名/IP（字符串，本地操作可不填，需与配置文件匹配） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（字符串）<br>- `data`：包含操作详情的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP（本地为 `localhost`）<br>&nbsp;&nbsp;- `pid`：被恢复的进程 PID |
| | `check_process_status` | 检查本地或远程进程是否存在及名称信息 | - `pid`：需检查的进程 PID（正整数，必填）<br>- `host`：远程主机名/IP（字符串，本地操作可不填，需与配置文件匹配） | - `success`：查询是否成功（布尔值）<br>- `message`：查询结果描述（字符串）<br>- `data`：包含进程状态的字典<br>&nbsp;&nbsp;- `host`：查询的主机名/IP（本地为 `localhost`）<br>&nbsp;&nbsp;- `pid`：查询的进程 PID<br>&nbsp;&nbsp;- `exists`：进程是否存在（布尔值）<br>&nbsp;&nbsp;- `name`：进程名称（字符串，进程不存在时为空） |
| | `get_kill_signals` | 查看本地或远程服务器的 `kill` 信号量含义及功能说明 | - `host`：远程主机名/IP（字符串，本地查询可不填，需与配置文件匹配） | - `success`：查询是否成功（布尔值）<br>- `message`：查询结果描述（字符串）<br>- `data`：包含信号量信息的字典<br>&nbsp;&nbsp;- `host`：查询的主机名/IP（本地为 `localhost`）<br>&nbsp;&nbsp;- `signals`：信号量列表，每个元素包含：<br>&nbsp;&nbsp;&nbsp;&nbsp;- `number`：信号编号（整数）<br>&nbsp;&nbsp;&nbsp;&nbsp;- `name`：信号名称（如 `SIGTERM`）<br>&nbsp;&nbsp;&nbsp;&nbsp;- `description`：信号功能说明 |

---

#### ls_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **ls_mcp** | ls_collect_tool | 列出目录内容 | - `host`：远程主机名/IP（本地采集可不填）<br>- `file`：目标文件/目录 | 目标目录内容的列表 |

---

#### lscpu_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **lscpu_mcp** | lscpu_info_tool | 使用 `lscpu` 命令获取本地或远程主机的 CPU 架构及核心静态信息 | - `host`：远程主机名/IP（若不提供则获取本机信息） | `architecture`：CPU 架构（如 x86\_64）、`cpus_total`：CPU 总数量、`model_name`：CPU 型号名称、`cpu_max_mhz`：CPU 最大频率 (MHz)、`vulnerabilities`：常见安全漏洞的缓解状态字典 |

---

#### mkdir_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **mkdir_mcp** | mkdir_collect_tool | 进行目录创建、支持批量创建、设置权限、递归创建多级目录 | - `host`：远程主机名/IP（本地采集可不填）<br>- `dir`：创建目录名 | 布尔值，表示 mkdir 操作是否成功 |

---

#### mv_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **mv_mcp** | mv_collect_tool | 移动或重命名文件/目录 | - `host`：远程主机名/IP（本地采集可不填）<br>- `source`：源文件或目录 <br>- `target`：目标文件或目录 | 布尔值，表示 mv 操作是否成功 |

---

#### nohup_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **nohup_mcp** | run_with_nohup | 使用 `nohup` 在本地或远程服务器运行命令，支持后台执行 | - `command`：需执行的命令（字符串，必填）<br>- `host`：远程主机 IP 或 hostname（本地执行可不填）<br>- `port`：SSH 端口（默认 22，远程执行时使用）<br>- `username`：SSH 用户名（远程执行时必填）<br>- `password`：SSH 密码（远程执行时必填）<br>- `output_file`：输出日志文件路径（可选，默认自动生成）<br>- `working_dir`：命令执行的工作目录（可选） | - `success`：操作是否成功（布尔值）<br>- `message`：执行结果描述（字符串）<br>- `pid`：进程 ID（成功执行时返回）<br>- `output_file`：输出日志文件路径<br>- `command`：实际执行的命令<br>- `host`：执行命令的主机（本地为 `localhost`） |

---

#### perf_microarch_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **perf_microarch_mcp** | cache_miss_audit_tool | 通过 `perf stat -a -e cache-misses,cycles,instructions sleep 10` 采集整机的微架构指标，支持本地和远程执行 | - `host`：可选，远程主机名/IP，留空则采集本机 | `cache_misses`：缓存未命中次数<br>`cycles`：CPU 周期数<br>`instructions`：指令数<br>`ipc`：每周期指令数 (Instructions per Cycle)<br>`seconds`：采集时长（秒） |

---

#### cache_miss_audit_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **cache_miss_audit_mcp** | cache_miss_audit_tool | 通过 `perf stat -a -e cache-misses,cycles,instructions sleep 10` 采集整机的微架构指标，支持本地和远程执行 | - `host`：可选，远程主机名/IP，留空则采集本机 | `cache_miss`：缓存未命中次数<br>`cycles`：CPU 周期数<br>`instructions`：指令数<br>`ipc`：每周期指令数 (Instructions per Cycle)<br>`seconds`：采集时长（秒） |

---

#### cat_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **cat_mcp** | cat_file_view_tool | 快速查看文件内容 | - `host`：远程主机名/IP（本地采集可不填）<br>- `file`：查看的文件路径 | 文件内容字符串 |

---

#### chmod_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **chmod_mcp** | chmod_change_mode_tool | 修改文件或目录的权限 | - `host`：远程主机名/IP（本地操作可不填）<br>- `mode`：权限模式（如 755、644 等）<br>- `file`：目标文件或目录路径 | 布尔值，表示操作是否成功 |

---

#### chown_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **chown_mcp** | chown_change_owner_tool | 修改文件或目录的所有者和所属组 | - `host`：远程主机名/IP（本地操作可不填）<br>- `owner_group`：文件所有者和文件关联组 <br>- `file`：要修改的目标文件 | 布尔值，表示操作是否成功 |

---

#### disk_manager_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | top_collect_tool | 获取目标设备（本地/远程）中**内存占用排名前 k 个**的进程信息，k 支持自定义配置 | - `host`：远程主机名/IP（本地采集可不填）<br>- `k`：需获取的进程数量（默认 5） | 进程列表（含 `pid` 进程 ID、`name` 进程名称、`memory` 内存使用量（MB）） |
| | get_process_info_tool | 查询指定 PID 进程的**详细运行信息**，支持本地与远程进程信息获取 | - `host`：远程主机名/IP（本地查询可不填）<br>- `pid`：需查询的进程 ID（必传，且为正整数） | 进程详细字典（含 `status` 状态、`create_time` 创建时间、`cpu_times` CPU 时间、`memory_info` 内存信息、`open_files` 打开文件列表、`connections` 网络连接等） |
| | change_name_to_pid_tool | 根据进程名称反向查询对应的**PID 列表**，解决"已知进程名查 ID"的场景需求 | - `host`：远程主机名/IP（本地查询可不填）<br>- `name`：需查询的进程名称（必传，不能为空） | 以空格分隔的 PID 字符串（如 "1234 5678"） |
| | get_cpu_info_tool | 采集目标设备的 CPU 硬件与使用状态信息，包括核心数、频率、核心使用率 | - `host`：远程主机名/IP（本地采集可不填） | CPU 信息字典（含 `physical_cores` 物理核心数、`total_cores` 逻辑核心数、`max_frequency` 最大频率（MHz）、`cpu_usage` 各核心使用率（%）等） |
| | memory_anlyze_tool | 分析目标设备的内存使用情况，计算总内存、可用内存及使用率 | - `host`：远程主机名/IP（本地采集可不填） | 内存信息字典（含 `total` 总内存（MB）、`available` 可用内存（MB）、`used` 已用内存（MB）、`percent` 内存使用率（%）等） |
| **disk_manager_mcp** | get_disk_info_tool | 采集目标设备的磁盘分区信息与容量使用状态，过滤临时文件系统（tmpfs/devtmpfs） | - `host`：远程主机名/IP（本地采集可不填） | 磁盘列表（含 `device` 设备名、`mountpoint` 挂载点、`fstype` 文件系统类型、`total` 总容量（GB）、`percent` 磁盘使用率（%）等） |
| | get_os_info_tool | 获取目标设备的操作系统类型与版本信息，适配 openEuler | - `host`：远程主机名/IP（本地采集可不填） | 操作系统信息字符串（如 "openEuler 22.03 LTS"） |
| | get_network_info_tool | 采集目标设备的网络接口信息，包括 IP 地址、MAC 地址、接口启用状态 | - `host`：远程主机名/IP（本地采集可不填） | 网络接口列表（含 `interface` 接口名、`ip_address` IP 地址、`mac_address` MAC 地址、`is_up` 接口是否启用（布尔值）等） |
| | write_report_tool | 将系统信息分析结果写入本地报告文件，自动生成带时间戳的文件路径 | - `report`：报告内容字符串（必传，不能为空） | 报告文件路径字符串（如 "/reports/system_report_20240520_153000.txt"） |
| | telnet_test_tool | 测试目标主机指定端口的 Telnet 连通性，验证端口开放状态 | - `host`：远程主机名/IP（必传）<br>- `port`：端口号（1-65535，必传） | 连通性结果（布尔值：`True` 成功，`False` 失败） |
| | ping_test_tool | 测试目标主机的 ICMP Ping 连通性，验证主机网络可达性 | - `host`：远程主机名/IP（必传） | 连通性结果（布尔值：`True` 成功，`False` 失败） |
| | get_dns_info_tool | 采集目标设备的 DNS 配置信息，包括 DNS 服务器列表与搜索域 | - `host`：远程主机名/IP（本地采集可不填） | DNS 信息字典（含 `nameservers` DNS 服务器列表、`search` 搜索域列表） |
| | perf_data_tool | 采集目标设备的实时性能数据，支持"指定进程"或"全系统"性能监控 | - `host`：远程主机名/IP（本地采集可不填）<br>- `pid`：进程 ID（全系统监控可不填） | 性能数据字典（含 `cpu_usage` CPU 使用率（%）、`memory_usage` 内存使用率（%）、`io_counters` I/O 统计信息） |

---

#### echo_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **echo_mcp** | echo_write_to_file_tool | 使用 echo 命令将文本写入文件 | - `host`：远程主机名/IP（本地操作可不填）<br>- `text`：要写入的文本内容<br>- `file`：要写入的文件路径<br>- `options`：echo 选项（可选），如 "-n" 不输出换行符等<br>- `mode`：写入模式，"w" 表示覆盖写入，"a" 表示追加写入，默认为 "w" | 布尔值，表示写入操作是否成功 |

---

#### fallocate_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **fallocate_mcp** | fallocate_create_file_tool | 创建并启用 swap 文件（修正工具功能描述，与参数匹配） | - `host`：远程主机名/IP（本地采集可不填）<br>- `name`：swap 空间对应的设备或文件路径 <br>- `size`：创建的磁盘空间大小 | 布尔值，表示创建启用 swap 文件是否成功 |

---

#### file_content_tool_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | file_grep_tool | 通过 `grep` 命令搜索文件中匹配指定模式的内容（支持正则、大小写忽略等） | - `file_path`：目标文件路径（绝对路径，必填）<br>- `pattern`：搜索模式（支持正则，如 "error"，必填）<br>- `options`：`grep` 可选参数（如 "-n" 显示行号、"-i" 忽略大小写，可选）<br>- `host`：远程主机名/IP（默认 `localhost`，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用）<br>- `username`：SSH 用户名（默认 `root`，远程操作时需指定）<br>- `password`：SSH 密码（远程操作时必填） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "本地文件搜索完成"）<br>- `data`：包含操作详情的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `file_path`：目标文件路径<br>&nbsp;&nbsp;- `result`：匹配结果列表（每行一个匹配项） |
| | file_sed_tool | 通过 `sed` 命令替换文件中匹配的内容（支持全局替换、原文件修改） | - `file_path`：目标文件路径（绝对路径，必填）<br>- `pattern`：替换模式（如 "s/old/new/g"，`g` 表示全局替换，必填）<br>- `in_place`：是否直接修改原文件（布尔值，默认 `False`，仅输出结果）<br>- `options`：`sed` 可选参数（如 "-i.bak" 备份原文件，可选）<br>- `host`/`port`/`username`/`password`：同 `file_grep_tool` | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "远程 sed 执行成功"）<br>- `data`：包含操作详情的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `file_path`：目标文件路径<br>&nbsp;&nbsp;- `result`：替换后内容（`in_place=False` 时返回） |
| **file_content_tool_mcp** | file_awk_tool | 通过 `awk` 命令对文本文件进行高级处理（支持列提取、条件过滤） | - `file_path`：目标文件路径（绝对路径，必填）<br>- `script`：`awk` 处理脚本（如 "'{print $1,$3}'" 提取 1、3 列，必填）<br>- `options`：`awk` 可选参数（如 "-F:" 指定分隔符为冒号，可选）<br>- `host`/`port`/`username`/`password`：同 `file_grep_tool` | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "本地 awk 处理成功"）<br>- `data`：包含操作详情的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `file_path`：目标文件路径<br>&nbsp;&nbsp;- `result`：处理结果列表（每行一个结果项） |
| | file_sort_tool | 通过 `sort` 命令对文本文件进行排序（支持按列、升序/降序） | - `file_path`：目标文件路径（绝对路径，必填）<br>- `options`：`sort` 可选参数（如 "-n" 按数字排序、"-k2" 按第 2 列排序、"-r" 降序，可选）<br>- `output_file`：排序结果输出路径（可选，默认不保存到文件）<br>- `host`/`port`/`username`/`password`：同 `file_grep_tool` | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "远程排序完成"）<br>- `data`：包含操作详情的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `file_path`/`output_file`：目标文件/输出文件路径<br>&nbsp;&nbsp;- `result`：排序结果列表（`output_file` 为空时返回） |
| | file_unique_tool | 通过 `unique` 命令对文本文件进行去重（支持统计重复次数） | - `file_path`：目标文件路径（绝对路径，必填）<br>- `options`：`unique` 可选参数（如 "-u" 仅显示唯一行、"-c" 统计重复次数，可选）<br>- `output_file`：去重结果输出路径（可选，默认不保存到文件）<br>- `host`/`port`/`username`/`password`：同 `file_grep_tool` | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "本地去重完成"）<br>- `data`：包含操作详情的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `file_path`/`output_file`：目标文件/输出文件路径<br>&nbsp;&nbsp;- `result`：去重结果列表（`output_file` 为空时返回） |
| | file_echo_tool | 通过 `echo` 命令向文件写入内容（支持覆盖/追加模式） | - `content`：要写入的内容（如 "Hello World"，必填）<br>- `file_path`：目标文件路径（绝对路径，必填）<br>- `append`：是否追加内容（布尔值，默认 `False`，覆盖原文件）<br>- `host`/`port`/`username`/`password`：同 `file_grep_tool` | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "本地写入成功"）<br>- `data`：包含操作详情的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `file_path`：目标文件路径<br>&nbsp;&nbsp;- `action`：操作类型（"overwrite" 覆盖/"append" 追加） |

---

#### find_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | find_with_name_tool | 基于名称在指定目录下查找文件 | - `host`：远程主机名/IP（本地采集可不填）<br>- `path`：指定查找的目录 <br>- `name`：要找的文件名 | 查找到的文件列表（含 `file` 符合查找要求的具体文件路径） |
| **find_mcp** | find_with_date_tool | 基于修改时间在指定目录下查找文件 | - `host`：远程主机名/IP（本地采集可不填）<br>- `path`：指定查找的目录 <br>- `date_condition`：修改时间条件（如 "-mtime -1" 表示 1 天内修改，补充参数使功能匹配） | 查找到的文件列表（含 `file` 符合查找要求的具体文件路径） |
| | find_with_size_tool | 基于文件大小在指定目录下查找文件 | - `host`：远程主机名/IP（本地采集可不填）<br>- `path`：指定查找的目录 <br>- `size_condition`：文件大小条件（如 "+10M" 表示大于 10MB，补充参数使功能匹配） | 查找到的文件列表（含 `file` 符合查找要求的具体文件路径） |

---

#### flame_graph_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **flame_graph_mcp** | flame_graph | 基于 `perf.data` 生成 CPU 火焰图，用于性能分析（支持本地/远程） | - `host`：远程主机地址（可选）<br>- `perf_data_path`：perf.data 输入路径（必选）<br>- `output_path`：SVG 输出路径（默认：\~/cpu\_flamegraph.svg）<br>- `flamegraph_path`：FlameGraph 脚本路径（必选） | - `svg_path`：生成的火焰图文件路径<br>- `status`：生成状态（success / failure）<br>- `message`：状态信息 |

---

#### free_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **free_mcp** | free_collect_tool | 获取目标设备（本地/远程）中内存整体状态信息 | - `host`：远程主机名/IP（本地采集可不填） | 内存信息列表（含 `total` 系统内存总量（MB）、`used` 系统已使用内存量(MB)、`free` 空闲物理内存（MB）、`available` 系统可分配内存（MB）） |

---

#### func_timing_trace_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **func_timing_trace_mcp** | func_timing_trace_tool | 使用 `perf record -g` 采集目标进程的函数调用栈耗时，并解析热点函数 | - `pid`：目标进程 PID<br>- `host`：可选，远程主机 IP/域名；留空则采集本机 | `top_functions`：函数耗时分析结果，包含列表，每项包括：<br>• `function`：函数名<br>• `self_percent`：函数自身耗时占比<br>• `total_percent`：函数总耗时占比<br>• `call_stack`：函数调用栈 |

---

#### grep_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **grep_mcp** | grep_search_tool | 在文件中搜索指定模式的内容 | - `host`：远程主机名/IP（本地搜索可不填）<br>- `options`：grep 选项（可选），如 "-i" 忽略大小写，"-n" 显示行号等<br>- `pattern`：要搜索的模式（支持正则表达式）<br>- `file`：要搜索的文件路径 | 包含匹配行的字符串，如果没有找到匹配项则返回相应的提示信息 |

---

#### head_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **head_mcp** | head_file_view_tool | 快速查看文件开头部分内容 | - `host`：远程主机名/IP（本地采集可不填）<br>- `num`：查看文件开头行数，默认为 10 行 <br>- `file`：查看的文件路径 | 文件内容字符串 |

---

#### systrace_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | slow_node_perception_tool | 检测指定 task_id 的机器性能是否发生劣化的工具 | - task_id：目标机器 ip | 文件内容字符串 |
| **systrace_mcp** | slow_node_detection_tool | 这是针对 slow_node_perception_tool 工具返回 is_anomaly=True 时调用的慢卡定界工具 | - performance_data: 感知工具返回的完整性能数据 PerceptionResult |  |
| | generate_report_tool | 报告工具：生成最终 Markdown 格式报告 | - source_data 感知或定界的结果<br>- report_type 是否劣化 normal anomaly |  |

---

#### hotspot_trace_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **hotspot_trace_mcp** | hotspot_trace_tool | 使用 `perf record` 和 `perf report` 分析系统或指定进程的 CPU 性能瓶颈 | - `host`：远程主机名/IP（可选，不填则分析本机）<br>- `pid`：目标进程 ID（可选，不填则分析整机） | - `total_samples`：总样本数<br>- `event_count`：事件计数（如 cycles）<br>- `hot_functions`：热点函数列表（按 Children 百分比排序，包含函数名、库、符号类型和占比） |

---

#### docker_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | manage_container_tool | 本地/远程主机容器全生命周期管理（含创建、启动、停止、删除、重启，支持端口映射与数据卷配置） | - `name`：容器名称（必填，唯一标识容器）<br>- `image`：镜像名称（创建时必填，格式如 "nginx:latest"）<br>- `action`：操作类型（create/start/stop/delete/restart，必填）<br>- `ports`：端口映射（可选，格式 "8080:80,443:443"）<br>- `volumes`：数据卷挂载（可选，格式 "/host/path:/container/path:ro"）<br>- `restart_policy`：重启策略（no/always/on-failure/unless-stopped，默认 "no"）<br>- `host`：远程主机名/IP（可选，默认 "localhost"）<br>- `ssh_port`：SSH 端口（可选，默认 22，远程操作时使用） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "容器 my-nginx start 成功"）<br>- `data`：容器操作信息字典<br>  - `host`：操作的主机名/IP<br>  - `container_name`：容器名称<br>  - `action`：执行的操作类型<br>  - `details`：操作详情（含容器 ID、配置参数） |
| | manage_image_tool | 本地/远程主机镜像管理（含拉取、删除、标签、推送，支持私有仓库认证） | - `image`：镜像名称（必填，格式如 "nginx:latest" "registry.com/app:v1"）<br>- `action`：操作类型（pull/delete/tag/push/inspect，必填）<br>- `new_tag`：新标签（tag 操作必填，格式如 "my-app:v1"）<br>- `registry_auth`：仓库认证（可选，格式 "username:password"，私有仓库使用）<br>- `host`：远程主机名/IP（可选，默认 "localhost"）<br>- `ssh_port`：SSH 端口（可选，默认 22，远程操作时使用） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "镜像 nginx:latest pull 成功"）<br>- `data`：镜像信息字典<br>  - `host`：操作的主机名/IP<br>  - `image`：镜像名称<br>  - `action`：执行的操作类型<br>  - `inspect`：镜像详情（inspect 操作返回，含架构、配置等） |
| **docker_mcp** | container_data_operate_tool | 本地/远程主机容器数据交互（含容器导出、导入，及容器与本地文件拷贝） | - `name`：容器名称（必填，import 时为镜像前缀）<br>- `action`：操作类型（export/import/cp，必填）<br>- `file_path`：文件路径（必填，cp 时格式 "src:dst"）<br>- `host`：远程主机名/IP（可选，默认 "localhost"）<br>- `ssh_port`：SSH 端口（可选，默认 22，远程操作时使用） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "容器 my-nginx export 成功"）<br>- `data`：数据操作信息字典<br>  - `host`：操作的主机名/IP<br>  - `container_name`：容器名称<br>  - `action`：执行的操作类型<br>  - `file_path`：操作的文件路径 |
| | container_logs_tool | 本地/远程主机容器日志查询（支持实时跟踪、按时间/行数筛选） | - `name`：容器名称（必填）<br>- `tail`：日志行数（可选，默认 100，0 表示全部）<br>- `follow`：实时跟踪（可选，True/False，默认 False）<br>- `since`：时间筛选（可选，格式 "10m" "2024-01-01T00:00:00"）<br>- `host`：远程主机名/IP（可选，默认 "localhost"）<br>- `ssh_port`：SSH 端口（可选，默认 22，远程操作时使用） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取 my-nginx 日志"）<br>- `data`：日志信息字典<br>  - `host`：操作的主机名/IP<br>  - `container_name`：容器名称<br>  - `logs`：日志内容（字符串格式）<br>  - `filter`：筛选条件（tail/since） |
| | list_containers_tool | 本地/远程主机容器列表查询（支持按运行状态、名称/镜像筛选） | - `all`：显示所有容器（可选，True/False，默认 False 仅显示运行中）<br>- `filter`：筛选条件（可选，格式 "name=nginx,image=nginx:latest"）<br>- `host`：远程主机名/IP（可选，默认 "localhost"）<br>- `ssh_port`：SSH 端口（可选，默认 22，远程操作时使用） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取本地运行中容器，共 5 个"）<br>- `data`：容器列表信息字典<br>  - `host`：操作的主机名/IP<br>  - `container_count`：容器总数<br>  - `containers`：容器列表（含 ID、名称、镜像、状态等）<br>  - `filter`：筛选条件（all/name/image） |

---

#### file_transfer_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | http_download_tool | 通过 `curl` 或 `wget` 工具下载 HTTP/HTTPS/FTP 资源至本地，支持自动选择可用下载工具 | - `url`：下载资源链接（字符串，必填）<br>- `output_path`：本地保存路径（字符串，必填，格式如 "/tmp/file.zip"）<br>- `tool`：下载工具（字符串，可选，值为 "curl"/"wget"，默认自动选择可用工具） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（字符串，如 "文件已通过 curl 下载至 /tmp/file.zip"）<br>- `data`：操作详情字典<br>  - `url`：实际下载链接<br>  - `output_path`：本地保存路径<br>  - `file_size`：下载文件大小（整数，单位：字节）<br>  - `transfer_time`：传输耗时（浮点数，单位：秒） |
| **file_transfer_mcp** | scp_transfer_tool | 通过 `scp` 协议实现本地与远程主机间文件/目录传输，支持递归传输目录 | - `src`：源路径（字符串，必填，本地路径如 "/data/docs"，远程路径如 "192.168.1.100:/remote/docs"）<br>- `dst`：目标路径（字符串，必填，格式同 `src`）<br>- `host`：远程主机名/IP（字符串，必填，需与配置文件中主机信息匹配）<br>- `recursive`：是否递归传输目录（布尔值，可选，默认 "false"，传输目录需设为 "true"） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（字符串，如 "SCP 传输成功：/data/docs -> 192.168.1.100:/remote/docs"）<br>- `data`：操作详情字典<br>  - `src`：源路径<br>  - `dst`：目标路径<br>  - `file_count`：传输的文件总数（整数）<br>  - `transfer_time`：传输耗时（浮点数，单位：秒） |
| | sftp_transfer_tool | 通过 `SFTP` 协议实现本地与远程主机间高级文件传输，支持自动创建目标目录 | - `operation`：操作类型（字符串，必填，值为 "put"/"get"，"put"=本地到远程，"get"=远程到本地）<br>- `src`：源路径（字符串，必填，与 `operation` 匹配，如 "put" 时为本地路径）<br>- `dst`：目标路径（字符串，必填，与 `operation` 匹配，如 "put" 时为远程路径）<br>- `host`：远程主机名/IP（字符串，必填，需与配置文件中主机信息匹配）<br>- `create_dir`：是否自动创建目标目录（布尔值，可选，默认 "true"） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（字符串，如 "SFTP put 成功：/data/file.zip -> 192.168.1.100:/remote/file.zip"）<br>- `data`：操作详情字典<br>  - `operation`：操作类型（"put"/"get"）<br>  - `src`：源路径<br>  - `dst`：目标路径<br>  - `file_size`：传输文件总大小（整数，单位：字节）<br>  - `transfer_time`：传输耗时（浮点数，单位：秒） |

---

#### numa_bind_docker_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **numa_bind_docker_mcp** | numa_bind_docker_tool | 使用 `numactl` 将指定 NUMA 绑定参数插入到镜像原有的 ENTRYPOINT / CMD 前，运行 Docker 容器（本地/远程） | - `image`：镜像名称<br>- `cpuset_cpus`：允许使用的 CPU 核心范围<br>- `cpuset_mems`：允许使用的内存节点<br>- `detach`：是否后台运行容器（默认 False）<br>- `host`：远程主机名/IP（可选） | - `status`：操作状态（success / error）<br>- `message`：操作结果信息<br>- `output`：命令的原始输出（如有） |

---

#### numa_bind_proc_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **numa_bind_proc_mcp** | numa_bind_proc_tool | 使用 `numactl` 命令在指定的 NUMA 节点和内存节点上运行程序（支持本地/远程执行） | - `host`：远程主机名/IP（本地可不填）<br>- `numa_node`：NUMA 节点编号（整数）<br>- `memory_node`：内存节点编号（整数）<br>- `program_path`：程序路径（必填） | `stdout`：程序标准输出、`stderr`：程序标准错误、`exit_code`：程序退出码 |

---

#### numa_container_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **numa_container_mcp** | numa_container | 监控指定 Docker 容器的 NUMA 内存访问情况（支持本地/远程执行） | - `container_id`：要监控的容器 ID 或名称<br>- `host`：远程主机地址（可选，若为空则在本地执行） | - `status`：操作状态（success / error）<br>- `message`：操作结果信息<br>- `output`：NUMA 内存访问统计信息（包含每个 NUMA 节点的内存使用情况） |

---

#### numa_cross_node_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **numa_cross_node_mcp** | numa_cross_node | 自动检测 NUMA 跨节点访问异常的进程（支持本地与远程主机） | - `host`：远程主机 IP/域名（可选，留空则检测本机）<br>- `threshold`：跨节点内存比例阈值（默认 30%） | `overall_conclusion`：整体结论（是否存在问题、严重程度、摘要），`anomaly_processes`：异常进程列表（包含 `pid`、`local_memory`、`remote_memory`、`cross_ratio`、`name`、`command`） |

---

#### numa_diagnose_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **numa_diagnose_mcp** | numa_diagnose | 获取 NUMA 架构硬件监控信息，包括 CPU 实时频率、规格参数以及 NUMA 拓扑结构 | - `host`：远程主机地址（可选，不填则在本地执行） | - `real_time_frequencies`：各 CPU 核心实时频率 (MHz)<br>- `specifications`：CPU 规格信息（型号 / 频率范围 / NUMA 节点）<br>- `numa_topology`：NUMA 拓扑结构 |

---

#### numa_perf_compare_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **numa_perf_compare_mcp** | numa_perf_compare | 执行 NUMA 基准测试，支持本地绑定、跨节点绑定和不绑定三种策略 | - `benchmark`：基准测试可执行文件路径（如 `/root/mcp_center/stream`）<br>- `host`：远程主机名称或 IP 地址（可选） | `numa_nodes`：系统 NUMA 节点数量<br>`test_results`：包含三种绑定策略的测试结果<br>`timestamp`：执行时间<br>`error`：错误信息（如有） |

---

#### numa_rebind_proc_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **numa_rebind_proc_mcp** | numa_rebind_proc_tool | 修改已运行进程的 NUMA 内存绑定，使用 migratepages 工具将进程的内存从一个 NUMA 节点迁移到另一个节点 | - `pid`：进程 ID<br>- `from_node`：当前内存所在的 NUMA 节点编号<br>- `to_node`：目标 NUMA 节点编号<br>- `host`：远程主机 IP 或名称（可选） | `status`：操作状态（success / error）<br>`message`：操作结果信息<br>`output`：命令的原始输出（如有） |

---

#### numa_topo_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **numa_topo_mcp** | numa_topo_tool | 使用 numactl 获取本地或远程主机的 NUMA 拓扑信息 | - `host`：远程主机名称或 IP（可选，不填表示获取本机信息） | - `nodes_total`：总节点数<br>- `nodes`：节点信息列表，每个节点包含：`node_id`（节点 ID）、`cpus`（CPU 列表）、`size_mb`（内存大小 MB）、`free_mb`（空闲内存 MB） |

---

#### numastat_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **numastat_mcp** | numastat_info_tool | 使用 `numastat` 命令获取本地或远程主机的 NUMA 统计信息 | - `host`：远程主机名称或 IP，若不提供则获取本机信息 | `numa_hit`: NUMA 命中次数、`numa_miss`: NUMA 未命中次数、`numa_foreign`: 外部访问次数、`interleave_hit`: 交错命中次数、`local_node`: 本地节点访问次数、`other_node`: 其他节点访问次数 |

---

#### nvidia_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | nvidia_smi_status | 输出结构化 GPU 状态数据（JSON 友好） | - `host`：远程主机 IP/hostname（本地可不填）<br>- `port`：SSH 端口（默认 22）<br>- `username`/`password`：远程查询必填<br>- `gpu_index`：指定 GPU 索引（可选）<br>- `include_processes`：是否包含进程信息（默认 False） | - `success`：查询成功与否<br>- `message`：结果描述<br>- `data`：结构化数据，包含：<br>&nbsp;&nbsp;- `host`：主机地址<br>&nbsp;&nbsp;- `gpus`：GPU 列表（含索引、型号、利用率、显存等） |
| **nvidia_mcp** | nvidia_smi_raw_table | 输出 `nvidia-smi` 原生表格（保留原始格式） | - `host`：远程主机 IP/hostname（本地可不填）<br>- `port`：SSH 端口（默认 22）<br>- `username`/`password`：远程查询必填 | - `success`：查询成功与否<br>- `message`：结果描述<br>- `data`：原始表格数据，包含：<br>&nbsp;&nbsp;- `host`：主机地址<br>&nbsp;&nbsp;- `raw_table`：`nvidia-smi` 原生表格字符串（含换行和格式） |

---

#### perf_interrupt_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **perf_interrupt_mcp** | perf_interrupt_health_check | 检查系统中断统计信息，以定位高频中断导致的 CPU 占用 | - `host`：远程主机名称或 IP 地址，若不提供则获取本机信息 | 返回一个包含中断信息的列表，每个元素包含：`irq_number` 中断编号、`total_count` 总触发次数、`device` 设备名称、`cpu_distribution` 各 CPU 核心的中断分布、`interrupt_type` 中断类型 |

---

#### rm_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **rm_mcp** | rm_collect_tool | 对文件或文件夹进行删除 | - `host`：远程主机名/IP（本地采集可不填）<br>- `path`：要进行删除的文件或文件夹路径 | 布尔值，表示 rm 操作是否成功 |

---

#### sar_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | sar_cpu_collect_tool | 分析 CPU 使用的周期性规律 | - `host`：远程主机名/IP（本地采集可不填）<br>- `interval`：监控的时间间隔<br>- `count`：监控次数 | 采集指标列表：含 `timestamp` 采集时间点、`user` 用户空间程序占用 CPU 的百分比、`nice` 低优先级用户进程占用的 CPU 百分比、`system` 内核空间程序占用 CPU 的百分比、`iowait` CPU 等待磁盘 I/O 操作的时间百分比、`steal` 虚拟化环境中其他虚拟机占用的 CPU 时间百分比、`idle` CPU 空闲时间百分比 |
| | sar_memory_collect_tool | 分析内存资源使用的周期性规律 | - `host`：远程主机名/IP（本地采集可不填）<br>- `interval`：监控的时间间隔<br>- `count`：监控次数 | 采集指标列表：含 `timestamp` 采集时间点、`kbmemfree` 物理空闲内存量、`kbavail` 实际可用内存、`kbmemused` 已使用的物理内存、`memused` 已用内存占总物理内存的百分比、`kbbuffers` 内核缓冲区（Buffer）占用的内存、`kbcached` 内核缓存（Cache）占用的内存、`kbcommit` 当前工作负载所需的总内存量、`commit` kbcommit 占系统总可用内存百分比、`kbactive` 活跃内存、`kbinact` 非活跃内存、`kbdirty` 等待写入磁盘的脏数据量 |
| | sar_disk_collect_tool | 分析磁盘 IO 使用的周期性规律 | - `host`：远程主机名/IP（本地采集可不填）<br>- `interval`：监控的时间间隔<br>- `count`：监控次数 | 采集指标列表：含 `timestamp` 采集时间点、`name` 磁盘设备名称、`tps` 每秒传输次数、`rkB_s` 每秒读取的数据量、`wkB_s` 每秒写入的数据量、`dkB_s` 每秒丢弃的数据量、`areq-sz` 平均每次 I/O 请求的数据大小、`aqu-sz` 平均 I/O 请求队列长度、`await` 平均每次 I/O 请求的等待时间、`util` 设备带宽利用率 |
| **sar_mcp** | sar_network_collect_tool | 分析网络流量的周期性规律 | - `host`：远程主机名/IP（本地采集可不填）<br>- `interval`：监控的时间间隔<br>- `count`：监控次数 | 采集指标列表：含 `timestamp` 采集时间点、`iface` 网络接口名称、`rxpck_s` 每秒接收的数据包数量、`txpck_s` 每秒发送的数据包数量、`rxkB_s` 每秒接收的数据量、`txkB_s` 每秒发送的数据量、`rxcmp_s` 每秒接收的压缩数据包数、`txcmp_s` 每秒发送的压缩数据包数、`rxmcst_s` 每秒接收的多播数据包数、`ifutil` 网络接口带宽利用率 |
| | sar_cpu_historicalinfo_collect_tool | 进行历史状态分析，排查过去某时段 cpu 的性能问题 | - `host`：远程主机名/IP（本地查询可不填）<br>- `file`：sar 要分析的 log 文件<br>- `starttime`：分析开始的时间点<br>- `endtime`：分析结束的时间点 | 采集指标列表：含 `timestamp` 采集时间点、`user` 用户空间程序占用 CPU 的百分比、`nice` 低优先级用户进程占用的 CPU 百分比、`system` 内核空间程序占用 CPU 的百分比、`iowait` CPU 等待磁盘 I/O 操作的时间百分比、`steal` 虚拟化环境中其他虚拟机占用的 CPU 时间百分比、`idle` CPU 空闲时间百分比 |
| | sar_memory_historicalinfo_collect_tool | 进行历史状态分析，排查过去某时段内存的性能问题 | - `host`：远程主机名/IP（本地查询可不填）<br>- `file`：sar 要分析的 log 文件<br>- `starttime`：分析开始的时间点<br>- `endtime`：分析结束的时间点 | 采集指标列表：含 `timestamp` 采集时间点、`kbmemfree` 物理空闲内存量、`kbavail` 实际可用内存、`kbmemused` 已使用的物理内存、`memused` 已用内存占总物理内存的百分比、`kbbuffers` 内核缓冲区（Buffer）占用的内存、`kbcached` 内核缓存（Cache）占用的内存、`kbcommit` 当前工作负载所需的总内存量、`commit` kbcommit 占系统总可用内存百分比、`kbactive` 活跃内存、`kbinact` 非活跃内存、`kbdirty` 等待写入磁盘的脏数据量 |
| | sar_disk_historicalinfo_collect_tool | 进行历史状态分析，排查过去某时段磁盘 IO 的性能问题 | - `host`：远程主机名/IP（本地查询可不填）<br>- `file`：sar 要分析的 log 文件<br>- `starttime`：分析开始的时间点<br>- `endtime`：分析结束的时间点 | 采集指标列表：含 `timestamp` 采集时间点、`name` 磁盘设备名称、`tps` 每秒传输次数、`rkB_s` 每秒读取的数据量、`wkB_s` 每秒写入的数据量、`dkB_s` 每秒丢弃的数据量、`areq-sz` 平均每次 I/O 请求的数据大小、`aqu-sz` 平均 I/O 请求队列长度、`await` 平均每次 I/O 请求的等待时间、`util` 设备带宽利用率 |
| | sar_network_historicalinfo_collect_tool | 进行历史状态分析，排查过去某时段网络的性能问题 | - `host`：远程主机名/IP（本地查询可不填）<br>- `file`：sar 要分析的 log 文件<br>- `starttime`：分析开始的时间点<br>- `endtime`：分析结束的时间点 | 采集指标列表：含 `timestamp` 采集时间点、`iface` 网络接口名称、`rxpck_s` 每秒接收的数据包数量、`txpck_s` 每秒发送的数据包数量、`rxkB_s` 每秒接收的数据量、`txkB_s` 每秒发送的数据量、`rxcmp_s` 每秒接收的压缩数据包数、`txcmp_s` 每秒发送的压缩数据包数、`rxmcst_s` 每秒接收的多播数据包数、`ifutil` 网络接口带宽利用率 |

---

#### sed_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **sed_mcp** | sed_text_replace_tool | 在文件中替换指定模式的文本 | - `host`：远程主机名/IP（本地操作可不填）<br>- `options`：sed 选项（可选），如 "-i" 直接修改文件<br>- `pattern`：要替换的模式（支持正则表达式）<br>- `replacement`：替换后的文本<br>- `file`：要操作的文件路径 | 布尔值，表示操作是否成功 |
| | sed_text_delete_tool | 删除文件中匹配模式的行 | - `host`：远程主机名/IP（本地操作可不填）<br>- `options`：sed 选项（可选），如 "-i" 直接修改文件<br>- `pattern`：要删除的行的模式（支持正则表达式）<br>- `file`：要操作的文件路径 | 布尔值，表示操作是否成功 |

---

#### strace_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | strace_track_file_process | 跟踪进程的文件操作和运行状态（如打开、读取、写入文件等） | - `pid`：目标进程 PID（必填）<br>- `host`：远程主机 IP/hostname（本地跟踪可不填）<br>- `port`：SSH 端口（默认 22）<br>- `username`/`password`：远程跟踪时必填<br>- `output_file`：日志路径（可选）<br>- `follow_children`：是否跟踪子进程（默认 False）<br>- `duration`：跟踪时长（秒，可选） | - `success`：跟踪启动状态<br>- `message`：结果描述<br>- `strace_pid`：跟踪进程 ID<br>- `output_file`：日志路径<br>- `target_pid`/`host`：目标进程及主机信息 |
| **strace_mcp** | strace_check_permission_file | 排查进程的"权限不足"和"文件找不到"错误 | - `pid`：目标进程 PID（必填）<br>- 远程参数（`host`/`port`/`username`/`password`）<br>- `output_file`：日志路径（可选）<br>- `duration`：跟踪时长（默认 30 秒） | - 基础状态信息（`success`/`message` 等）<br>- `errors`：错误统计字典，包含：<br>&nbsp;&nbsp;- 权限不足错误详情<br>&nbsp;&nbsp;- 文件找不到错误详情 |
| | strace_check_network | 诊断进程网络问题（连接失败、超时、DNS 解析等） | - `pid`：目标进程 PID（必填）<br>- 远程参数（同上）<br>- `output_file`：日志路径（可选）<br>- `duration`：跟踪时长（默认 30 秒）<br>- `trace_dns`：是否跟踪 DNS 调用（默认 True） | - 基础状态信息<br>- `errors`：网络错误统计，包含：<br>&nbsp;&nbsp;- 连接被拒绝、超时等错误<br>&nbsp;&nbsp;- DNS 解析失败详情（若启用） |
| | strace_locate_freeze | 定位进程卡顿原因（IO 阻塞、锁等待等慢操作） | - `pid`：目标进程 PID（必填）<br>- 远程参数（同上）<br>- `output_file`：日志路径（可选）<br>- `duration`：跟踪时长（默认 30 秒）<br>- `slow_threshold`：慢操作阈值（默认 0.5 秒） | - 基础状态信息<br>- `analysis`：卡顿分析字典，包含：<br>&nbsp;&nbsp;- 慢操作调用详情<br>&nbsp;&nbsp;- 阻塞类型分类统计<br>&nbsp;&nbsp;- 耗时最长的系统调用 |

---

#### strace_syscall_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **strace_syscall_mcp** | strace_syscall | 采集指定进程的系统调用统计信息 | - `host`：可选，远程主机地址<br>- `pid`：目标进程 ID（必填）<br>- `timeout`：采集超时时间，默认 10 秒 | List\[Dict]，每个字典包含：<br>- `syscall`：系统调用名称<br>- `total_time`：总耗时（秒）<br>- `call_count`：调用次数<br>- `avg_time`：平均耗时（微秒）<br>- `error_count`：错误次数 |

---

#### swapoff_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **swapoff_mcp** | swapoff_disabling_swap_tool | 停用交换空间（Swap），释放已启用的交换分区或交换文件，将其从系统内存管理中移除 | - `host`：远程主机名/IP（本地采集可不填）<br>- `name`：停用的 swap 空间路径 | 布尔值，表示停用指定 swap 空间是否成功 |

---

#### swapon_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **swapon_mcp** | swapon_collect_tool | 获取目标设备（本地/远程）中当前 swap 设备状态 | - `host`：远程主机名/IP（本地采集可不填） | swap 设备列表（含 `name` swap 空间对应的设备或文件路径、`type` swap 空间的类型、`size` swap 空间的总大小、`used` 当前已使用的 swap 空间量、`prio` swap 空间的优先级） |

---

#### tail_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **tail_mcp** | tail_file_view_tool | 快速查看文件末尾部分内容 | - `host`：远程主机名/IP（本地采集可不填）<br>- `num`：查看文件末尾行数，默认为 10 行 <br>- `file`：查看的文件路径 | 文件内容字符串 |

---

#### tar_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **tar_mcp** | tar_extract_file_tool | 使用 tar 命令解压文件或目录 | - `host`：远程主机名称或 IP 地址，若不提供则表示对本机文件进行修改<br>- `options`：tar 命令选项（如 `-xzvf` 等）<br>- `file`：压缩包文件路径<br>- `extract_path`：指定解压目录 | 布尔值，表示解压操作是否成功 |
| | tar_compress_file_tool | 使用 tar 命令压缩文件或目录 | - `host`：远程主机名称或 IP 地址，若不提供则表示对本机文件进行压缩<br>- `options`：tar 命令选项（如 `-czvf`、`-xzvf` 等）<br>- `source_path`：需要压缩的文件或目录路径<br>- `archive_path`：压缩包输出路径 | 布尔值，表示压缩操作是否成功 |

---

#### touch_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **touch_mcp** | touch_create_files_tool | 进行文件快速初始化、批量创建 | - `host`：远程主机名/IP（本地采集可不填）<br>- `file`：创建的文件名 | 布尔值，表示 touch 操作是否成功 |
| | touch_timestamp_files_tool | 进行文件时间戳校准与模拟 | - `host`：远程主机名/IP（本地查询可不填）<br>- `options`：更新访问时间\更新修改时间（`-a` 表示仅更新访问时间、`-m` 表示仅更新修改时间）<br>- `file`：文件名 | 布尔值，表示 touch 操作是否成功 |

---

#### vmstat_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **vmstat_mcp** | vmstat_collect_tool | 获取目标设备资源整体状态 | - `host`：远程主机名/IP（本地采集可不填） | 系统资源状态字典（含 `r` 运行队列进程数、`b` 等待 I/O 的进程数、`si` 每秒从磁盘加载到内存的数据量（KB/s）、`so` 每秒从内存换出到磁盘的数据量（KB/s）、`bi` 从磁盘读取的块数、`bo` 写入磁盘的块数、`in` 每秒发生的中断次数（含时钟中断）、`cs` 每秒上下文切换次数、`us` 用户进程消耗 CPU 时间、`sy` 内核进程消耗 CPU 时间、`id` CPU 空闲时间、`wa` CPU 等待 I/O 完成的时间百分比、`st` 被虚拟机偷走的 CPU 时间百分比） |
| | vmstat_slabinfo_collect_tool | 获取内核 slab 内存缓存（slabinfo）的统计信息 | - `host`：远程主机名/IP（本地查询可不填） | slab 内存缓存信息详细字典（含 `cache` 内核中 slab 缓存名称、`num` 当前活跃的缓存对象数量、`total` 该缓存的总对象数量、`size` 每个缓存对象的大小、`pages` 每个 slab 中包含的缓存对象数量） |

---

#### zip_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **zip_mcp** | zip_extract_file_tool | 使用 unzip 命令解压 zip 文件 | - `host`：远程主机名称或 IP 地址，若不提供则表示对本机文件进行修改<br>- `file`：压缩包文件路径<br>- `extract_path`：指定解压目录 | 布尔值，表示解压操作是否成功 |
| | tar_compress_file_tool | 使用 zip 命令压缩文件或目录 | - `host`：远程主机名称或 IP 地址，若不提供则表示对本机文件进行压缩<br>- `source_path`：需要压缩的文件或目录路径<br>- `archive_path`：压缩包输出路径 | 布尔值，表示压缩操作是否成功 |

---

#### euler-copilot-tune_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **tune_mcp** | Collector | 采集机器的性能指标 |  | 采集的性能数据 |
| | Analyzer | 分析采集到的数据 |  | 分析报告 |
| | Optimizer | 参数+策略 |  | 推荐的服务参数 |
| | StartTune | 开始调优 |  | 调优完成 |

---

#### iftop_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | get_interface_traffic | 通过 `iftop` 获取指定网卡的实时流量数据（含总流量和 Top 连接） | - `iface`：网络网卡名称（如 eth0，必填）<br>- `sample_seconds`：采样时长（秒，默认 5 秒，3-30 范围）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用）<br>- `username`：SSH 用户名（默认 root，远程操作时需指定）<br>- `password`：SSH 密码（远程操作时必填） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取网卡流量数据"）<br>- `data`：包含流量信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `total_stats`：总流量统计（含 `interface` 网卡名称、`tx_total`/`rx_total` 总发送/接收流量（MB）、`tx_rate_avg`/`rx_rate_avg` 平均发送/接收速率（Mbps））<br>&nbsp;&nbsp;- `top_connections`：Top 10 连接列表（按接收速率排序） |
| **iftop_mcp** | list_network_interfaces | 获取本地或远程主机的所有网络网卡名称（用于选择监控目标） | - `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用）<br>- `username`：SSH 用户名（默认 root，远程操作时需指定）<br>- `password`：SSH 密码（远程操作时必填） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取 3 个网卡名称"）<br>- `data`：包含网卡列表的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `interfaces`：网卡名称列表（如 ["eth0", "lo"]） |

---

#### nload_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | monitor_bandwidth | 通过 `nload` 获取指定网卡的实时带宽数据（含入站/出站流量详情） | - `iface`：网络网卡名称（如 eth0，必填）<br>- `duration`：监控时长（秒，默认 10 秒，5-60 范围）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取网卡带宽数据"）<br>- `data`：包含带宽信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `monitor_duration`：实际监控时长（秒）<br>&nbsp;&nbsp;- `bandwidth`：带宽监控数据<br>&nbsp;&nbsp;&nbsp;&nbsp;- `interface`：网卡名称<br>&nbsp;&nbsp;&nbsp;&nbsp;- `incoming`：入站流量（含 current/average/maximum/total/unit 字段）<br>&nbsp;&nbsp;&nbsp;&nbsp;- `outgoing`：出站流量（含 current/average/maximum/total/unit 字段） |
| **nload_mcp** | list_network_interfaces | 获取本地或远程主机的所有网络网卡名称（用于选择监控目标） | - `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取 3 个网卡名称"）<br>- `data`：包含网卡列表的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `interfaces`：网卡名称列表（如 ["eth0", "lo"]） |

---

#### netstat_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | query_network_connections | 通过 `netstat` 查询本地/远程主机的网络连接列表（支持 TCP/UDP 筛选、TCP 状态过滤） | - `proto`：协议类型（tcp/udp/all，默认 all）<br>- `state`：连接状态（仅 TCP 有效，如 ESTABLISHED/LISTENING，默认不筛选）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取本地 TCP 连接，共 12 条"）<br>- `data`：包含连接数据的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `connection_count`：符合条件的连接总数<br>&nbsp;&nbsp;- `connections`：连接列表（每条含 protocol/recv_queue/local_ip/local_port/foreign_ip/foreign_port/state/pid/program 字段）<br>&nbsp;&nbsp;- `filter`：筛选条件（proto/state） |
| **netstat_mcp** | check_port_occupation | 通过 `netstat` 检测本地/远程主机指定端口的占用情况（含进程关联信息） | - `port`：端口号（必填，需为 1-65535 的整数，如 80、443）<br>- `proto`：协议类型（tcp/udp，默认 tcp）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `ssh_port`：SSH 端口（默认 22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "远程主机 192.168.1.100 的端口 80/TCP 被占用：nginx"）<br>- `data`：包含端口占用数据的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `check_port`：检测的端口号<br>&nbsp;&nbsp;- `proto`：检测的协议<br>&nbsp;&nbsp;- `is_occupied`：端口是否被占用（布尔值）<br>&nbsp;&nbsp;- `occupations`：占用列表（每条含 protocol/local_ip/pid/program/state 字段） |

---

#### lsof_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | list_open_files | 查询本地/远程主机的打开文件列表（支持按文件路径、用户筛选） | - `path`：文件路径（可选，指定后仅显示该文件的打开情况）<br>- `user`：用户名（可选，筛选指定用户打开的文件）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取本地打开文件，共 28 个"）<br>- `data`：包含文件信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `file_count`：打开的文件总数<br>&nbsp;&nbsp;- `files`：文件列表（每条含 command/pid/user/fd/type/file_path 等字段）<br>&nbsp;&nbsp;- `filter`：筛选条件（path/user） |
| | list_network_files | 查询本地/远程主机的网络连接相关文件（网络套接字，支持按协议、端口筛选） | - `proto`：协议类型（tcp/udp/all，默认 all）<br>- `port`：端口号（可选，筛选指定端口的网络连接）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `ssh_port`：SSH 端口（默认 22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取 192.168.1.100 的 TCP 网络连接，共 15 条"）<br>- `data`：包含网络连接信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `connection_count`：网络连接总数<br>&nbsp;&nbsp;- `connections`：连接列表（每条含 command/pid/user/local_address/foreign_address/state 等字段）<br>&nbsp;&nbsp;- `filter`：筛选条件（proto/port） |
| **lsof_mcp** | find_process_by_file | 查找本地/远程主机中打开指定文件的进程（精准定位文件占用进程） | - `path`：文件路径（必填，如 /tmp/test.log、/var/log/nginx/access.log）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "找到 2 个在本地打开 /tmp/test.log 的进程"）<br>- `data`：包含进程信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `file_path`：目标文件路径<br>&nbsp;&nbsp;- `process_count`：相关进程总数<br>&nbsp;&nbsp;- `processes`：进程列表（每条含 command/pid/user/fd 等字段） |

---

#### ifconfig_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | get_network_interfaces | 查询本地/远程主机的网络接口详细信息（支持指定单网卡或返回所有网卡） | - `iface`：网卡名称（可选，如 eth0，不填则返回所有网卡）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取本地所有网卡信息，共 3 个"）<br>- `data`：包含网卡信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `interface_count`：网卡总数<br>&nbsp;&nbsp;- `interfaces`：网卡列表（每条含 name/status/mac_address/ipv4/ipv6/mtu/statistics 等字段）<br>&nbsp;&nbsp;- `filter`：筛选条件（iface） |
| **ifconfig_mcp** | get_interface_ip | 查询本地/远程主机指定网卡的 IP 地址信息（专注于 IPv4/IPv6 地址提取） | - `iface`：网卡名称（必填，如 eth0、ens33）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取 eth0 的 IP 地址信息"）<br>- `data`：包含 IP 信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `interface`：网卡名称<br>&nbsp;&nbsp;- `ipv4`：IPv4 地址信息（address/subnet_mask/broadcast）<br>&nbsp;&nbsp;- `ipv6`：IPv6 地址信息（address） |

---

#### ethtool_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | get_interface_details | 查询指定网卡的基础硬件信息（驱动、固件、速率等） | - `iface`：网卡名称（必填，如 eth0、ens33）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取本地网卡 eth0 的详细信息"）<br>- `data`：包含网卡信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `interface`：网卡名称<br>&nbsp;&nbsp;- `basic_info`：基础信息（driver/version/firmware_version/speed/duplex/link_detected 等） |
| | get_interface_features | 查询指定网卡的特性支持情况（网络协议特性、速率模式等） | - `iface`：网卡名称（必填，如 eth0、ens33）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取本地网卡 eth0 的特性信息"）<br>- `data`：包含特性信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `interface`：网卡名称<br>&nbsp;&nbsp;- `features`：特性列表（supported/advertised/speed_duplex） |
| **ethtool_mcp** | set_interface_speed | 设置指定网卡的速率和双工模式（需要管理员权限） | - `iface`：网卡名称（必填，如 eth0、ens33）<br>- `speed`：速率（Mbps，必填，如 10/100/1000）<br>- `duplex`：双工模式（必填，full/half）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功将 eth0 设置为 1000Mbps 全双工"）<br>- `data`：包含配置结果的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `interface`：网卡名称<br>&nbsp;&nbsp;- `configured`：配置信息（speed/duplex） |

---

#### tshark_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | capture_packets | 捕获指定网卡的网络数据包（支持时长、包数、过滤规则限制） | - `iface`：网卡名称（必填，如 eth0、ens33）<br>- `duration`：捕获时长（秒，默认 10，范围 3-60）<br>- `count`：最大捕获包数（可选，如 100，达到即停止）<br>- `filter`：抓包过滤规则（可选，如 `tcp port 80`，遵循 pcap 语法）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "在本地网卡 eth0 上成功捕获 58 个数据包"）<br>- `data`：包含抓包数据的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `interface`：网卡名称<br>&nbsp;&nbsp;- `capture_params`：抓包参数（duration/count/filter）<br>&nbsp;&nbsp;- `packet_count`：实际捕获包数<br>&nbsp;&nbsp;- `packets`：数据包列表（每条含 packet_id/timestamp/src_ip/dst_ip 等字段） |
| **tcpdump_mcp** | analyze_protocol_stats | 分析指定网卡的网络协议分布（统计各协议数据包占比） | - `iface`：网卡名称（必填，如 eth0、ens33）<br>- `duration`：分析时长（秒，默认 10，范围 3-60）<br>- `filter`：分析过滤规则（可选，如 `ip`，仅统计符合条件的流量）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功分析本地网卡 eth0 的协议分布，共捕获 120 个数据包"）<br>- `data`：包含统计数据的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `interface`：网卡名称<br>&nbsp;&nbsp;- `analysis_params`：分析参数（duration/filter）<br>&nbsp;&nbsp;- `stats`：协议统计信息（total_packets 总包数、protocols 各协议计数） |

---

#### firewalld_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | manage_ip_access | 允许/拒绝特定 IP/CIDR 段访问（基于富规则） | - `ip`：目标 IP/CIDR（必填，如 192.168.1.100/24）<br>- `action`：操作类型（必填，allow/deny）<br>- `zone`：防火墙区域（默认 public）<br>- `protocol`：协议（tcp/udp/all，默认 all）<br>- `permanent`：是否永久生效（默认 True）<br>- `host`：远程主机名/IP（默认 localhost）<br>- `port`：SSH 端口（默认 22） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功允许 IP 192.168.1.100 访问 public 区域"）<br>- `data`：包含配置信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `zone`：应用的区域<br>&nbsp;&nbsp;- `rule`：规则详情（ip/action/protocol） |
| | manage_port_access | 添加/移除特定端口的访问权限 | - `port`：端口/端口范围（必填，如 80、80-90）<br>- `protocol`：协议（tcp/udp，默认 tcp）<br>- `action`：操作类型（必填，add/remove）<br>- `zone`：防火墙区域（默认 public）<br>- `permanent`：是否永久生效（默认 True）<br>- `host`：远程主机名/IP（默认 localhost）<br>- `ssh_port`：SSH 端口（默认 22） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功添加端口 80/tcp 访问 public 区域"）<br>- `data`：包含配置信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `zone`：应用的区域<br>&nbsp;&nbsp;- `rule`：规则详情（port/protocol/action） |
| | configure_port_forward | 配置端口转发（源端口→目标 IP:端口） | - `source_port`：源端口（必填，如 80）<br>- `dest_ip`：目标 IP（必填，如 192.168.2.100）<br>- `dest_port`：目标端口（必填，如 8080）<br>- `protocol`：协议（tcp/udp，默认 tcp）<br>- `action`：操作类型（add/remove，默认 add）<br>- `zone`：防火墙区域（默认 public）<br>- `permanent`：是否永久生效（默认 True）<br>- `host`：远程主机名/IP（默认 localhost）<br>- `port`：SSH 端口（默认 22） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功配置端口转发 80/tcp→192.168.2.100:8080"）<br>- `data`：包含转发规则的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `zone`：应用的区域<br>&nbsp;&nbsp;- `forward_rule`：转发详情（source_port/dest_ip 等） |
| | list_firewall_rules | 展示指定区域/所有区域的防火墙规则 | - `zone`：目标区域（可选，不填则查所有）<br>- `host`：远程主机名/IP（默认 localhost）<br>- `port`：SSH 端口（默认 22） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取所有区域规则，共 12 条"）<br>- `data`：包含规则信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `zone`：查询的区域<br>&nbsp;&nbsp;- `rule_count`：规则总数<br>&nbsp;&nbsp;- `rules`：规则列表（按区域分组） |
| **firewalld_mcp** | list_firewall_zones | 展示所有防火墙区域信息（含默认区域、关联接口） | - `host`：远程主机名/IP（默认 localhost）<br>- `port`：SSH 端口（默认 22） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取 5 个区域信息，默认区域 public"）<br>- `data`：包含区域信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `zone_count`：区域总数<br>&nbsp;&nbsp;- `default_zone`：默认区域<br>&nbsp;&nbsp;- `zones`：区域列表（含名称、关联接口等） |

---

#### iptables_mcp

| MCP_Server名称 | MCP_Tool列表            | 工具功能                                   | 核心输入参数                                                                 | 关键返回内容                                                                 |
|----------------|-------------------------|--------------------------------------------|------------------------------------------------------------------------------|------------------------------------------------------------------------------|
|                | manage_ip_rule          | 添加/删除IP访问控制规则（允许/拒绝特定IP的TCP/UDP/全协议流量） | - `ip`：目标IP/CIDR（必填，如192.168.1.100/24）<br>- `action`：动作（必填，ACCEPT/DROP/REJECT）<br>- `chain`：规则链（INPUT/OUTPUT/FORWARD，默认INPUT）<br>- `protocol`：协议（tcp/udp/all，默认all）<br>- `port`：端口号（可选，如80，仅tcp/udp协议有效）<br>- `action_type`：操作类型（add/delete，默认add）<br>- `save`：是否保存规则（True/False，默认False，保存后重启不丢失）<br>- `host`：远程主机名/IP（默认localhost，本地操作可不填）<br>- `port`：SSH端口（默认22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如"成功添加规则：ACCEPT来自192.168.1.0/24的tcp流量（端口80），已保存"）<br>- `data`：包含规则信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `rule`：规则详情（ip/action/chain/protocol/port）<br>&nbsp;&nbsp;- `save_status`：规则保存状态（saved/unsaved） |
|                | configure_port_forward  | 配置基于DNAT的端口转发规则（将源端口流量转发到目标IP:端口） | - `src_port`：源端口（必填，如80，1-65535整数）<br>- `dst_ip`：目标IP（必填，如10.0.0.5，仅支持IPv4）<br>- `dst_port`：目标端口（必填，如8080，1-65535整数）<br>- `protocol`：协议（tcp/udp，默认tcp）<br>- `action`：操作类型（add/remove，默认add）<br>- `save`：是否保存规则（True/False，默认False）<br>- `host`：远程主机名/IP（默认localhost，本地操作可不填）<br>- `ssh_port`：SSH端口（默认22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如"成功添加端口转发：80/tcp → 10.0.0.5:8080"）<br>- `data`：包含转发规则的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `forward_rule`：转发详情（src_port/dst_ip/dst_port/protocol）<br>&nbsp;&nbsp;- `ip_forward_status`：IP转发功能状态（enabled/disabled） |
|                | list_iptables_rules     | 查询指定表/链的所有防火墙规则（支持filter/nat/mangle/raw表） | - `table`：目标表（filter/nat/mangle/raw，默认filter）<br>- `chain`：目标链（可选，如INPUT，不填则查询所有链）<br>- `host`：远程主机名/IP（默认localhost，本地操作可不填）<br>- `ssh_port`：SSH端口（默认22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如"成功获取192.168.1.100的nat表规则，共8条"）<br>- `data`：包含规则信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `table`：查询的表名<br>&nbsp;&nbsp;- `rule_count`：规则总数<br>&nbsp;&nbsp;- `rules`：规则列表（每条含chain/target/protocol/source/destination/details） |
|   **iptables_mcp**  | enable_ip_forward       | 启用/禁用系统IP转发功能（端口转发的前置依赖） | - `enable`：是否启用（True/False，必填）<br>- `persistent`：是否持久化（True/False，默认True，重启后仍生效）<br>- `host`：远程主机名/IP（默认localhost，本地操作可不填）<br>- `ssh_port`：SSH端口（默认22，远程操作时使用，覆盖配置端口） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如"成功禁用192.168.1.100的IP转发功能（非持久化）"）<br>- `data`：包含配置状态的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `enabled`：IP转发启用状态（True/False）<br>&nbsp;&nbsp;- `persistent`：持久化状态（True/False） |

---

#### npu_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | get_npu_status | 通过 `npu-smi` 获取 NPU 设备状态信息（支持查询单个/所有设备） | - `npu_id`：特定 NPU 设备 ID（可选，默认查询所有设备）<br>- `host`：远程主机名/IP（默认 `localhost`，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用）<br>- `username`：SSH 用户名（默认 `root`，远程操作时需指定）<br>- `password`：SSH 密码（远程操作时必填） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取 2 个 NPU 设备信息"）<br>- `data`：包含 NPU 状态的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `npus`：NPU 设备列表，每个设备包含：<br>&nbsp;&nbsp;&nbsp;&nbsp;- `Id`：设备 ID（整数）<br>&nbsp;&nbsp;&nbsp;&nbsp;- `Name`：设备名称<br>&nbsp;&nbsp;&nbsp;&nbsp;- `Memory-Usage`：内存使用（含 used/total）<br>&nbsp;&nbsp;&nbsp;&nbsp;- `Utilization`：设备利用率（%）<br>&nbsp;&nbsp;&nbsp;&nbsp;- `Temperature`：温度（°C） |
| | set_npu_power_limit | 通过 `npu-smi` 设置 NPU 设备的功率限制（单位：瓦特） | - `npu_id`：NPU 设备 ID（非负整数，必填）<br>- `power_limit`：功率限制值（正整数，必填）<br>- `host`：远程主机名/IP（默认 `localhost`，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用）<br>- `username`：SSH 用户名（默认 `root`，远程操作时需指定）<br>- `password`：SSH 密码（远程操作时必填） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "功率限制已设置为 150 瓦特"）<br>- `data`：包含操作详情的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `npu_id`：目标设备 ID<br>&nbsp;&nbsp;- `power_limit`：设置的功率值（瓦特） |
| **npu_mcp** | reset_npu_device | 通过 `npu-smi` 重置 NPU 设备（用于故障恢复） | - `npu_id`：NPU 设备 ID（非负整数，必填）<br>- `host`：远程主机名/IP（默认 `localhost`，本地操作可不填）<br>- `port`：SSH 端口（默认 22，远程操作时使用）<br>- `username`：SSH 用户名（默认 `root`，远程操作时需指定）<br>- `password`：SSH 密码（远程操作时必填） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "NPU 设备 3 已成功重置"）<br>- `data`：包含操作详情的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `npu_id`：被重置的设备 ID |

---

#### sync_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **sync_mcp** | sync_refresh_data_tool | 将内存缓冲区数据写入磁盘 | - `host`：远程主机名/IP（本地采集可不填） | 布尔值，表示缓冲数据是否刷新成功 |

---

#### qemu_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| | manage_vm | 本地/远程主机虚拟机全生命周期管理（创建/启动/停止/删除/修改配置） | - `name`：虚拟机名称（必填，唯一标识虚拟机）<br>- `action`：操作类型（create/start/stop/delete/modify，必填）<br>- `arch`：CPU 架构（create 时必填，如 x86_64/arm64）<br>- `memory`：内存大小（create/modify 可选，如 2G/4096M，默认 2G）<br>- `disk`：磁盘配置（create/modify 可选，格式 "path=/data/vm/disk.qcow2,size=20G"）<br>- `iso`：系统镜像路径（create 可选，如 /data/iso/ubuntu-22.04.iso）<br>- `vcpus`：CPU 核心数（create/modify 可选，默认 2 核）<br>- `vm_dir`：虚拟机存储目录（create 可选，默认 /var/lib/qemu）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `ssh_port`：SSH 端口（默认 22，远程操作时使用）<br>- `ssh_user`：SSH 用户名（远程操作必填）<br>- `ssh_pwd`：SSH 密码（远程操作必填，与 ssh_key 二选一）<br>- `ssh_key`：SSH 私钥路径（远程操作可选，优先于密码） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "虚拟机 ubuntu-vm create 成功"）<br>- `data`：包含虚拟机操作信息的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `vm_name`：虚拟机名称<br>&nbsp;&nbsp;- `action`：执行的操作类型<br>&nbsp;&nbsp;- `details`：操作详情（如修改前后配置对比、磁盘路径） |
| | list_vms | 本地/远程主机虚拟机列表查询（支持按状态、架构、名称筛选） | - `status`：虚拟机状态（可选，running/stopped/all，默认 all）<br>- `arch`：CPU 架构（可选，如 x86_64/arm64，筛选指定架构虚拟机）<br>- `filter_name`：名称模糊筛选（可选，如 "ubuntu" 筛选含该字段的虚拟机）<br>- `vm_dir`：虚拟机存储目录（默认 /var/lib/qemu）<br>- `host`/`ssh_port`/`ssh_user`/`ssh_pwd`/`ssh_key`：同 `manage_vm` | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取本地运行中虚拟机，共 3 个"）<br>- `data`：包含虚拟机列表的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `vm_count`：虚拟机总数<br>&nbsp;&nbsp;- `vms`：虚拟机列表，每个设备包含：<br>&nbsp;&nbsp;&nbsp;&nbsp;- `name`：虚拟机名称<br>&nbsp;&nbsp;&nbsp;&nbsp;- `arch`：CPU 架构<br>&nbsp;&nbsp;&nbsp;&nbsp;- `vcpus`：CPU 核心数<br>&nbsp;&nbsp;&nbsp;&nbsp;- `memory`：内存大小<br>&nbsp;&nbsp;&nbsp;&nbsp;- `disk`：磁盘配置（路径+大小）<br>&nbsp;&nbsp;&nbsp;&nbsp;- `status`：运行状态（running/stopped） |
| **qemu_mcp** | monitor_vm_status | 本地/远程主机虚拟机实时状态监控（CPU/内存/磁盘/网络） | - `name`：虚拟机名称（必填，指定监控目标）<br>- `metrics`：监控指标（可选，cpu/memory/disk/network/all，默认 all）<br>- `interval`：监控采样间隔（可选，单位秒，默认 5 秒，最小值 1 秒）<br>- `count`：采样次数（可选，默认 1 次，0 表示持续采样直到手动停止）<br>- `host`/`ssh_port`/`ssh_user`/`ssh_pwd`/`ssh_key`：同 `manage_vm` | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功获取 ubuntu-vm 5 次采样数据"）<br>- `data`：包含监控数据的字典<br>&nbsp;&nbsp;- `host`：操作的主机名/IP<br>&nbsp;&nbsp;- `vm_name`：虚拟机名称<br>&nbsp;&nbsp;- `timestamp`：采样时间列表（对应每条数据的时间戳）<br>&nbsp;&nbsp;- `metrics_data`：监控指标数据（按 metrics 字段返回对应指标的采样值） |

---

#### nmap_mcp

| MCP_Server 名称 | MCP_Tool 列表 | 工具功能 | 核心输入参数 | 关键返回内容 |
|-----------------|---------------|----------|--------------|--------------|
| **nmap_mcp** | scan_network | 本地/远程主机的 IP/网段扫描（支持主机发现、端口探测、服务识别） | - `target`：扫描目标（必填，支持单个 IP、CIDR 网段、IP 范围，如 192.168.1.1、192.168.1.0/24、192.168.1.1-100）<br>- `scan_type`：扫描类型（可选，basic/full/quick，默认 basic；basic=常用 100 端口，full=1-65535 全端口，quick=10 个核心端口）<br>- `port_range`：自定义端口范围（可选，如 22,80-443，优先级高于 scan_type）<br>- `host_discovery`：是否仅主机发现（不扫描端口，True/False，默认 False）<br>- `host`：远程主机名/IP（默认 localhost，本地操作可不填）<br>- `ssh_port`：SSH 端口（默认 22，远程操作时使用）<br>- `ssh_user`：SSH 用户名（远程操作必填）<br>- `ssh_pwd`：SSH 密码（远程操作可选，与 ssh_key 二选一）<br>- `ssh_key`：SSH 私钥路径（远程操作可选，优先于密码） | - `success`：操作是否成功（布尔值）<br>- `message`：操作结果描述（如 "成功扫描 192.168.1.0/24，发现 8 台活跃主机"）<br>- `data`：包含扫描结果的字典<br>&nbsp;&nbsp;- `host`：执行扫描的主机名/IP<br>&nbsp;&nbsp;- `target`：扫描目标<br>&nbsp;&nbsp;- `scan_type`：扫描类型（含 custom，即自定义端口）<br>&nbsp;&nbsp;- `host_count`：发现的主机总数<br>&nbsp;&nbsp;- `up_host_count`：活跃主机数量<br>&nbsp;&nbsp;- `results`：主机列表，每个主机包含：<br>&nbsp;&nbsp;&nbsp;&nbsp;- `ip`：主机 IP<br>&nbsp;&nbsp;&nbsp;&nbsp;- `status`：状态（up/down/unknown）<br>&nbsp;&nbsp;&nbsp;&nbsp;- `status_details`：状态详情（如延迟时间）<br>&nbsp;&nbsp;&nbsp;&nbsp;- `open_ports`：开放端口列表（含端口号、状态、服务名、详情） |

---

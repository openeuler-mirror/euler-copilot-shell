# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

from gettext import gettext as _

BRAND_NAME = 'EulerCopilot'

main_exit_prompt = _('\033[33m输入 "exit" 或按下 Ctrl+C 结束对话\033[0m')
main_service_is_none = _('\033[1;31m未正确配置 LLM 后端，请检查配置文件\033[0m')
main_service_framework_plugin_is_none = _('\033[1;31m获取插件失败或插件列表为空\n请联系管理员检查后端配置\033[0m')
main_exec_builtin_cmd = _('不支持执行 Shell 内置命令 "{cmd_prefix}"，请复制后手动执行')
main_exec_value_error = _('执行命令时出错：{error}')
main_exec_not_found_error = _('命令不存在：{error}')
main_exec_cmd_failed_with_exit_code = _('命令 "{cmd}" 执行中止，退出码：{exit_code}')

cli_help_prompt_question = _('通过自然语言提问')
cli_help_prompt_switch_mode = _('切换到{mode}模式')
cli_help_prompt_init_settings = _('初始化 copilot 设置')
cli_help_prompt_edit_settings = _('编辑 copilot 设置')
cli_help_prompt_select_backend = _('选择大语言模型后端')
cli_help_panel_switch_mode = _('选择问答模式')
cli_help_panel_advanced_options = _('高级选项')
cli_notif_select_one_mode = _('\033[1;31m当前版本只能选择一种问答模式\033[0m')
cli_notif_compatibility = _('\033[33m当前大模型后端不支持{mode}功能\033[0m\n\
    \033[33m推荐使用 {brand_name} 智能体框架\033[0m')
cli_notif_no_config = _('\033[1;31m请先初始化 copilot 设置\033[0m\n\
    \033[33m请使用 "copilot --init" 命令初始化\033[0m')

interact_action_explain = _('解释命令')
interact_action_edit = _('编辑命令')
interact_action_execute = _('执行命令')
interact_action_explain_selected = _('解释指定命令')
interact_action_edit_selected = _('编辑指定命令')
interact_action_execute_selected = _('执行指定命令')
interact_action_execute_all = _('执行所有命令')
interact_backend_framework = _('{brand_name} 智能体')
interact_backend_spark = _('讯飞星火大模型')
interact_backend_openai = _('OpenAI 兼容模式')
interact_cancel = _('取消')

interact_question_select_action = _('选择要执行的操作：')
interact_question_select_cmd = _('选择命令：')
interact_question_select_backend = _('请选择大模型后端：')
interact_question_select_plugin = _('请选择插件：')
interact_select_plugins_valiidate = _('请选择至少一个插件')

backend_general_request_failed = _('请求失败: {code}')
backend_framework_auth_invalid_api_key = _('{brand_name} 智能体 API 密钥无效，请检查配置文件')
backend_framework_request_connection_error = _('{brand_name} 智能体连接失败，请检查网络连接')
backend_framework_request_timeout = _('{brand_name} 智能体请求超时，请检查网络连接')
backend_framework_request_exceptions = _('{brand_name} 智能体请求异常，请检查网络连接')
backend_framework_request_unauthorized = _('当前会话已过期，请退出后重试')
backend_framework_request_too_many_requests = _('请求过于频繁，请稍后再试')
backend_framework_response_ended_prematurely = _('请求异常中止，请检查网络连接')
backend_framework_stream_error = _('{brand_name} 智能体遇到错误，请联系管理员定位问题')
backend_framework_stream_unknown = _('{brand_name} 智能体返回了未知内容：\n```json\n{content}\n```')
backend_framework_stream_sensitive = _('检测到违规信息，请重新提问')
backend_framework_sugggestion = _('**你可以继续问** {sugggestion}')
backend_spark_stream_error = _('请求错误: {code}\n{message}')
backend_spark_websockets_exceptions_msg_title = _('\033[1;31m请求错误\033[0m\n\n')
backend_spark_websockets_exceptions_msg_a = _('请检查 appid 和 api_key 是否正确，或检查网络连接是否正常。\n')
backend_spark_websockets_exceptions_msg_b = _('输入 "vi ~/.config/eulercopilot/config.json" 查看和编辑配置；\n')
backend_spark_websockets_exceptions_msg_c = _('或尝试 ping {spark_url}')
backend_spark_network_error = _('访问大模型失败，请检查网络连接')
backend_openai_request_connection_error = _('连接大模型失败')
backend_openai_request_timeout = _('请求大模型超时')
backend_openai_request_exceptions = _('请求大模型异常')

query_mode_chat = _('智能问答')
query_mode_flow = _('智能工作流')
query_mode_diagnose = _('智能诊断')
query_mode_tuning = _('智能调优')

prompt_general_root_true = _('当前用户为 root 用户，你生成的 shell 命令不能包涵 sudo')
prompt_general_root_false = _('当前用户为普通用户，若你生成的 shell 命令需要 root 权限，需要包含 sudo')
prompt_general_system = _('''你是操作系统 {os} 的运维助理，你精通当前操作系统的管理和运维，熟悉运维脚本的编写。
你的任务是：
根据用户输入的问题，提供相应的操作系统的管理和运维解决方案，并使用 shell 脚本或其它常用编程语言实现。
你给出的答案必须符合当前操作系统要求，你不能使用当前操作系统没有的功能。

格式要求：
你的回答必须使用 Markdown 格式，代码块和表格都必须用 Markdown 呈现；
你需要用中文回答问题，除了代码，其他内容都要符合汉语的规范。

用户可能问你一些操作系统相关的问题，你尤其需要注意安装软件包的情景：
openEuler 使用 dnf 或 yum 管理软件包，你不能在回答中使用 apt 或其他命令；
Debian 和 Ubuntu 使用 apt 管理软件包，你也不能在回答中使用 dnf 或 yum 命令；
你可能还会遇到使用其他类 unix 系统的情景，比如 macOS 要使用 Homebrew 安装软件包。

请特别注意当前用户的权限：
{prompt_general_root}

在给用户返回 shell 命令时，你必须返回安全的命令，不能进行任何危险操作！
如果涉及到删除文件、清理缓存、删除用户、卸载软件、wget下载文件等敏感操作，你必须生成安全的命令

危险操作举例：
+ 例1: 强制删除
  ```bash
  rm -rf /path/to/sth
  ```
+ 例2: 卸载软件包时默认同意
  ```bash
  dnf remove -y package_name
  ```
你不能输出类似于上述例子的命令！

由于用户使用命令行与你交互，你需要避免长篇大论，请使用简洁的语言，一般情况下你的回答不应超过1000字。
''')
prompt_general_chat = _('''根据用户输入的问题，使用 Markdown 格式输出。

用户的问题：
{question}

基本要求：
1. 如果涉及到生成 shell 命令，请用单行 shell 命令回答，不能使用多行 shell 命令
2. 如果涉及 shell 命令或代码，请用 Markdown 代码块输出，必须标明代码的语言
3. 如果用户要求你生成的命令涉及到数据输入，你需要正确处理数据输入的方式，包括用户交互
4. 当前操作系统是 {os}，你的回答必须符合当前系统要求，不能使用当前系统没有的功能
''')
prompt_general_explain_cmd = _('''```bash
{cmd}
```
请解释上面的 Shell 命令

要求：
先在代码块中打印一次上述命令，再有条理地解释命令中的主要步骤
''')
prompt_framework_primary = _('''你的任务是：
根据用户输入的问题，提供相应的操作系统的管理和运维解决方案。
你给出的答案必须符合当前操作系统要求，你不能使用当前操作系统没有的功能。

格式要求：
+ 你的回答中的代码块和表格都必须用 Markdown 呈现；
+ 你需要用中文回答问题，除了代码，其他内容都要符合汉语的规范。

其他要求：
+ 如果用户要求安装软件包，请注意 openEuler 使用 dnf 管理软件包，你不能在回答中使用 apt 或其他软件包管理器
+ 请特别注意当前用户的权限：{prompt_general_root}

在给用户返回 shell 命令时，你必须返回安全的命令，不能进行任何危险操作！
如果涉及到删除文件、清理缓存、删除用户、卸载软件、wget下载文件等敏感操作，你必须生成安全的命令

危险操作举例：
+ 例1: 强制删除
  ```bash
  rm -rf /path/to/sth
  ```
+ 例2: 卸载软件包时默认同意
  ```bash
  dnf remove -y package_name
  ```
你不能输出类似于上述例子的命令！

由于用户使用命令行与你交互，你需要避免长篇大论，请使用简洁的语言，一般情况下你的回答不应超过1000字。
''')
prompt_framework_plugin_ip = _('当前机器的IP为')

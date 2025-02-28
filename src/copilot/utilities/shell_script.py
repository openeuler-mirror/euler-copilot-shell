# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.

import os
import uuid


def write_shell_script(content: str) -> str:
    """将脚本内容写进 sh 文件中，并返回执行命令"""
    script_name = f"plugin_gen_script_{str(uuid.uuid4())[:8]}.sh"
    script_path = os.path.join(os.path.expanduser("~"), ".eulercopilot", "scripts", script_name)
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as script_file:
        script_file.write(content)
    os.chmod(script_path, 0o700)
    return f"bash {script_path}"

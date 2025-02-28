# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.

import os
import platform
import re
import subprocess
import sys
from typing import Optional


def _exec_shell_cmd(cmd: list) -> Optional[subprocess.CompletedProcess]:
    try:
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr)
        return None
    except FileNotFoundError as e:
        sys.stderr.write(str(e))
        return None
    return process


def _porc_linux_info(shell_result: Optional[subprocess.CompletedProcess]):
    if shell_result is not None:
        pattern = r'PRETTY_NAME="(.+?)"'
        match = re.search(pattern, shell_result.stdout)
        if match:
            return match.group(1)  # 返回括号内匹配的内容，即PRETTY_NAME的值
    return "Unknown Linux distribution"


def _porc_macos_info(shell_result: Optional[subprocess.CompletedProcess]):
    if shell_result is not None:
        macos_info = {}
        if shell_result.returncode == 0:
            lines = shell_result.stdout.splitlines()
            for line in lines:
                key, value = line.split(":\t\t", maxsplit=1)
                macos_info[key.strip()] = value.strip()
        product_name = macos_info.get("ProductName")
        product_version = macos_info.get("ProductVersion")
        if product_name is not None and product_version is not None:
            return f"{product_name} {product_version}"
    return "Unknown macOS version"


def get_os_info() -> str:
    system = platform.system()
    if system == "Linux":
        return _porc_linux_info(_exec_shell_cmd(["cat", "/etc/os-release"]))
    elif system == "Darwin":
        return _porc_macos_info(_exec_shell_cmd(["sw_vers"]))
    else:
        return system


def is_root() -> bool:
    return os.geteuid() == 0

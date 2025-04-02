#!/usr/bin/env python3
# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.

import sys

from copilot.app.copilot_cli import entry_point

if __name__ == "__main__":
    code = entry_point()
    sys.exit(code)

# -*- coding: utf-8 -*-
"""
統一動能策略 - 執行腳本
"""

import os
import sys

# 加入路徑
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from unified_strategy import main

if __name__ == "__main__":
    main()

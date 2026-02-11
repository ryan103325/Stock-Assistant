# -*- coding: utf-8 -*-
"""
CMoney 三維度策略 - 執行腳本
"""

import os
import sys

# 加入路徑
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from cmoney_strategy import run_cmoney_strategy

if __name__ == "__main__":
    run_cmoney_strategy()


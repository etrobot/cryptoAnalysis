import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import date, datetime, timedelta
from market_data.bybit_api import get_kline
from factors.support import compute_support

# 获取BTCUSDT的K线数据
print("获取BTCUSDT的K线数据...")
df = get_kline('BTCUSDT', date.today() - timedelta(days=10), date.today())
print('K线数据:')
print(df)
print()

# 准备用于支撑因子计算的数据
history_data = {'BTCUSDT': df}

# 计算支撑因子，使用较小的窗口大小
print("计算支撑因子...")
support_df = compute_support(history_data, window_size=10)  # 使用较小的窗口大小
print('支撑因子计算结果:')
print(support_df)
print()
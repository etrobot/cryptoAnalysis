import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import date, datetime, timedelta
from market_data.bybit_api import get_kline
from factors.momentum import compute_momentum

# 获取BTCUSDT的K线数据
print("获取BTCUSDT的K线数据...")
df = get_kline('BTCUSDT', date.today() - timedelta(days=10), date.today())
print('K线数据:')
print(df)
print()

# 准备用于动量因子计算的数据
history_data = {'BTCUSDT': df}

# 计算动量因子
print("计算动量因子...")
momentum_df = compute_momentum(history_data)
print('动量因子计算结果:')
print(momentum_df)
print()
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import date, datetime, timedelta
from market_data.bybit_api import get_kline
from data_management.crypto_data_manager import save_daily_data

# 获取BTCUSDT的K线数据
print("获取BTCUSDT的K线数据...")
df = get_kline('BTCUSDT', date.today() - timedelta(days=10), date.today())
print('K线数据:')
print(df)
print()

# 准备保存到数据库的数据
history_data = {'BTCUSDT': df}
print("准备保存到数据库的数据:")
print(history_data)
print()

# 保存数据到数据库
print("保存数据到数据库...")
total_saved = save_daily_data(history_data)
print(f"保存了 {total_saved} 条记录")
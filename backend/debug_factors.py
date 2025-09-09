import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import date, datetime, timedelta
from market_data.bybit_api import get_kline
from data_management.crypto_data_manager import load_daily_data_for_analysis
from market_data import compute_factors
from data_management.crypto_data_manager import save_crypto_symbol_info

# 获取BTCUSDT的K线数据
print("获取BTCUSDT的K线数据...")
df = get_kline('BTCUSDT', date.today() - timedelta(days=10), date.today())
print('K线数据:')
print(df)
print()

# 准备用于因子计算的数据
history_data = {'BTCUSDT': df}
top_symbols = pd.DataFrame([{'symbol': 'BTCUSDT', 'name': 'BTC/USDT'}])

# 计算因子
print("计算因子...")
factors_df = compute_factors(top_symbols, history_data)
print('因子计算结果:')
print(factors_df)
print()

# 检查从数据库加载的数据
print("从数据库加载数据...")
db_history_data = load_daily_data_for_analysis(['BTCUSDT'], limit=10)
print('从数据库加载的数据:')
for symbol, data in db_history_data.items():
    print(f'{symbol}:')
    print(data)
    print()
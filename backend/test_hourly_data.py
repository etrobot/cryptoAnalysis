#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import date, datetime, timedelta
from market_data.bybit_api import get_kline
from data_management.crypto_data_manager import save_hourly_data

def test_hourly_data():
    print("=== 测试小时线数据获取和保存 ===")
    
    # 获取BTCUSDT的1小时K线数据
    print("1. 获取BTCUSDT的1小时K线数据...")
    try:
        df = get_kline('BTCUSDT', date.today() - timedelta(days=2), date.today(), interval='60')
        print(f"   K线数据形状: {df.shape}")
        print(f"   K线数据列: {df.columns.tolist()}")
        
        if not df.empty:
            print("   前3行数据:")
            print(df.head(3))
            print("   数据类型:")
            print(df.dtypes)
            print()
            
            # 准备保存到数据库的数据
            history_data = {'BTCUSDT': df}
            
            # 保存数据到数据库
            print("2. 保存小时数据到数据库...")
            try:
                total_saved = save_hourly_data(history_data)
                print(f"   成功保存了 {total_saved} 条记录")
            except Exception as e:
                print(f"   保存失败: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("   没有获取到数据")
    except Exception as e:
        print(f"   获取数据失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_hourly_data()
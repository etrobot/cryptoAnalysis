#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import date, datetime, timedelta
from market_data.data_fetcher import fetch_top_symbols_by_turnover, fetch_history
from data_management.crypto_data_manager import save_hourly_data, save_crypto_symbol_info

def test_full_analysis_flow():
    print("=== 测试完整分析流程 ===")
    
    try:
        # Step 1: 获取Top交易对
        print("1. 获取Top 5交易对...")
        top_symbols_df = fetch_top_symbols_by_turnover(5)
        print(f"   获取到 {len(top_symbols_df)} 个交易对")
        print(f"   交易对列表: {top_symbols_df['symbol'].tolist()}")
        
        # Step 2: 保存交易对信息
        print("2. 保存交易对信息...")
        save_crypto_symbol_info(top_symbols_df)
        print("   交易对信息保存成功")
        
        # Step 3: 获取历史数据
        symbols_to_process = top_symbols_df["symbol"].tolist()
        today = date.today()
        start_1h = today - timedelta(days=3)  # 只获取3天的数据进行测试
        
        print(f"3. 获取1小时K线数据 ({start_1h} 到 {today})...")
        history_1h = fetch_history(symbols_to_process, start_1h, today, interval="60")
        print(f"   成功获取 {len(history_1h)} 个交易对的数据")
        
        for symbol, df in history_1h.items():
            print(f"   {symbol}: {len(df)} 条记录")
        
        # Step 4: 保存小时数据
        print("4. 保存1小时K线到数据库...")
        try:
            total_saved = save_hourly_data(history_1h)
            print(f"   成功保存了 {total_saved} 条记录")
        except Exception as e:
            print(f"   保存失败: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        print("✅ 完整分析流程测试成功！")
        return True
        
    except Exception as e:
        print(f"❌ 分析流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_full_analysis_flow()
"""
K线交易策略
基于成交额排名和连续阳线/阴线模式的交易策略
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import requests
import os

from market_data.data_fetcher import fetch_top_symbols_by_turnover
from utils import update_task_progress

logger = logging.getLogger(__name__)

# Proxy configuration
proxy_url = os.getenv('PROXY_URL')
proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None

BASE_URL = "https://api.bybit.com/v5"

class CandlestickStrategy:
    def __init__(self):
        self.timeframes = ["3", "5", "10", "15", "30", "60"]  # 分钟级别
        self.position_size = 0.2  # 1/5仓位
        self.active_positions = {}  # 记录活跃头寸
        
    def get_kline_data(self, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
        """获取指定时间周期的K线数据"""
        try:
            url = f"{BASE_URL}/market/kline"
            params = {
                "category": "spot",
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            
            response = requests.get(url, params=params, proxies=proxies, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get("retCode") == 0 and result["result"]["list"]:
                klines = result["result"]["list"]
                
                df = pd.DataFrame(
                    klines,
                    columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"]
                )
                
                # 转换数据类型
                df["timestamp"] = pd.to_numeric(df["timestamp"])
                df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
                df["open"] = pd.to_numeric(df["open"])
                df["high"] = pd.to_numeric(df["high"])
                df["low"] = pd.to_numeric(df["low"])
                df["close"] = pd.to_numeric(df["close"])
                df["volume"] = pd.to_numeric(df["volume"])
                
                # 按时间排序(最新的在前面)
                df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)
                
                # 计算涨跌
                df["is_green"] = df["close"] > df["open"]  # 阳线
                df["is_red"] = df["close"] < df["open"]    # 阴线
                
                return df
            else:
                logger.warning(f"No K-line data for {symbol} interval {interval}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error fetching K-line data for {symbol} interval {interval}: {e}")
            return pd.DataFrame()
    
    def count_consecutive_candles(self, df: pd.DataFrame, candle_type: str) -> int:
        """计算连续的阳线或阴线数量"""
        if df.empty:
            return 0
        
        count = 0
        column = "is_green" if candle_type == "green" else "is_red"
        
        # 从最新K线开始计算连续数量
        for i in range(len(df)):
            if df.iloc[i][column]:
                count += 1
            else:
                break
                
        return count
    
    def load_selected_timeframes(self) -> List[str]:
        """从每日分析结果中加载预选的时间周期"""
        import json
        import os
        
        try:
            analysis_file = "debug_output/timeframe_analysis.json"
            if os.path.exists(analysis_file):
                with open(analysis_file, "r", encoding="utf-8") as f:
                    analysis_data = json.load(f)
                
                selected_timeframes = analysis_data.get("selected_timeframes", [])
                if selected_timeframes:
                    # 移除 'm' 后缀，因为内部逻辑使用纯数字
                    timeframes = [tf.replace('m', '') for tf in selected_timeframes]
                    logger.info(f"Loaded selected timeframes: {timeframes}")
                    return timeframes
            
            logger.warning("No timeframe analysis found, using default timeframes")
            return ["3", "5", "10", "15"]  # 默认时间周期
            
        except Exception as e:
            logger.error(f"Failed to load timeframe analysis: {e}")
            return ["3", "5", "10", "15"]  # 出错时使用默认值
    
    def load_trading_symbols(self) -> List[str]:
        """从每日分析结果中加载预选的交易币种"""
        import json
        import os
        
        try:
            analysis_file = "debug_output/timeframe_analysis.json"
            if os.path.exists(analysis_file):
                with open(analysis_file, "r", encoding="utf-8") as f:
                    analysis_data = json.load(f)
                
                trading_symbols = analysis_data.get("trading_symbols", [])
                if trading_symbols:
                    logger.info(f"Loaded trading symbols: {trading_symbols}")
                    return trading_symbols
            
            logger.warning("No trading symbols found in analysis, fetching current top symbols")
            return []
            
        except Exception as e:
            logger.error(f"Failed to load trading symbols: {e}")
            return []
    
    def check_pattern_three_green_then_sideways(self, df: pd.DataFrame) -> bool:
        """检查是否有连续3阳线后震荡10根K线的模式"""
        if len(df) < 13:  # 需要至少13根K线
            return False
        
        # 检查最新的10根K线是否为震荡(没有连续3根同色)
        recent_10 = df.head(10)
        
        # 检查是否有连续3根阳线或阴线
        for i in range(len(recent_10) - 2):
            if (recent_10.iloc[i]["is_green"] and 
                recent_10.iloc[i+1]["is_green"] and 
                recent_10.iloc[i+2]["is_green"]):
                return False
            if (recent_10.iloc[i]["is_red"] and 
                recent_10.iloc[i+1]["is_red"] and 
                recent_10.iloc[i+2]["is_red"]):
                return False
        
        # 检查第11-13根K线是否为连续3阳线
        if (df.iloc[10]["is_green"] and 
            df.iloc[11]["is_green"] and 
            df.iloc[12]["is_green"]):
            logger.info("Pattern found: 3 green candles followed by 10 sideways candles")
            return True
        
        return False
    
    def check_pattern_sideways_then_three_red(self, df: pd.DataFrame) -> bool:
        """检查是否有震荡10根K线后连续3阴线的模式"""
        if len(df) < 13:
            return False
        
        # 检查最新的3根K线是否为连续3阴线
        if (df.iloc[0]["is_red"] and 
            df.iloc[1]["is_red"] and 
            df.iloc[2]["is_red"]):
            
            # 检查第4-13根K线是否为震荡(没有连续3根同色)
            middle_10 = df.iloc[3:13]
            
            for i in range(len(middle_10) - 2):
                if (middle_10.iloc[i]["is_green"] and 
                    middle_10.iloc[i+1]["is_green"] and 
                    middle_10.iloc[i+2]["is_green"]):
                    return False
                if (middle_10.iloc[i]["is_red"] and 
                    middle_10.iloc[i+1]["is_red"] and 
                    middle_10.iloc[i+2]["is_red"]):
                    return False
            
            logger.info("Pattern found: 10 sideways candles followed by 3 red candles")
            return True
        
        return False
    
    def send_trade_signal(self, symbol: str, action: str, price: float, timeframe: str) -> bool:
        """发送交易信号到Freqtrade"""
        try:
            # 这里应该调用Freqtrade API发送交易信号
            # 由于是模拟交易，我们只记录信号
            signal = {
                "symbol": symbol,
                "action": action,
                "price": price,
                "timeframe": timeframe,
                "position_size": self.position_size,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Trade signal: {signal}")
            
            # 记录活跃头寸
            if action == "buy":
                self.active_positions[symbol] = {
                    "entry_price": price,
                    "entry_time": datetime.now(),
                    "timeframe": timeframe,
                    "candles_count": 0
                }
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send trade signal for {symbol}: {e}")
            return False
    
    def check_exit_conditions(self, position_key: str, current_price: float) -> bool:
        """检查是否满足退出条件(7根K线后)"""
        if position_key not in self.active_positions:
            return False
        
        position = self.active_positions[position_key]
        timeframe = position["timeframe"]
        symbol = position_key.split('_')[0]  # 从 "BTCUSDT_5" 中提取 "BTCUSDT"
        
        # 获取最新数据更新K线计数
        df = self.get_kline_data(symbol, timeframe, limit=10)
        if df.empty:
            return False
        
        # 计算从入场以来的K线数量
        entry_time = position["entry_time"]
        timeframe_minutes = int(timeframe)
        elapsed_minutes = (datetime.now() - entry_time).total_seconds() / 60
        candles_elapsed = int(elapsed_minutes / timeframe_minutes)
        
        if candles_elapsed >= 7:
            logger.info(f"Exit condition met for {position_key}: {candles_elapsed} candles elapsed")
            return True
        
        return False
    
    def monitor_and_trade(self, symbols: List[str], selected_timeframes: List[str], task_id: Optional[str] = None) -> Dict:
        """监控交易对并执行交易策略，使用预选的时间周期"""
        results = {
            "analyzed_symbols": len(symbols),
            "selected_timeframes": selected_timeframes,
            "signals_sent": [],
            "positions_closed": [],
            "timeframe_analysis": {}
        }
        
        for i, symbol in enumerate(symbols):
            if task_id:
                progress = 0.3 + (0.6 * i / len(symbols))
                update_task_progress(task_id, progress, f"监控交易对 {i+1}/{len(symbols)}: {symbol}")
            
            try:
                symbol_results = {}
                
                # 遍历所有预选的时间周期
                for timeframe in selected_timeframes:
                    # 获取该时间周期的数据
                    df = self.get_kline_data(symbol, timeframe, limit=50)
                    if df.empty:
                        continue
                    
                    current_price = float(df.iloc[0]["close"])
                    
                    # 检查是否已有持仓需要平仓
                    position_key = f"{symbol}_{timeframe}"
                    if self.check_exit_conditions(position_key, current_price):
                        if self.send_trade_signal(symbol, "sell", current_price, timeframe):
                            results["positions_closed"].append({
                                "symbol": symbol,
                                "price": current_price,
                                "timeframe": timeframe
                            })
                            if position_key in self.active_positions:
                                del self.active_positions[position_key]
                    
                    # 检查入场信号(如果该时间周期没有持仓)
                    if position_key not in self.active_positions:
                        pattern1 = self.check_pattern_three_green_then_sideways(df)
                        pattern2 = self.check_pattern_sideways_then_three_red(df)
                        
                        if pattern1 or pattern2:
                            if self.send_trade_signal(symbol, "buy", current_price, timeframe):
                                results["signals_sent"].append({
                                    "symbol": symbol,
                                    "pattern": "3green+10sideways" if pattern1 else "10sideways+3red",
                                    "price": current_price,
                                    "timeframe": timeframe
                                })
                                # 使用组合键记录持仓
                                self.active_positions[position_key] = {
                                    "entry_price": current_price,
                                    "entry_time": datetime.now(),
                                    "timeframe": timeframe,
                                    "candles_count": 0
                                }
                    
                    # 记录该时间周期的分析结果
                    symbol_results[timeframe] = {
                        "has_position": position_key in self.active_positions,
                        "pattern_detected": pattern1 or pattern2 if position_key not in self.active_positions else False
                    }
                
                results["timeframe_analysis"][symbol] = symbol_results
                
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue
        
        return results

def run_candlestick_strategy(task_id: Optional[str] = None) -> Dict:
    """运行K线交易策略，使用每日预选的币种和时间周期"""
    logger.info("Starting candlestick trading strategy")
    
    try:
        if task_id:
            update_task_progress(task_id, 0.05, "初始化K线策略")
        
        # 1. 初始化策略
        strategy = CandlestickStrategy()
        
        # 2. 加载每日分析的预选币种和时间周期
        if task_id:
            update_task_progress(task_id, 0.1, "加载预选交易币种和时间周期")
        
        trading_symbols = strategy.load_trading_symbols()
        selected_timeframes = strategy.load_selected_timeframes()
        
        # 如果没有预选币种，获取当前成交额前5名作为备选
        if not trading_symbols:
            logger.info("No pre-selected symbols, fetching current top symbols")
            top_symbols_df = fetch_top_symbols_by_turnover(top_n=5)
            if top_symbols_df.empty:
                logger.error("No symbols found")
                return {"error": "No symbols found"}
            trading_symbols = top_symbols_df["symbol"].tolist()
        
        logger.info(f"Trading symbols: {trading_symbols}")
        logger.info(f"Selected timeframes: {selected_timeframes}")
        
        if task_id:
            update_task_progress(task_id, 0.2, f"开始监控 {len(trading_symbols)} 个交易对")
        
        # 3. 执行策略
        results = strategy.monitor_and_trade(trading_symbols, selected_timeframes, task_id)
        
        if task_id:
            update_task_progress(task_id, 1.0, "K线策略执行完成")
        
        logger.info(f"Candlestick strategy completed: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Candlestick strategy failed: {e}")
        if task_id:
            update_task_progress(task_id, 1.0, f"策略执行失败: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    # 测试运行
    result = run_candlestick_strategy()
    print(f"Strategy result: {result}")
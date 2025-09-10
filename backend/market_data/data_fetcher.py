from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

import pandas as pd
from utils import update_task_progress
from .bybit_api import get_symbols, get_kline, get_spot_tickers

logger = logging.getLogger(__name__)

def fetch_symbols() -> pd.DataFrame:
    """Fetch all available symbols from Bybit"""
    logger.info("Fetching all symbols from Bybit...")
    df = get_symbols()
    if 'symbol' in df.columns and 'baseCoin' in df.columns and 'quoteCoin' in df.columns:
        df['name'] = df.get('name') if 'name' in df.columns else (df['baseCoin'] + '/' + df['quoteCoin'])
    logger.info(f"Successfully fetched {len(df)} symbols from Bybit")
    return df


def fetch_top_symbols_by_turnover(top_n: int = 50) -> pd.DataFrame:
    """获取按24小时成交额排序的前N个交易对（USDT现货）"""
    logger.info(f"Fetching top {top_n} symbols by 24h turnover from Bybit...")
    tickers = get_spot_tickers()
    if tickers.empty:
        logger.warning("Tickers empty, fallback to all symbols (unsorted)")
        all_symbols = fetch_symbols()
        return all_symbols.head(top_n)

    # 保留USDT计价的交易对（Bybit现货symbols本身是形如 'BTCUSDT'，tickers不直接给quote）
    # 这里用简单规则：以USDT结尾
    tickers = tickers[tickers['symbol'].str.endswith('USDT', na=False)].copy()
    if tickers.empty:
        logger.warning("No USDT spot tickers found, fallback to head")
        all_symbols = fetch_symbols()
        return all_symbols.head(top_n)

    # 按24h成交额排序
    tickers = tickers.sort_values('turnover24h', ascending=False)
    top = tickers.head(top_n).copy()

    # 加入name列（BASE/USDT）
    top['baseCoin'] = top['symbol'].str.replace('USDT', '', regex=False)
    top['quoteCoin'] = 'USDT'
    top['name'] = top['baseCoin'] + '/' + top['quoteCoin']

    # 只返回和get_symbols一致的关键列
    return top[['symbol', 'baseCoin', 'quoteCoin', 'name']]


def fetch_history(symbols: List[str], start_date: date, end_date: date, task_id: Optional[str] = None, interval: str = "D") -> Dict[str, pd.DataFrame]:
    """Fetch historical k-line data for multiple symbols"""
    import time
    
    history: Dict[str, pd.DataFrame] = {}
    
    logger.info(f"Fetching historical data for {len(symbols)} symbols from {start_date} to {end_date} (interval: {interval})")
    
    failed_symbols = []
    
    for i, symbol in enumerate(symbols):
        if task_id:
            progress = 0.2 + (0.5 * i / len(symbols))  # 20%-70% of total progress
            update_task_progress(task_id, progress, f"获取历史数据 {i+1}/{len(symbols)}: {symbol}")
        
        logger.info(f"Fetching data for symbol {i+1}/{len(symbols)}: {symbol}")
        
        try:
            # 添加超时控制，避免单个交易对获取时间过长
            df = get_kline(symbol, start_date, end_date, interval=interval)
            
            if not df.empty:
                df["symbol"] = symbol
                history[symbol] = df
                logger.info(f"Successfully fetched {len(df)} records for {symbol}")
            else:
                logger.warning(f"No data returned for {symbol}")
                failed_symbols.append(symbol)
                
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            failed_symbols.append(symbol)
            # 如果连续失败太多，可能是网络问题，增加延迟
            if len(failed_symbols) >= 2:
                logger.warning("连续获取失败，增加延迟时间")
                time.sleep(2)  # 增加延迟
        
        # Add delay between symbol requests to prevent API overload
        if i < len(symbols) - 1:  # Don't delay after the last symbol
            time.sleep(0.3)  # 300ms delay between symbols
            
        if (i + 1) % 10 == 0:  # 更频繁的进度报告
            logger.info(f"Processed {i + 1}/{len(symbols)} symbols, successful: {len(history)}, failed: {len(failed_symbols)}")
    
    if failed_symbols:
        logger.warning(f"Failed to fetch data for {len(failed_symbols)} symbols: {failed_symbols[:5]}{'...' if len(failed_symbols) > 5 else ''}")
    
    logger.info(f"Successfully fetched historical data for {len(history)} symbols out of {len(symbols)} requested")
    return history

def compute_factors(top_symbols: pd.DataFrame, history: Dict[str, pd.DataFrame], task_id: Optional[str] = None, selected_factors: Optional[List[str]] = None) -> pd.DataFrame:
    """Compute comprehensive factors for crypto analysis via pluggable factor modules"""
    from factors import compute_all_factors, compute_selected_factors

    logger.info("Computing factors using modular plugins...")

    if task_id:
        update_task_progress(task_id, 0.7, "计算各类因子")

    # Filter history to only include top symbols
    filtered_history = {symbol: df for symbol, df in history.items() if symbol in top_symbols["symbol"].values}

    # Compute selected or all registered factor dataframes
    if selected_factors:
        factors_df = compute_selected_factors(filtered_history, top_symbols, selected_factors)
        logger.info(f"Computing selected factors: {selected_factors}")
    else:
        factors_df = compute_all_factors(filtered_history, top_symbols)
        logger.info("Computing all available factors")

    if factors_df is None or factors_df.empty:
        logger.warning("No factor data calculated")
        factors_df = pd.DataFrame({"symbol": list(filtered_history.keys())})

    result = factors_df

    # Add current price, symbol name and other basic info
    current_data = []
    for symbol in result["symbol"].tolist():
        df = filtered_history.get(symbol)
        if df is not None and not df.empty:
            # 确保DataFrame有正确的列名
            if "date" in df.columns:
                df = df.rename(columns={"date": "日期"})
            if "close" in df.columns:
                df = df.rename(columns={"close": "收盘"})
            if "change_pct" in df.columns:
                df = df.rename(columns={"change_pct": "涨跌幅"})
            
            # 检查必要的列是否存在
            required_columns = ["日期", "收盘", "涨跌幅"]
            if all(col in df.columns for col in required_columns):
                df_sorted = df.sort_values("日期")
                symbol_name = top_symbols[top_symbols["symbol"] == symbol]["name"].iloc[0] if "name" in top_symbols.columns and len(top_symbols[top_symbols["symbol"] == symbol]) > 0 else symbol
                current_data.append({
                    "symbol": symbol,
                    "name": symbol_name,
                    "当前价格": float(df_sorted["收盘"].iloc[-1]),
                    "涨跌幅": float(df_sorted["涨跌幅"].iloc[-1]) if "涨跌幅" in df_sorted.columns else 0
                })
            else:
                # 如果缺少必要的列，使用默认值
                symbol_name = top_symbols[top_symbols["symbol"] == symbol]["name"].iloc[0] if "name" in top_symbols.columns and len(top_symbols[top_symbols["symbol"] == symbol]) > 0 else symbol
                current_data.append({
                    "symbol": symbol,
                    "name": symbol_name,
                    "当前价格": 0,
                    "涨跌幅": 0
                })

    current_df = pd.DataFrame(current_data)
    if not current_df.empty:
        result = result.merge(current_df, on="symbol", how="left")

    # Generic score computation: for any column ending with '因子', compute a percentile rank score with suffix '评分'
    score_columns = []
    for col in list(result.columns):
        if isinstance(col, str) and col.endswith("因子"):
            score_col = col.replace("因子", "评分")
            try:
                result[score_col] = result[col].rank(ascending=True, pct=True)
                score_columns.append(score_col)
            except Exception:
                pass

    # Composite score: average of all available score columns if any
    if score_columns:
        result["综合评分"] = result[score_columns].mean(axis=1)
        result = result.sort_values("综合评分", ascending=False)

    if task_id:
        update_task_progress(task_id, 0.9, "计算因子评分")

    logger.info(f"Calculated factors for {len(result)} symbols")
    return result

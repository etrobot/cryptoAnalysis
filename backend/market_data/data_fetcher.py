from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

import pandas as pd
from utils import update_task_progress
from .bybit_api import get_symbols, get_kline

logger = logging.getLogger(__name__)

def fetch_symbols() -> pd.DataFrame:
    """Fetch all available symbols from Bybit"""
    logger.info("Fetching all symbols from Bybit...")
    df = get_symbols()
    logger.info(f"Successfully fetched {len(df)} symbols from Bybit")
    return df

def fetch_history(symbols: List[str], start_date: date, end_date: date, task_id: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """Fetch historical k-line data for multiple symbols"""
    history: Dict[str, pd.DataFrame] = {}
    
    logger.info(f"Fetching historical data for {len(symbols)} symbols from {start_date} to {end_date}")
    
    for i, symbol in enumerate(symbols):
        if task_id:
            progress = 0.2 + (0.5 * i / len(symbols))  # 20%-70% of total progress
            update_task_progress(task_id, progress, f"获取历史数据 {i+1}/{len(symbols)}: {symbol}")
        
        df = get_kline(symbol, start_date, end_date)
        
        if not df.empty:
            df["symbol"] = symbol
            history[symbol] = df
            
            if (i + 1) % 20 == 0:
                logger.info(f"Processed {i + 1}/{len(symbols)} symbols")
    
    logger.info(f"Successfully fetched historical data for {len(history)} symbols")
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
            df_sorted = df.sort_values("日期")
            symbol_name = top_symbols[top_symbols["symbol"] == symbol]["name"].iloc[0] if "name" in top_symbols.columns and len(top_symbols[top_symbols["symbol"] == symbol]) > 0 else symbol
            current_data.append({
                "symbol": symbol,
                "name": symbol_name,
                "当前价格": float(df_sorted["收盘"].iloc[-1]),
                "涨跌幅": float(df_sorted["涨跌幅"].iloc[-1]) if "涨跌幅" in df_sorted.columns else 0
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

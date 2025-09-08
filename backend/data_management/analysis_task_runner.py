from __future__ import annotations
import logging
import threading
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

import numpy as np
import pandas as pd
from sqlmodel import Session, select, func

from models import Task, TaskStatus, engine, DailyMarketData
from utils import (
    get_task, 
    update_task_progress,
    set_last_completed_task,
)
from market_data import fetch_symbols, fetch_history, compute_factors
from .crypto_data_manager import (
    save_daily_data,
    save_crypto_symbol_info,
    load_daily_data_for_analysis,
    get_missing_daily_data,
)

logger = logging.getLogger(__name__)

def run_analysis_task(task_id: str, top_n: int, selected_factors: Optional[List[str]] = None, 
                     collect_latest_data: bool = True, stop_event: Optional[threading.Event] = None):
    """The main crypto analysis task runner"""
    
    task = get_task(task_id)
    if not task:
        logger.error(f"Task {task_id} not found")
        return

    def check_cancel() -> bool:
        if stop_event is not None and stop_event.is_set():
            task.status = TaskStatus.CANCELLED
            task.message = "任务已取消"
            task.completed_at = datetime.now().isoformat()
            logger.info(f"Task {task_id} cancelled by user")
            return True
        return False

    try:
        task.status = TaskStatus.RUNNING
        update_task_progress(task_id, 0.0, "开始分析任务")

        # Step 1: Fetch all symbols from Bybit
        update_task_progress(task_id, 0.05, "获取所有交易对")
        if check_cancel(): return
        all_symbols_df = fetch_symbols()
        if all_symbols_df.empty:
            raise Exception("Failed to fetch symbols from Bybit.")

        # Step 2: Save new symbols to DB
        update_task_progress(task_id, 0.1, "保存交易对信息")
        if check_cancel(): return
        save_crypto_symbol_info(all_symbols_df)

        # Step 3: Select top N symbols (for now, just by order from API, which is not ideal)
        # A better approach would be to get symbols with highest volume in the last 24h
        update_task_progress(task_id, 0.15, "筛选热门交易对")
        if check_cancel(): return
        top_symbols_df = all_symbols_df.head(top_n).copy()
        symbols_to_process = top_symbols_df["symbol"].tolist()
        logger.info(f"Selected top {len(symbols_to_process)} symbols to process.")

        # Step 4: Determine what historical data is missing
        if collect_latest_data:
            update_task_progress(task_id, 0.2, "检查缺失的K线数据")
            if check_cancel(): return
            today = date.today()
            missing_data_info = get_missing_daily_data(symbols_to_process)
            
            # Step 5: Fetch missing historical data
            if missing_data_info:
                update_task_progress(task_id, 0.25, f"获取 {len(missing_data_info)} 个交易对的历史K线")
                if check_cancel(): return
                
                history_to_save = {}
                for i, (symbol, start_date) in enumerate(missing_data_info.items()):
                    if check_cancel(): break
                    update_task_progress(task_id, 0.25 + (0.2 * i / len(missing_data_info)), f"获取K线: {symbol}")
                    # Fetch data from start_date to today
                    history_df = fetch_history([symbol], start_date, today)
                    if symbol in history_df and not history_df[symbol].empty:
                        history_to_save[symbol] = history_df[symbol]
                
                # Step 6: Save fetched data to DB
                if history_to_save:
                    update_task_progress(task_id, 0.45, "保存K线数据到数据库")
                    if check_cancel(): return
                    save_daily_data(history_to_save)
            else:
                update_task_progress(task_id, 0.45, "所有K线数据都已是最新")

        # Step 7: Load data for analysis
        update_task_progress(task_id, 0.7, "从数据库加载数据进行因子计算")
        if check_cancel(): return
        history_for_factors = load_daily_data_for_analysis(symbols_to_process, limit=120)

        # Step 8: Compute factors
        factor_msg = f"计算{'选定' if selected_factors else '所有'}因子"
        update_task_progress(task_id, 0.85, factor_msg)
        if check_cancel(): return
        
        # We need a dataframe with 'symbol' and 'name' for compute_factors
        top_symbols_for_factors = all_symbols_df[all_symbols_df['symbol'].isin(symbols_to_process)]

        df = compute_factors(top_symbols_for_factors, history_for_factors, task_id=task_id, selected_factors=selected_factors)

        update_task_progress(task_id, 0.95, "数据清理和格式化")
        if check_cancel(): return

        if not df.empty:
            df = df.replace({np.nan: None})
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            for col in numeric_columns:
                df[col] = df[col].astype(float, errors='ignore')
        
        data = df.to_dict(orient="records") if not df.empty else []
        
        result = {
            "data": data,
            "count": len(data),
            "extended": None, # Removed extended analysis for now
        }

        # Step 9: Complete the task
        task.status = TaskStatus.COMPLETED
        task.progress = 1.0
        task.message = f"分析完成，共 {result['count']} 条结果"
        task.completed_at = datetime.now().isoformat()
        task.result = result
        set_last_completed_task(task)
        logger.info(f"Analysis task {task_id} completed successfully.")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        task.status = TaskStatus.FAILED
        task.message = f"任务失败: {e}"
        task.completed_at = datetime.now().isoformat()
        task.error = str(e)

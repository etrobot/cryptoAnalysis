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
from market_data import fetch_symbols, fetch_history, compute_factors, fetch_top_symbols_by_turnover
from .crypto_data_manager import (
    save_daily_data,
    save_crypto_symbol_info,
    load_daily_data_for_analysis,
    get_missing_daily_data,
    save_hourly_data,
    load_hourly_data_for_analysis,
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
            from utils import bump_task_version
            bump_task_version(task_id)
            return True
        return False

    try:
        task.status = TaskStatus.RUNNING
        from utils import bump_task_version
        bump_task_version(task_id)
        update_task_progress(task_id, 0.0, "开始分析任务")

        # Step 1: 获取成交额Top交易对，避免遍历所有交易对
        update_task_progress(task_id, 0.05, "获取成交额Top交易对")
        if check_cancel(): return
        top_symbols_df = fetch_top_symbols_by_turnover(top_n)
        if top_symbols_df.empty:
            raise Exception("Failed to fetch top symbols by turnover from Bybit.")

        # Step 2: 保存交易对信息（仅Top列表）
        update_task_progress(task_id, 0.1, "保存交易对信息")
        if check_cancel(): return
        save_crypto_symbol_info(top_symbols_df)

        # Step 3: 确认要处理的列表
        update_task_progress(task_id, 0.15, "筛选热门交易对")
        if check_cancel(): return
        symbols_to_process = top_symbols_df["symbol"].tolist()
        logger.info(f"Selected top {len(symbols_to_process)} symbols to process by 24h turnover.")

        # Step 4-6: 直接获取90天的1小时K线，避免全量日线耗时
        if collect_latest_data:
            if check_cancel(): return
            today = date.today()
            start_1h = today - timedelta(days=90)
            update_task_progress(task_id, 0.25, f"获取1小时K线（近90天，共 {len(symbols_to_process)} 个交易对）")
            history_1h = fetch_history(symbols_to_process, start_1h, today, task_id=task_id, interval="60")
            # 入库小时数据
            update_task_progress(task_id, 0.4, "保存1小时K线到数据库")
            try:
                save_hourly_data(history_1h)
            except Exception as e:
                logger.warning(f"保存小时数据失败: {e}")
            history_for_factors = history_1h
        else:
            # 可选：从数据库加载最近的小时数据用于计算
            history_for_factors = load_hourly_data_for_analysis(symbols_to_process, limit=24*90)

        # Step 7: 准备数据进行因子计算
        update_task_progress(task_id, 0.7, "加载数据进行因子计算")
        if check_cancel(): return

        # Step 8: Compute factors
        factor_msg = f"计算{'选定' if selected_factors else '所有'}因子"
        update_task_progress(task_id, 0.85, factor_msg)
        if check_cancel(): return
        
        # We need a dataframe with 'symbol' and 'name' for compute_factors
        top_symbols_for_factors = top_symbols_df[top_symbols_df['symbol'].isin(symbols_to_process)]

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
        from utils import bump_task_version
        bump_task_version(task_id)
        logger.info(f"Analysis task {task_id} completed successfully.")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        task.status = TaskStatus.FAILED
        task.message = f"任务失败: {e}"
        task.completed_at = datetime.now().isoformat()
        task.error = str(e)
        from utils import bump_task_version
        bump_task_version(task_id)

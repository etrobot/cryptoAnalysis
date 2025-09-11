"""
定时任务调度器
每天UTC 0点运行分析和新闻评估任务
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from data_management.services import create_analysis_task, create_news_evaluation_task

logger = logging.getLogger(__name__)

class TaskScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=timezone.utc)
        self.is_running = False
        self.enabled = True
        self.last_run: Optional[str] = None
        self.current_analysis_task_id: Optional[str] = None
        self.current_news_task_id: Optional[str] = None

    def start(self):
        """启动调度器"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        try:
            # 添加每日UTC 0点的定时任务
            self.scheduler.add_job(
                func=self._run_daily_tasks,
                trigger=CronTrigger(hour=0, minute=0, timezone=timezone.utc),
                id="daily_crypto_analysis",
                name="Daily Crypto Analysis and News Evaluation",
                replace_existing=True
            )
            
            self.scheduler.start()
            self.is_running = True
            logger.info("Task scheduler started successfully")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    def stop(self):
        """停止调度器"""
        if not self.is_running:
            return
        
        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Task scheduler stopped")
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")

    def stop_current_tasks(self) -> bool:
        """停止当前运行的定时任务"""
        stopped_any = False
        
        try:
            from utils import TASK_STOP_EVENTS
            
            # 停止分析任务
            if self.current_analysis_task_id:
                stop_event = TASK_STOP_EVENTS.get(self.current_analysis_task_id)
                if stop_event:
                    stop_event.set()
                    stopped_any = True
                    logger.info(f"Requested stop for analysis task: {self.current_analysis_task_id}")
            
            # 停止新闻任务
            if self.current_news_task_id:
                stop_event = TASK_STOP_EVENTS.get(self.current_news_task_id)
                if stop_event:
                    stop_event.set()
                    stopped_any = True
                    logger.info(f"Requested stop for news task: {self.current_news_task_id}")
            
            return stopped_any
        except Exception as e:
            logger.error(f"Failed to stop current tasks: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        from utils import get_task
        
        # 获取下次运行时间
        next_run = None
        if self.is_running:
            try:
                job = self.scheduler.get_job("daily_crypto_analysis")
                if job and job.next_run_time:
                    next_run = job.next_run_time.isoformat()
            except Exception as e:
                logger.error(f"Failed to get next run time: {e}")
        
        # 检查当前任务状态
        analysis_task = None
        news_task = None
        
        if self.current_analysis_task_id:
            analysis_task = get_task(self.current_analysis_task_id)
        if self.current_news_task_id:
            news_task = get_task(self.current_news_task_id)
        
        return {
            "scheduler_running": self.is_running,
            "enabled": self.enabled,
            "last_run": self.last_run,
            "next_run": next_run,
            "current_analysis_task": {
                "task_id": self.current_analysis_task_id,
                "status": analysis_task.status if analysis_task else None,
                "progress": analysis_task.progress if analysis_task else None,
                "message": analysis_task.message if analysis_task else None
            } if self.current_analysis_task_id else None,
            "current_news_task": {
                "task_id": self.current_news_task_id,
                "status": news_task.status if news_task else None,
                "progress": news_task.progress if news_task else None,
                "message": news_task.message if news_task else None
            } if self.current_news_task_id else None
        }

    def enable_scheduled_tasks(self, enabled: bool):
        """启用或禁用定时任务"""
        self.enabled = enabled
        logger.info(f"Scheduled tasks {'enabled' if enabled else 'disabled'}")

    def _run_daily_tasks(self):
        """运行每日任务序列"""
        if not self.enabled:
            logger.info("Scheduled tasks are disabled, skipping")
            return

        self.last_run = datetime.now(timezone.utc).isoformat()
        logger.info("Starting daily scheduled tasks")
        
        try:
            # 第一阶段：运行分析任务
            logger.info("Starting analysis phase")
            analysis_task_id = create_analysis_task(
                top_n=20,  # 分析前20个币种
                selected_factors=None,  # 所有因子
                collect_latest_data=True  # 收集最新数据
            )
            self.current_analysis_task_id = analysis_task_id
            logger.info(f"Created analysis task: {analysis_task_id}")
            
            # 等待分析任务完成
            self._wait_for_task_completion(analysis_task_id, "Analysis")
            
            # 第二阶段：运行新闻评估任务
            logger.info("Starting news evaluation phase")
            news_task_id = create_news_evaluation_task(
                top_n=10,  # 评估前10个币种
                news_per_symbol=3,  # 每个币种3条新闻
                openai_model="gpt-oss-120b"  # 默认模型
            )
            self.current_news_task_id = news_task_id
            logger.info(f"Created news evaluation task: {news_task_id}")
            
            # 等待新闻任务完成
            self._wait_for_task_completion(news_task_id, "News evaluation")
            
            logger.info("Daily scheduled tasks completed successfully")
            
        except Exception as e:
            logger.error(f"Daily scheduled tasks failed: {e}")
        finally:
            # 清理任务ID
            self.current_analysis_task_id = None
            self.current_news_task_id = None

    def _wait_for_task_completion(self, task_id: str, task_name: str, max_wait_seconds: int = 3600):
        """等待任务完成，最多等待1小时"""
        import time
        from utils import get_task
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            task = get_task(task_id)
            if not task:
                logger.error(f"{task_name} task {task_id} not found")
                return
            
            if task.status in ["completed", "failed", "cancelled"]:
                logger.info(f"{task_name} task {task_id} finished with status: {task.status}")
                return
            
            # 每10秒检查一次
            time.sleep(10)
        
        logger.warning(f"{task_name} task {task_id} timed out after {max_wait_seconds} seconds")

# 全局调度器实例
task_scheduler = TaskScheduler()

def start_scheduler():
    """启动全局调度器"""
    task_scheduler.start()

def stop_scheduler():
    """停止全局调度器"""
    task_scheduler.stop()

def get_scheduler_status():
    """获取调度器状态"""
    return task_scheduler.get_status()

def stop_current_scheduled_task():
    """停止当前运行的定时任务"""
    return task_scheduler.stop_current_tasks()

def enable_scheduled_tasks(enabled: bool):
    """启用或禁用定时任务"""
    task_scheduler.enable_scheduled_tasks(enabled)
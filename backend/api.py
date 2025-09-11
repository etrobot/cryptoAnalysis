from __future__ import annotations
from typing import List
from fastapi import HTTPException
from models import (
    RunRequest,
    RunResponse,
    TaskResult,
    NewsTaskResult,
    TaskStatus,
    Message,
    AuthRequest,
    AuthResponse,
    User,
    NewsEvaluationRequest,
    get_session,
)
from sqlmodel import select
from utils import get_task, get_all_tasks, get_last_completed_task, TASK_STOP_EVENTS
from data_management.services import create_analysis_task, create_news_evaluation_task


def read_root():
    return {"service": "crypto-analysis-backend", "status": "running"}


def run_analysis(request: RunRequest) -> RunResponse:
    """Start comprehensive crypto analysis as background task"""
    # 强制限制为最多50个交易对
    top_n = min(request.top_n, 50)
    task_id = create_analysis_task(
        top_n, request.selected_factors, request.collect_latest_data
    )

    return RunResponse(
        task_id=task_id, status=TaskStatus.PENDING, message="分析任务已启动"
    )


def stop_analysis(task_id: str) -> TaskResult:
    """Signal a running task to stop and return its status"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    stop_event = TASK_STOP_EVENTS.get(task_id)
    if not stop_event:
        raise HTTPException(
            status_code=400, detail="Task is not cancellable or already finished"
        )

    # Signal cancellation
    stop_event.set()

    # Reflect status change immediately; the worker will mark completed/cancelled later.
    task.status = TaskStatus.RUNNING  # keep running until worker finalizes
    task.message = "已请求停止，正在清理..."
    from utils import bump_task_version

    bump_task_version(task_id)
    return TaskResult(
        task_id=task.task_id,
        status=task.status,
        progress=task.progress,
        message=task.message,
        created_at=task.created_at,
        completed_at=task.completed_at,
        top_n=task.top_n,
        selected_factors=task.selected_factors,
        data=task.result["data"] if task.result else None,
        count=task.result["count"] if task.result else None,
        extended=task.result.get("extended") if task.result else None,
        error=task.error,
    )


def get_task_status(task_id: str) -> TaskResult:
    """Get status of a specific task"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Note: this endpoint is kept for compatibility/polling but SSE is preferred.
    return TaskResult(
        task_id=task.task_id,
        status=task.status,
        progress=task.progress,
        message=task.message,
        created_at=task.created_at,
        completed_at=task.completed_at,
        top_n=task.top_n,
        selected_factors=task.selected_factors,
        data=task.result["data"] if task.result else None,
        count=task.result["count"] if task.result else None,
        extended=task.result.get("extended") if task.result else None,
        error=task.error,
    )


def get_latest_results() -> TaskResult | Message:
    """Get the latest completed task results"""
    last_task = get_last_completed_task()
    if not last_task:
        return Message(message="No results yet. POST /run to start a calculation.")

    return TaskResult(
        task_id=last_task.task_id,
        status=last_task.status,
        progress=last_task.progress,
        message=last_task.message,
        created_at=last_task.created_at,
        completed_at=last_task.completed_at,
        top_n=last_task.top_n,
        selected_factors=last_task.selected_factors,
        data=last_task.result["data"] if last_task.result else None,
        count=last_task.result["count"] if last_task.result else None,
        extended=last_task.result.get("extended") if last_task.result else None,
        error=last_task.error,
    )


def list_all_tasks() -> List[TaskResult]:
    """List all tasks"""
    all_tasks = get_all_tasks()
    return [
        TaskResult(
            task_id=task.task_id,
            status=task.status,
            progress=task.progress,
            message=task.message,
            created_at=task.created_at,
            completed_at=task.completed_at,
            top_n=task.top_n,
            selected_factors=task.selected_factors,
            data=task.result["data"] if task.result else None,
            count=task.result["count"] if task.result else None,
            extended=task.result.get("extended") if task.result else None,
            error=task.error,
        )
        for task in all_tasks.values()
    ]


def login_user(request: AuthRequest) -> AuthResponse:
    """User authentication with username, email and password. Creates user if not exists."""
    try:
        import hashlib
        with next(get_session()) as session:
            # Find user by name and email
            statement = select(User).where(
                User.name == request.name, User.email == request.email
            )
            user = session.exec(statement).first()

            if user and user.password_hash:
                # Verify password for existing user
                password_hash = hashlib.sha256(request.password.encode()).hexdigest()
                if password_hash == user.password_hash:
                    # Authentication successful
                    token = f"token_{user.id}"
                    return AuthResponse(success=True, token=token, message="认证成功")
                else:
                    # Password incorrect
                    return AuthResponse(
                        success=False, 
                        message="密码错误"
                    )
            else:
                # User not found, create new user
                password_hash = hashlib.sha256(request.password.encode()).hexdigest()
                
                # Check if this is the first user (admin)
                all_users_statement = select(User)
                all_users = session.exec(all_users_statement).all()
                is_first_user = len(all_users) == 0
                
                new_user = User(
                    name=request.name,
                    email=request.email,
                    password_hash=password_hash,
                    is_admin=is_first_user  # First user becomes admin
                )
                session.add(new_user)
                session.commit()
                session.refresh(new_user)
                
                # Generate token for new user
                token = f"token_{new_user.id}"
                admin_status = " (管理员)" if is_first_user else ""
                return AuthResponse(
                    success=True, 
                    token=token, 
                    message=f"用户创建成功{admin_status}"
                )

    except Exception as e:
        return AuthResponse(success=False, message=f"认证失败: {str(e)}")


def run_news_evaluation(request: NewsEvaluationRequest) -> RunResponse:
    """Start news evaluation task for top cryptocurrencies"""
    # 限制参数范围
    top_n = min(max(request.top_n, 1), 20)  # 1-20个币种
    news_per_symbol = min(max(request.news_per_symbol, 1), 10)  # 每个币种1-10条新闻

    task_id = create_news_evaluation_task(top_n, news_per_symbol, request.openai_model)

    return RunResponse(
        task_id=task_id, status=TaskStatus.PENDING, message="新闻评估任务已启动"
    )


def _is_news_evaluation_task(task) -> bool:
    """Check if a task is a news evaluation task based on selected_factors being None"""
    return task.selected_factors is None


def get_task_status_universal(task_id: str) -> TaskResult | NewsTaskResult:
    """Get status of a specific task, returning appropriate type based on task type"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if _is_news_evaluation_task(task):
        return NewsTaskResult(
            task_id=task.task_id,
            status=task.status,
            progress=task.progress,
            message=task.message,
            created_at=task.created_at,
            completed_at=task.completed_at,
            result=task.result,
            error=task.error,
        )
    else:
        return TaskResult(
            task_id=task.task_id,
            status=task.status,
            progress=task.progress,
            message=task.message,
            created_at=task.created_at,
            completed_at=task.completed_at,
            top_n=task.top_n,
            selected_factors=task.selected_factors,
            data=task.result["data"] if task.result else None,
            count=task.result["count"] if task.result else None,
            extended=task.result.get("extended") if task.result else None,
            error=task.error,
        )


def stop_task_universal(task_id: str) -> TaskResult | NewsTaskResult:
    """Signal a running task to stop and return its status"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    stop_event = TASK_STOP_EVENTS.get(task_id)
    if not stop_event:
        raise HTTPException(
            status_code=400, detail="Task is not cancellable or already finished"
        )

    # Signal cancellation
    stop_event.set()

    # Reflect status change immediately; the worker will mark completed/cancelled later.
    task.status = TaskStatus.RUNNING  # keep running until worker finalizes
    task.message = "已请求停止，正在清理..."
    from utils import bump_task_version

    bump_task_version(task_id)
    
    if _is_news_evaluation_task(task):
        return NewsTaskResult(
            task_id=task.task_id,
            status=task.status,
            progress=task.progress,
            message=task.message,
            created_at=task.created_at,
            completed_at=task.completed_at,
            result=task.result,
            error=task.error,
        )
    else:
        return TaskResult(
            task_id=task.task_id,
            status=task.status,
            progress=task.progress,
            message=task.message,
            created_at=task.created_at,
            completed_at=task.completed_at,
            top_n=task.top_n,
            selected_factors=task.selected_factors,
            data=task.result["data"] if task.result else None,
            count=task.result["count"] if task.result else None,
            extended=task.result.get("extended") if task.result else None,
            error=task.error,
        )


def get_latest_results_universal() -> TaskResult | NewsTaskResult | Message:
    """Get the latest completed task results, returning appropriate type based on task type"""
    last_task = get_last_completed_task()
    if not last_task:
        return Message(message="No results yet. POST /run to start a calculation.")

    if _is_news_evaluation_task(last_task):
        return NewsTaskResult(
            task_id=last_task.task_id,
            status=last_task.status,
            progress=last_task.progress,
            message=last_task.message,
            created_at=last_task.created_at,
            completed_at=last_task.completed_at,
            result=last_task.result,
            error=last_task.error,
        )
    else:
        return TaskResult(
            task_id=last_task.task_id,
            status=last_task.status,
            progress=last_task.progress,
            message=last_task.message,
            created_at=last_task.created_at,
            completed_at=last_task.completed_at,
            top_n=last_task.top_n,
            selected_factors=last_task.selected_factors,
            data=last_task.result["data"] if last_task.result else None,
            count=last_task.result["count"] if last_task.result else None,
            extended=last_task.result.get("extended") if last_task.result else None,
            error=last_task.error,
        )

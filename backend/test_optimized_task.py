#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_management.services import create_analysis_task
from utils import get_task
import time

def test_optimized_analysis():
    print("=== 测试优化后的分析任务 ===")
    
    print("创建分析任务（Top 2交易对）...")
    task_id = create_analysis_task(top_n=2, collect_latest_data=True)
    print(f"任务ID: {task_id}")
    
    # 等待任务完成
    print("等待任务完成...")
    for i in range(120):  # 最多等待2分钟
        task = get_task(task_id)
        if task:
            print(f"[{i+1:3d}s] 状态: {task.status.value:10s} | 进度: {task.progress:5.1%} | {task.message}")
            
            if task.status.value in ['completed', 'failed', 'cancelled']:
                if task.error:
                    print(f"❌ 错误: {task.error}")
                    return False
                elif task.status.value == 'completed':
                    print("✅ 任务完成成功！")
                    if task.result:
                        print(f"   结果数量: {task.result.get('count', 0)}")
                    return True
                else:
                    print(f"❌ 任务状态: {task.status.value}")
                    return False
        time.sleep(1)
    
    print("❌ 任务超时")
    return False

if __name__ == "__main__":
    success = test_optimized_analysis()
    if success:
        print("\n🎉 数据库写入问题已修复！")
    else:
        print("\n💥 仍然存在问题，需要进一步调试")
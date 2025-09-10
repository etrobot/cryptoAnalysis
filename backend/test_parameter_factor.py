#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_management.analysis_task_runner import run_analysis_task
from data_management.services import create_analysis_task
from utils import get_task
import time
import threading

def test_parameter_passing():
    print("=== 测试参数传递和因子计算 ===")
    
    # 测试1: 基本参数传递
    print("1. 测试Top N参数传递...")
    top_n_values = [5, 10, 15]
    
    for top_n in top_n_values:
        print(f"   测试Top {top_n}...")
        task_id = create_analysis_task(top_n=top_n, collect_latest_data=True)
        task = get_task(task_id)
        if task and task.top_n == top_n:
            print(f"   ✅ Top {top_n} 参数正确传递")
        else:
            print(f"   ❌ Top {top_n} 参数传递失败")
            return False
    
    # 测试2: 特定因子选择
    print("\n2. 测试特定因子选择...")
    selected_factors = ["momentum", "support"]
    task_id = create_analysis_task(top_n=3, selected_factors=selected_factors, collect_latest_data=True)
    task = get_task(task_id)
    
    if task and task.selected_factors == selected_factors:
        print("   ✅ 特定因子参数正确传递")
    else:
        print("   ❌ 特定因子参数传递失败")
        return False
    
    return True

def test_factor_calculation():
    print("\n3. 测试因子计算准确性...")
    
    # 创建测试任务
    task_id = create_analysis_task(top_n=3, collect_latest_data=True)
    
    # 等待任务完成
    print("   等待任务完成...")
    for i in range(60):  # 最多等待60秒
        task = get_task(task_id)
        if task:
            print(f"   [{i+1:2d}s] 状态: {task.status.value:10s} | 进度: {task.progress:5.1%}")
            
            if task.status.value == 'completed':
                print("   ✅ 任务完成成功！")
                
                # 检查结果数据
                if task.result and task.result.get('data'):
                    result_count = task.result.get('count', 0)
                    print(f"   结果数量: {result_count}")
                    
                    # 验证结果结构
                    if result_count > 0:
                        data = task.result.get('data', [])
                        first_result = data[0]
                        
                        # 检查是否包含基本字段
                        required_fields = ['symbol', 'name', '当前价格']
                        for field in required_fields:
                            if field not in first_result:
                                print(f"   ❌ 缺少必要字段: {field}")
                                return False
                        
                        print(f"   ✅ 结果结构验证通过: 包含 {len(first_result)} 个字段")
                        
                        # 检查是否包含因子字段
                        factor_fields = [key for key in first_result.keys() if key.endswith('因子') or key.endswith('评分')]
                        if factor_fields:
                            print(f"   ✅ 因子计算成功: 包含 {len(factor_fields)} 个因子相关字段")
                            for field in factor_fields:
                                print(f"      - {field}: {first_result.get(field)}")
                        else:
                            print("   ⚠️  未发现因子相关字段")
                        
                        return True
                    else:
                        print("   ❌ 结果数据为空")
                        return False
                else:
                    print("   ❌ 未获取到结果数据")
                    return False
            
            elif task.status.value == 'failed':
                print(f"   ❌ 任务失败: {task.error}")
                return False
                
        time.sleep(1)
    
    print("   ❌ 任务超时")
    return False

def test_direct_runner():
    print("\n4. 测试直接调用任务运行器...")
    
    # 创建事件用于取消控制
    stop_event = threading.Event()
    
    # 直接调用运行器
    task_id = create_analysis_task(top_n=2, collect_latest_data=True)
    
    try:
        # 在新线程中运行任务
        thread = threading.Thread(target=run_analysis_task, args=(task_id, 2, None, True, stop_event))
        thread.start()
        
        # 等待几秒后检查进度
        time.sleep(5)
        
        task = get_task(task_id)
        if task:
            print(f"   当前进度: {task.progress:.1%}, 状态: {task.status.value}")
            
            if task.status.value == 'running' and task.progress > 0:
                print("   ✅ 任务运行器正常工作")
                
                # 取消任务
                stop_event.set()
                thread.join(timeout=10)
                
                # 检查是否取消成功
                task = get_task(task_id)
                if task and task.status.value == 'cancelled':
                    print("   ✅ 任务取消功能正常")
                    return True
                else:
                    print("   ❌ 任务取消失败")
                    return False
            else:
                print("   ❌ 任务未正常启动")
                return False
        else:
            print("   ❌ 无法获取任务信息")
            return False
            
    except Exception as e:
        print(f"   ❌ 运行器调用失败: {e}")
        return False

def main():
    print("开始测试参数传递和因子计算功能...\n")
    
    # 测试参数传递
    param_test_passed = test_parameter_passing()
    
    # 测试因子计算
    factor_test_passed = test_factor_calculation()
    
    # 测试直接运行器调用
    runner_test_passed = test_direct_runner()
    
    print("\n" + "="*50)
    print("测试结果汇总:")
    print(f"参数传递测试: {'✅ 通过' if param_test_passed else '❌ 失败'}")
    print(f"因子计算测试: {'✅ 通过' if factor_test_passed else '❌ 失败'}")
    print(f"运行器调用测试: {'✅ 通过' if runner_test_passed else '❌ 失败'}")
    
    all_passed = param_test_passed and factor_test_passed and runner_test_passed
    print(f"\n总体结果: {'🎉 所有测试通过！' if all_passed else '💥 存在失败的测试'}")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
from __future__ import annotations
import logging
import threading
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

import openai
import pandas as pd
from sqlmodel import Session

from models import Task, TaskStatus, engine
from utils import (
    get_task, 
    update_task_progress,
    set_last_completed_task,
)
from market_data import fetch_top_symbols_by_turnover
from news_data import fetch_crypto_news, NewsItem
from llm_utils import evaluate_content_with_llm

logger = logging.getLogger(__name__)

def run_news_evaluation_task(
    task_id: str, 
    top_n: int = 10, 
    news_per_symbol: int = 3,
    openai_model: str = "gpt-oss-120b",
    stop_event: Optional[threading.Event] = None
):
    """
    运行新闻评估任务：获取最新一天成交额top10的加密货币资讯并评估
    
    Args:
        task_id: 任务ID
        top_n: 获取前N个成交额最高的币种
        news_per_symbol: 每个币种获取的新闻数量
        openai_model: 使用的OpenAI模型
        stop_event: 停止事件
    """
    
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
        update_task_progress(task_id, 0.0, "开始新闻评估任务")

        # 初始化OpenAI客户端
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise Exception("未设置OPENAI_API_KEY环境变量")
        
        client = openai.Client(api_key=openai_api_key)

        # Step 1: 获取成交额Top交易对
        update_task_progress(task_id, 0.1, f"获取成交额Top {top_n} 交易对")
        if check_cancel(): return
        
        top_symbols_df = fetch_top_symbols_by_turnover(top_n)
        if top_symbols_df.empty:
            raise Exception("Failed to fetch top symbols by turnover from Bybit.")
        
        symbols_to_process = top_symbols_df["symbol"].tolist()
        logger.info(f"Selected top {len(symbols_to_process)} symbols: {symbols_to_process}")

        # Step 2: 获取新闻数据
        update_task_progress(task_id, 0.2, f"获取 {len(symbols_to_process)} 个币种的新闻数据")
        if check_cancel(): return
        
        news_by_symbol = fetch_crypto_news(symbols_to_process, limit=news_per_symbol)
        
        # 统计获取到的新闻数量
        total_news = sum(len(news_list) for news_list in news_by_symbol.values())
        logger.info(f"获取到总计 {total_news} 条新闻")

        # Step 3: 评估新闻内容
        update_task_progress(task_id, 0.3, "开始评估新闻内容")
        if check_cancel(): return
        
        evaluation_results = []
        
        # 定义评估标准
        criteria_dict = {
            "技术创新与替代潜力": {
                "1分": "技术陈旧，缺乏创新，面临被新协议或链淘汰的风险，生态增长停滞",
                "2分": "技术有渐进式改进，但无显著优势，难以挑战现有主流公链或协议",
                "3分": "技术具备替代潜力（如高TPS、Layer 2优化），处于测试网或早期部署阶段",
                "4分": "替代趋势明确，新技术渗透率快速提升（生态TVL或用户增长10%-30%），开发者采用增加",
                "5分": "革命性技术确立主导地位（如新共识机制、跨链协议），渗透率>30%，旧技术被快速取代"
            },
            "监管与政策环境": {
                "1分": "受严格监管限制（如交易禁令、税收重压），发展空间严重受限",
                "2分": "监管环境中性，无明确支持或限制，政策不确定性较高",
                "3分": "获得一般性政策支持（如纳入国家区块链规划），但具体措施尚未落地",
                "4分": "获得实质性政策支持（如监管沙盒、税收减免、试点项目），合规性增强",
                "5分": "国家级战略重点（如数字货币储备、跨境支付试点），多重政策红利叠加，监管环境极度友好"
            },
            "市场表现与增长": {
                "1分": "价格下滑或交易量萎缩，增长率≤0%，市场关注度低（如X提及量<1万次/月）",
                "2分": "温和增长，价格/交易量增长0%-15%，与市场平均水平相当，缺乏爆发力",
                "3分": "较快增长，价格/交易量增长15%-30%，TVL或链上活动显现成长性",
                "4分": "高速增长，价格/交易量增长30%-50%，显著超越市场平均，机构/鲸鱼积累明显",
                "5分": "爆发式增长，价格/交易量增长>50%，可持续性强（如ETF流入、CME期货活跃）"
            },
            "社区与生态支持": {
                "1分": "社区活跃度低，开发者流失，核心团队不稳定或存在负面事件（如减持、退出）",
                "2分": "社区稳定但无显著增长，开发者参与有限，生态扩展缓慢",
                "3分": "社区活跃度提升，引入激励机制（如质押、治理代币），开发者数量增长",
                "4分": "知名机构或项目方加入生态（如Layer 2、DeFi协议），社区扩张迅速，X讨论量激增",
                "5分": "生态主导市场（如DeFi/NFT龙头），核心社区全球影响力强，顶级资本或开发者全面支持"
            },
            "需求与应用场景": {
                "1分": "应用场景萎缩，产品/服务被替代或过度竞争（如低效公链、单一功能代币）",
                "2分": "需求稳定，满足基础支付或存储需求，增长空间有限",
                "3分": "需求升级，用户为效率或体验支付溢价（如DeFi收益、NFT收藏），场景扩展中",
                "4分": "新需求爆发，服务于金融、娱乐、AI等高价值场景，链上交易量快速增长",
                "5分": "创造全新需求，定义新品类（如RWA代币化、AI代理），市场空间彻底打开"
            }
        }
        
        for i, (symbol, news_list) in enumerate(news_by_symbol.items()):
            if check_cancel(): return
            
            progress = 0.3 + (0.6 * i / len(news_by_symbol))
            update_task_progress(task_id, progress, f"评估 {symbol} 新闻内容 ({i+1}/{len(news_by_symbol)})")
            
            if not news_list:
                # 没有新闻数据的情况
                evaluation_results.append({
                    "symbol": symbol,
                    "base_coin": symbol.replace('USDT', '') if symbol.endswith('USDT') else symbol,
                    "news_count": 0,
                    "evaluation": {
                        "overall_score": 0,
                        "detailed_scores": {},
                        "top_scoring_criterion": "无数据",
                        "top_score": 0,
                    },
                    "news_summary": "未获取到相关新闻",
                    "error": "无新闻数据"
                })
                continue
            
            try:
                # 合并所有新闻内容
                combined_content = _combine_news_content(news_list)
                
                # 使用LLM评估
                evaluation = evaluate_content_with_llm(
                    client=client,
                    model=openai_model,
                    content=combined_content,
                    criteria_dict=criteria_dict
                )
                
                # 构建结果
                result = {
                    "symbol": symbol,
                    "base_coin": symbol.replace('USDT', '') if symbol.endswith('USDT') else symbol,
                    "news_count": len(news_list),
                    "evaluation": evaluation,
                    "news_summary": _create_news_summary(news_list),
                    "news_items": [_news_item_to_dict(item) for item in news_list]
                }
                
                evaluation_results.append(result)
                logger.info(f"完成 {symbol} 评估，总分: {evaluation['overall_score']:.1f}")
                
            except Exception as e:
                logger.error(f"评估 {symbol} 时出错: {e}")
                evaluation_results.append({
                    "symbol": symbol,
                    "base_coin": symbol.replace('USDT', '') if symbol.endswith('USDT') else symbol,
                    "news_count": len(news_list),
                    "evaluation": {
                        "overall_score": 0,
                        "detailed_scores": {},
                        "top_scoring_criterion": "评估失败",
                        "top_score": 0,
                    },
                    "news_summary": _create_news_summary(news_list),
                    "error": str(e)
                })

        # Step 4: 排序和整理结果
        update_task_progress(task_id, 0.95, "整理评估结果")
        if check_cancel(): return
        
        # 按总分排序
        evaluation_results.sort(key=lambda x: x["evaluation"]["overall_score"], reverse=True)
        
        # 构建最终结果
        result = {
            "data": evaluation_results,
            "count": len(evaluation_results),
            "summary": {
                "total_symbols": len(symbols_to_process),
                "total_news": total_news,
                "evaluation_model": openai_model,
                "top_performer": evaluation_results[0] if evaluation_results else None,
                "average_score": sum(r["evaluation"]["overall_score"] for r in evaluation_results) / len(evaluation_results) if evaluation_results else 0
            }
        }

        # Step 5: 完成任务
        task.status = TaskStatus.COMPLETED
        task.progress = 1.0
        task.message = f"新闻评估完成，共评估 {result['count']} 个币种，{total_news} 条新闻"
        task.completed_at = datetime.now().isoformat()
        task.result = result
        set_last_completed_task(task)
        from utils import bump_task_version
        bump_task_version(task_id)
        logger.info(f"News evaluation task {task_id} completed successfully.")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        task.status = TaskStatus.FAILED
        task.message = f"任务失败: {e}"
        task.completed_at = datetime.now().isoformat()
        task.error = str(e)
        from utils import bump_task_version
        bump_task_version(task_id)

def _combine_news_content(news_list: List[NewsItem]) -> str:
    """合并新闻内容用于评估"""
    combined = []
    for news in news_list:
        combined.append(f"标题: {news.title}")
        combined.append(f"内容: {news.content}")
        combined.append(f"来源: {news.source}")
        combined.append("---")
    
    return "\n".join(combined)

def _create_news_summary(news_list: List[NewsItem]) -> str:
    """创建新闻摘要"""
    if not news_list:
        return "无新闻数据"
    
    titles = [news.title for news in news_list]
    return f"共{len(news_list)}条新闻: " + "; ".join(titles[:3]) + ("..." if len(titles) > 3 else "")

def _news_item_to_dict(news_item: NewsItem) -> Dict[str, Any]:
    """将NewsItem转换为字典"""
    return {
        "title": news_item.title,
        "content": news_item.content,
        "url": news_item.url,
        "published_at": news_item.published_at,
        "source": news_item.source,
        "symbol": news_item.symbol
    }
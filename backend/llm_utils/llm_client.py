from __future__ import annotations
import json
import logging
from typing import Dict, Any
import openai

logger = logging.getLogger(__name__)

def llm_gen_dict(client: openai.Client, model: str, query: str, format_example: Dict, stream: bool = False) -> Dict:
    """
    使用LLM生成符合指定格式的字典结果
    
    Args:
        client: OpenAI客户端实例
        model: 模型名称
        query: 查询内容
        format_example: 输出格式示例
        stream: 是否使用流式输出
        
    Returns:
        Dict: 解析后的字典结果
    """
    
    # 构建系统提示，强制输出为JSON格式
    system_prompt = f"""你是一个专业的加密货币分析师。请严格按照以下JSON格式输出结果，不要包含任何其他文字：

输出格式示例：
{json.dumps(format_example, ensure_ascii=False, indent=2)}

重要要求：
1. 输出必须是有效的JSON格式
2. 不要包含任何解释或额外文字
3. 分数必须是1-5的整数
4. 说明必须是中文"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.3,
            stream=stream
        )
        
        if stream:
            # 处理流式响应
            content = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content += chunk.choices[0].delta.content
        else:
            content = response.choices[0].message.content
        
        # 简单的JSON解析，假设LLM返回有效JSON
        result = json.loads(content)
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}")
        # 返回默认格式
        return {}
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        return {}

def evaluate_content_with_llm(client: openai.Client, model: str, content: str, criteria_dict: Dict) -> Dict:
    """
    使用OpenAI API评估内容

    Args:
        client: OpenAI客户端实例
        model: 模型名称
        content: 待评估的内容
        criteria_dict: 评估标准字典

    Returns:
        dict: 包含详细评估结果的字典，格式如下：
        {
            "overall_score": float,  # 总分
            "detailed_scores": dict,  # 各项详细分数
            "top_scoring_criterion": str,  # 最高分标准
            "top_score": float,  # 最高分数
        }
    """

    # 构建输出格式示例
    format_example = {"criteria_name":{"score":"1-5", "explanation":"中文评分说明"}}
    
    query = content + """
按标准评估以上内容：
{
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
"""
    
    # 使用 llm_gen_dict 来强约束输出为 python 字典
    result = llm_gen_dict(client, model, query, format_example, stream=False)

    total_score = sum(int(v['score']) for v in result.values())/5*100/len(result)
    top_criterion = max(result.items(), key=lambda x: x[1]['score'])[0]
    top_score = int(max(result.items(), key=lambda x: x[1]['score'])[1]['score'])/5*100
    
    return {
        "criteria_result": result,
        "overall_score": total_score,
        "detailed_scores": result,  # Add this for compatibility
        "top_scoring_criterion": top_criterion,
        "top_score": top_score,
    }
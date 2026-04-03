"""
优先级智能推荐算法

基于 3 个维度智能推荐任务优先级：
1. 截止时间（40% 权重）
2. 任务依赖（30% 权重）
3. 业务价值（30% 权重）

用户明确指定优先级时，以用户指定为准
"""

from enum import Enum
from typing import Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class Priority(Enum):
    """优先级"""
    CRITICAL = 10    # 紧急故障
    URGENT = 9       # 用户正在等待
    HIGH = 8         # 重要业务
    MEDIUM = 5       # 常规任务
    LOW = 3          # 后台任务
    BACKGROUND = 1   # 可延迟任务


@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str
    task_name: str
    task_type: str  # customer_email/market_research/report/code/etc.
    user_priority: Optional[Priority] = None  # 用户指定的优先级
    deadline: Optional[datetime] = None  # 截止时间
    is_prerequisite: bool = False  # 是否是其他任务的前置条件
    estimated_duration: int = 5  # 预计时长（分钟）
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PriorityAdvisor:
    """优先级智能推荐器"""
    
    # 业务价值评分表
    BUSINESS_VALUE_SCORES = {
        # 高价值（30 分）
        'customer_email': 30,      # 客户邮件
        'customer_call': 30,       # 客户电话
        'contract_review': 30,     # 合同审查
        'payment': 30,             # 付款相关
        
        # 中高价值（25 分）
        'meeting': 25,             # 会议
        'proposal': 25,            # 方案
        'presentation': 25,        # 演示
        
        # 中价值（20 分）
        'market_research': 20,     # 市场调研
        'competitor_analysis': 20, # 竞品分析
        'report': 20,              # 报告
        'analysis': 20,            # 分析
        
        # 中低价值（15 分）
        'documentation': 15,       # 文档
        'code_review': 15,         # 代码审查
        'testing': 15,             # 测试
        
        # 低价值（10 分）
        'data_entry': 10,          # 数据录入
        'file_organization': 10,   # 文件整理
        'backup': 10,              # 备份
    }
    
    # 默认值
    DEFAULT_BUSINESS_VALUE = 15
    DEFAULT_URGENCY_SCORE = 10
    
    def recommend_priority(self, context: TaskContext) -> Priority:
        """
        推荐任务优先级
        
        Args:
            context: 任务上下文
        
        Returns:
            Priority: 推荐的优先级
        """
        # 用户明确指定，直接返回
        if context.user_priority:
            logger.info(f"用户已指定优先级：{context.user_priority.name}")
            return context.user_priority
        
        # 计算各维度得分
        urgency_score = self._calculate_urgency_score(context)  # 0-40
        dependency_score = self._calculate_dependency_score(context)  # 0-30
        business_score = self._calculate_business_score(context)  # 0-30
        
        # 总分
        total_score = urgency_score + dependency_score + business_score
        
        # 转换为优先级
        priority = self._score_to_priority(total_score)
        
        logger.info(f"优先级推荐：{context.task_name} -> {priority.name} "
                   f"(紧急{urgency_score} + 依赖{dependency_score} + 业务{business_score} = {total_score})")
        
        return priority
    
    def _calculate_urgency_score(self, context: TaskContext) -> int:
        """
        计算紧急性得分（0-40 分）
        
        基于截止时间
        """
        if not context.deadline:
            return self.DEFAULT_URGENCY_SCORE
        
        # 计算剩余时间
        now = datetime.now()
        time_left = context.deadline - now
        
        # 已经过期
        if time_left.total_seconds() < 0:
            return 40  # 满分
        
        # 剩余小时数
        hours_left = time_left.total_seconds() / 3600
        
        # 评分
        if hours_left < 1:
            return 40  # 1 小时内，非常紧急
        elif hours_left < 2:
            return 35  # 2 小时内
        elif hours_left < 4:
            return 30  # 4 小时内
        elif hours_left < 8:
            return 25  # 8 小时内
        elif hours_left < 24:
            return 20  # 24 小时内
        elif hours_left < 48:
            return 15  # 48 小时内
        else:
            return 10  # 超过 48 小时，不紧急
    
    def _calculate_dependency_score(self, context: TaskContext) -> int:
        """
        计算依赖得分（0-30 分）
        
        如果是其他任务的前置条件，优先级更高
        """
        if context.is_prerequisite:
            return 30  # 前置任务，满分
        else:
            return 0
    
    def _calculate_business_score(self, context: TaskContext) -> int:
        """
        计算业务价值得分（0-30 分）
        
        基于任务类型
        """
        task_type = context.task_type.lower()
        
        # 查找评分表
        score = self.BUSINESS_VALUE_SCORES.get(task_type, self.DEFAULT_BUSINESS_VALUE)
        
        # 检查关键词匹配（支持部分匹配）
        if score == self.DEFAULT_BUSINESS_VALUE:
            for key_type, key_score in self.BUSINESS_VALUE_SCORES.items():
                if key_type in task_type or task_type in key_type:
                    score = key_score
                    break
        
        logger.debug(f"任务类型 '{context.task_type}' 业务价值得分：{score}")
        return score
    
    def _score_to_priority(self, total_score: int) -> Priority:
        """
        将总分转换为优先级
        
        总分范围：0-100
        """
        if total_score >= 90:
            return Priority.CRITICAL
        elif total_score >= 80:
            return Priority.URGENT
        elif total_score >= 70:
            return Priority.HIGH
        elif total_score >= 40:
            return Priority.MEDIUM
        elif total_score >= 20:
            return Priority.LOW
        else:
            return Priority.BACKGROUND
    
    def explain_recommendation(self, context: TaskContext) -> Dict:
        """
        解释优先级推荐原因
        
        Args:
            context: 任务上下文
        
        Returns:
            Dict: 解释信息
        """
        urgency_score = self._calculate_urgency_score(context)
        dependency_score = self._calculate_dependency_score(context)
        business_score = self._calculate_business_score(context)
        total_score = urgency_score + dependency_score + business_score
        priority = self._score_to_priority(total_score)
        
        # 构建解释
        reasons = []
        
        # 紧急性原因
        if context.deadline:
            hours_left = (context.deadline - datetime.now()).total_seconds() / 3600
            if hours_left < 2:
                reasons.append(f"⏰ 截止时间临近（{hours_left:.1f}小时）")
            elif hours_left < 24:
                reasons.append(f"⏰ 今天截止（{hours_left:.1f}小时）")
        
        # 依赖原因
        if context.is_prerequisite:
            reasons.append("🔗 是其他任务的前置条件")
        
        # 业务价值原因
        task_type = context.task_type.lower()
        if task_type in ['customer_email', 'customer_call']:
            reasons.append("💼 客户相关任务，高优先级")
        elif task_type in ['contract_review', 'payment']:
            reasons.append("💰 合同/付款相关，高优先级")
        elif task_type in ['market_research', 'analysis']:
            reasons.append("📊 研究分析类任务")
        
        return {
            'task_id': context.task_id,
            'task_name': context.task_name,
            'recommended_priority': priority.name,
            'total_score': total_score,
            'breakdown': {
                'urgency': urgency_score,
                'dependency': dependency_score,
                'business_value': business_score
            },
            'reasons': reasons
        }


# 使用示例
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    advisor = PriorityAdvisor()
    
    print("\n=== 测试 1: 客户邮件（无截止时间） ===")
    context1 = TaskContext(
        task_id='task_001',
        task_name='回复客户 A 邮件',
        task_type='customer_email'
    )
    priority1 = advisor.recommend_priority(context1)
    print(f"推荐优先级：{priority1.name}")
    
    explanation1 = advisor.explain_recommendation(context1)
    print(f"原因：{explanation1['reasons']}")
    
    print("\n=== 测试 2: 市场调研（2 小时后截止） ===")
    context2 = TaskContext(
        task_id='task_002',
        task_name='市场调研报告',
        task_type='market_research',
        deadline=datetime.now() + timedelta(hours=2)
    )
    priority2 = advisor.recommend_priority(context2)
    print(f"推荐优先级：{priority2.name}")
    
    explanation2 = advisor.explain_recommendation(context2)
    print(f"原因：{explanation2['reasons']}")
    print(f"得分明细：紧急{explanation2['breakdown']['urgency']} + "
          f"依赖{explanation2['breakdown']['dependency']} + "
          f"业务{explanation2['breakdown']['business_value']} = "
          f"{explanation2['total_score']}")
    
    print("\n=== 测试 3: 前置任务（无截止时间） ===")
    context3 = TaskContext(
        task_id='task_003',
        task_name='数据收集',
        task_type='data_entry',
        is_prerequisite=True
    )
    priority3 = advisor.recommend_priority(context3)
    print(f"推荐优先级：{priority3.name}")
    
    explanation3 = advisor.explain_recommendation(context3)
    print(f"原因：{explanation3['reasons']}")
    
    print("\n=== 测试 4: 用户指定优先级 ===")
    context4 = TaskContext(
        task_id='task_004',
        task_name='产品方案讨论',
        task_type='proposal',
        user_priority=Priority.URGENT
    )
    priority4 = advisor.recommend_priority(context4)
    print(f"推荐优先级：{priority4.name}（用户指定）")

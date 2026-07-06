"""反思脑数据模型

从 reflector_brain.py 抽出的纯数据结构，无业务逻辑。
[P2-15] Step 1: 抽数据模型，保持向后兼容（reflector_brain.py re-export）。
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class EvaluationResult(Enum):
    """评估结果类型枚举"""

    EXCELLENT = "excellent"  # 优秀（完全符合预期）
    GOOD = "good"  # 良好（基本符合预期）
    ACCEPTABLE = "acceptable"  # 可接受（部分符合预期）
    POOR = "poor"  # 差（不符合预期）
    FAILURE = "failure"  # 失败（完全不符合预期）


class NextActionType(Enum):
    """下一步行动类型枚举"""

    CONTINUE = "continue"  # 继续执行（结果符合预期）
    RETRY = "retry"  # 重试（执行失败，可重试）
    ADJUST_STRATEGY = "adjust_strategy"  # 调整策略（路径错误）
    ABANDON = "abandon"  # 放弃（无法完成）
    REVIEW = "review"  # 人工复核（需要人工介入）


class CorrectionStrategy(Enum):
    """修正策略类型枚举"""

    RETRY = "retry"  # 重试当前步骤
    SEARCH_AND_RETRY = "search_and_retry"  # 补充搜索后重试
    SWITCH_SKILL = "switch_skill"  # 换技能执行
    DEGRADE = "degrade"  # 降级到规则引擎


@dataclass
class Evaluation:
    """评估结果对象"""

    result: EvaluationResult  # 评估结果类型
    quality_score: float  # 质量评分 (0.0-1.0)
    deviation_analysis: str  # 偏差分析
    key_findings: Optional[List[str]] = None  # 关键发现

    def __post_init__(self):
        if self.key_findings is None:
            self.key_findings = []


@dataclass
class NextAction:
    """下一步行动对象"""

    action_type: NextActionType  # 行动类型
    reason: str  # 行动原因
    parameters: Optional[Dict[str, Any]] = None  # 行动参数
    confidence: float = 0.0  # 决策置信度

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}

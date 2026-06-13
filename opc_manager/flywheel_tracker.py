"""
Flywheel State Tracker - FlywheelTracker

Implements state tracking for the "Hybrid Ecosystem" flywheel model.
Supports Level 1 → Level 2 → Level 3 growth path visualization.

Phase 2 MVP: In-memory storage + basic statistics
Phase 3 Extension: Database persistence support (FlywheelTrackerDB)
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from opc_manager.business_types import BusinessType


class FlywheelLevel(Enum):
    """Flywheel level enum"""

    LEVEL_1 = 1  # Single business type
    LEVEL_2 = 2  # Dual type combination
    LEVEL_3 = 3  # Full ecosystem (3+ types)


@dataclass
class DimensionScore:
    """Dimension score data class"""

    content_quality: float = 0.0  # Content quality (0-100)
    audience_growth: float = 0.0  # Audience growth (0-100)
    monetization: float = 0.0  # Monetization ability (0-100)
    cross_promotion: float = 0.0  # Cross-domain promotion (0-100)
    ecosystem_synergy: float = 0.0  # Ecosystem synergy (0-100)

    def overall_score(self) -> float:
        """Calculate weighted overall score"""
        weights = [0.25, 0.20, 0.20, 0.15, 0.20]
        scores = [
            self.content_quality,
            self.audience_growth,
            self.monetization,
            self.cross_promotion,
            self.ecosystem_synergy,
        ]
        return sum(w * s for w, s in zip(weights, scores))

    def to_dict(self) -> Dict[str, float]:
        return {
            "content_quality": self.content_quality,
            "audience_growth": self.audience_growth,
            "monetization": self.monetization,
            "cross_promotion": self.cross_promotion,
            "ecosystem_synergy": self.ecosystem_synergy,
            "overall": self.overall_score(),
        }


@dataclass
class UserFlywheelState:
    """User flywheel state data class"""

    user_id: str
    current_level: FlywheelLevel = FlywheelLevel.LEVEL_1
    active_types: List[BusinessType] = field(default_factory=list)
    dimension_scores: DimensionScore = field(default_factory=DimensionScore)
    scenario_completion_count: Dict[str, int] = field(default_factory=dict)
    total_scenarios_completed: int = 0
    active_days: int = 0
    last_activity_date: Optional[str] = None
    achievements: List[Any] = field(default_factory=list)  # Phase 3: Achievement list
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "current_level": self.current_level.value,
            "active_types": [bt.value for bt in self.active_types],
            "active_types_count": len(self.active_types),
            "dimension_scores": self.dimension_scores.to_dict(),
            "total_scenarios_completed": self.total_scenarios_completed,
            "active_days": self.active_days,
            "last_activity_date": self.last_activity_date,
        }


class FlywheelTracker:
    """
    Flywheel State Tracker

    Features:
    - Track user business type activation
    - Calculate flywheel level (Level 1/2/3)
    - Record dimension scores
    - Provide upgrade suggestions
    - Generate flywheel reports
    """

    def __init__(self):
        """Initialize tracker"""
        self.user_states: Dict[str, UserFlywheelState] = {}
        self._level_thresholds = {
            FlywheelLevel.LEVEL_1: 1,
            FlywheelLevel.LEVEL_2: 2,
            FlywheelLevel.LEVEL_3: 3,
        }

    def get_or_create_state(self, user_id: str) -> UserFlywheelState:
        """Get or create user flywheel state"""
        if user_id not in self.user_states:
            self.user_states[user_id] = UserFlywheelState(user_id=user_id)
        return self.user_states[user_id]

    def record_scenario_completion(
        self, user_id: str, scenario_id: str, business_type: BusinessType
    ) -> UserFlywheelState:
        """
        Record scenario completion event

        Args:
            user_id: User ID
            scenario_id: Scenario ID
            business_type: Business type used

        Returns:
            Updated user state
        """
        state = self.get_or_create_state(user_id)

        if business_type not in state.active_types:
            state.active_types.append(business_type)

        if scenario_id not in state.scenario_completion_count:
            state.scenario_completion_count[scenario_id] = 0
        state.scenario_completion_count[scenario_id] += 1
        state.total_scenarios_completed += 1

        today = datetime.now().strftime("%Y-%m-%d")
        if state.last_activity_date != today:
            state.active_days += 1
        state.last_activity_date = today

        state.updated_at = datetime.now().isoformat()

        self._recalculate_level(state)
        self._update_dimension_scores(state)

        return state

    def _recalculate_level(self, state: UserFlywheelState):
        """Recalculate flywheel level based on active types"""
        type_count = len(state.active_types)

        if type_count >= 3:
            state.current_level = FlywheelLevel.LEVEL_3
        elif type_count >= 2:
            state.current_level = FlywheelLevel.LEVEL_2
        else:
            state.current_level = FlywheelLevel.LEVEL_1

    def _update_dimension_scores(self, state: UserFlywheelState):
        """
        Update dimension scores based on user activity data

        Algorithm:
        - content_quality: Based on content_calendar scenario completion count
        - audience_growth: Based on active days and total scenario count
        - monetization: Based on digital_product/ecommerce scenario completion count
        - cross_promotion: Based on cross-type scenario usage
        - ecosystem_synergy: Based on type diversity and total scenario count
        """
        ds = state.dimension_scores

        content_scenarios = state.scenario_completion_count.get("content_calendar", 0)
        ds.content_quality = min(content_scenarios * 15 + 20, 100)

        ds.audience_growth = min(
            (state.active_days * 5) + (state.total_scenarios_completed * 3), 100
        )

        monetization_scenarios = sum(
            state.scenario_completion_count.get(s, 0)
            for s in ["digital_product_launch", "ecommerce_ops"]
        )
        ds.monetization = min(monetization_scenarios * 12 + 10, 100)

        type_diversity = len(state.active_types)
        cross_type_usage = min(type_diversity * 18, 90) if type_diversity > 1 else 0
        ds.cross_promotion = cross_type_usage

        synergy_base = (type_diversity * 12) + (state.total_scenarios_completed * 4)
        ds.ecosystem_synergy = min(synergy_base, 100)

    def get_flywheel_health_score(self, user_id: str) -> float:
        """Get overall flywheel health score (0-100)"""
        state = self.get_or_create_state(user_id)
        return round(state.dimension_scores.overall_score(), 1)

    def get_upgrade_suggestion(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get upgrade suggestion

        Returns:
            Upgrade suggestion dict, or None if already at max level
        """
        state = self.get_or_create_state(user_id)

        if state.current_level == FlywheelLevel.LEVEL_3:
            return None

        suggestions = {
            FlywheelLevel.LEVEL_1: {
                "target_level": 2,
                "title": "解锁双类型组合",
                "description": "你目前专注于单一领域，尝试结合第二类业务可以产生协同效应！",
                "suggested_actions": [
                    f"你已擅长{state.active_types[0].display_name if state.active_types else '当前领域'}",
                    "建议尝试：内容+电商（用内容引流，电商变现）",
                    "或尝试：咨询+产品（将方法论转化为数字产品）",
                ],
                "benefits": ["收入来源多元化", "风险分散化", "技能复用率提升"],
                "estimated_improvement": "+30% 综合效率",
            },
            FlywheelLevel.LEVEL_2: {
                "target_level": 3,
                "title": "进入全生态系统",
                "description": "你已经掌握了两种业务的组合，现在是时候构建完整的商业生态了！",
                "suggested_actions": [
                    f"当前组合: {', '.join([bt.display_name for bt in state.active_types])}",
                    "建议添加第三种能力以形成闭环",
                    "例如：内容→产品→服务 的完整价值链",
                ],
                "benefits": [
                    "构建竞争壁垒",
                    "客户终身价值最大化",
                    "品牌影响力指数级增长",
                ],
                "estimated_improvement": "+80% 商业价值",
            },
        }

        level_key = state.current_level
        suggestion = suggestions.get(level_key)

        if suggestion:
            suggestion["current_state"] = {
                "level": state.current_level.value,
                "active_types": [bt.value for bt in state.active_types],
                "health_score": state.dimension_scores.overall_score(),
            }

        return suggestion

    def generate_flywheel_report(self, user_id: str) -> Dict[str, Any]:
        """
        Generate complete flywheel report

        Returns:
            Detailed report containing all flywheel data
        """
        state = self.get_or_create_state(user_id)

        report = {
            "report_generated_at": datetime.now().isoformat(),
            "user_id": user_id,
            "current_status": state.to_dict(),
            "level_progression": {
                "current_level": state.current_level.value,
                "level_name": self._get_level_name(state.current_level),
                "next_level": min(state.current_level.value + 1, 3),
                "progress_to_next": self._calculate_level_progress(state),
                "level_descriptions": {
                    1: "单一业务类型 - 专注深耕一个领域",
                    2: "双类型组合 - 开始探索协同效应",
                    3: "全生态系统 - 多元化商业闭环",
                },
            },
            "dimension_analysis": {
                "scores": state.dimension_scores.to_dict(),
                "strengths": self._identify_strengths(state),
                "weaknesses": self._identify_weaknesses(state),
                "recommendations": self._generate_recommendations(state),
            },
            "activity_summary": {
                "total_scenarios": state.total_scenarios_completed,
                "active_days": state.active_days,
                "scenarios_by_type": self._get_scenarios_by_type(state),
                "most_used_scenario": self._get_most_used_scenario(state),
            },
            "upgrade_path": self.get_upgrade_suggestion(user_id),
            "achievements": self._check_achievements(state),
            "tips": self._generate_tips(state),
        }

        return report

    def _get_level_name(self, level: FlywheelLevel) -> str:
        names = {
            FlywheelLevel.LEVEL_1: "探索者",
            FlywheelLevel.LEVEL_2: "连接者",
            FlywheelLevel.LEVEL_3: "生态构建者",
        }
        return names.get(level, "未知")

    def _calculate_level_progress(self, state: UserFlywheelState) -> float:
        """Calculate progress percentage to next level (0-100)"""
        current_types = len(state.active_types)

        if state.current_level == FlywheelLevel.LEVEL_1:
            return min(current_types * 50, 100)
        elif state.current_level == FlywheelLevel.LEVEL_2:
            if current_types <= 2:
                return (current_types - 1) * 50
            else:
                return min((current_types - 2) * 33 + 67, 100)
        return 100

    def _identify_strengths(self, state: UserFlywheelState) -> List[str]:
        """Identify strong dimensions"""
        ds = state.dimension_scores
        strengths = []

        if ds.content_quality >= 70:
            strengths.append("内容创作能力强")
        if ds.audience_growth >= 70:
            strengths.append("受众增长势头好")
        if ds.monetization >= 70:
            strengths.append("商业化能力突出")
        if ds.cross_promotion >= 60:
            strengths.append("跨域推广意识强")
        if ds.ecosystem_synergy >= 60:
            strengths.append("生态协同效果好")

        return strengths if strengths else ["持续积累中"]

    def _identify_weaknesses(self, state: UserFlywheelState) -> List[str]:
        """Identify dimensions needing improvement"""
        ds = state.dimension_scores
        weaknesses = []

        if ds.content_quality < 40:
            weaknesses.append("内容质量需提升 - 建议多使用content_calendar场景")
        if ds.audience_growth < 40:
            weaknesses.append("受众增长缓慢 - 保持日常活跃度")
        if ds.monetization < 40:
            weaknesses.append("变现能力待加强 - 尝试digital_product或ecommerce场景")
        if ds.cross_promotion < 30 and len(state.active_types) > 1:
            weaknesses.append("跨域推广不足 - 尝试在不同类型间建立连接")
        if ds.ecosystem_synergy < 30:
            weaknesses.append("生态协同未启动 - 探索更多业务类型组合")

        return weaknesses if weaknesses else ["表现均衡，继续保持！"]

    def _generate_recommendations(self, state: UserFlywheelState) -> List[str]:
        """Generate personalized recommendations"""
        recommendations = []
        type_count = len(state.active_types)

        if type_count == 1:
            current = state.active_types[0]
            if current == BusinessType.CONTENT_CREATOR:
                recommendations.append(
                    "作为内容创作者，建议结合电商运营：\n"
                    "   用内容吸引流量 → 通过电商转化变现\n"
                    "   典型路径：小红书种草 → 淘宝店铺成交"
                )
            elif current == BusinessType.ECOMMERCE:
                recommendations.append(
                    "作为电商运营者，建议结合内容创作：\n"
                    "   用优质内容提升店铺信任度和自然流量\n"
                    "   典型路径：抖音短视频 → 商品详情页优化"
                )

        if state.total_scenarios_completed < 5:
            recommendations.append(
                "建议增加使用频率：每周至少完成3个场景任务\n" "   以快速积累经验和数据"
            )

        if state.active_days < 7:
            recommendations.append(
                "保持连续活跃：连续7天使用可解锁'坚持者'成就\n" "   并获得维度得分加成"
            )

        return recommendations[:3]

    def _get_scenarios_by_type(self, state: UserFlywheelState) -> Dict[str, int]:
        """Count scenario usage by business type"""
        result = {}

        type_scenario_map = {
            BusinessType.CONTENT_CREATOR: ["content_calendar"],
            BusinessType.DIGITAL_PRODUCT: ["digital_product_launch"],
            BusinessType.AI_TOOL_BUILDER: ["feedback_analysis"],
            BusinessType.CONSULTANT: ["consulting_proposal"],
            BusinessType.ECOMMERCE: ["ecommerce_ops"],
            BusinessType.CREATIVE_WORK: ["project_deliverable"],
        }

        for btype, scenarios in type_scenario_map.items():
            count = sum(state.scenario_completion_count.get(s, 0) for s in scenarios)
            if count > 0:
                result[btype.value] = count

        return result

    def _get_most_used_scenario(self, state: UserFlywheelState) -> Optional[str]:
        """Get the most frequently used scenario"""
        if not state.scenario_completion_count:
            return None

        return max(state.scenario_completion_count.items(), key=lambda x: x[1])[0]

    def _check_achievements(self, state: UserFlywheelState) -> List[Dict[str, Any]]:
        """Check achievement unlock status"""
        achievements = []

        if state.total_scenarios_completed >= 1:
            achievements.append(
                {
                    "id": "first_step",
                    "name": "第一步",
                    "description": "完成第一个场景任务",
                    "unlocked_at": state.created_at,
                }
            )

        if state.total_scenarios_completed >= 10:
            achievements.append(
                {
                    "id": "active_user",
                    "name": "活跃用户",
                    "description": "累计完成10个场景任务",
                    "unlocked_at": state.updated_at,
                }
            )

        if len(state.active_types) >= 2:
            achievements.append(
                {
                    "id": "cross_discipline",
                    "name": "跨界探索者",
                    "description": "激活2种以上业务类型",
                    "unlocked_at": state.updated_at,
                }
            )

        if len(state.active_types) >= 3:
            achievements.append(
                {
                    "id": "ecosystem_builder",
                    "name": "生态构建者",
                    "description": "激活3种以上业务类型",
                    "unlocked_at": state.updated_at,
                }
            )

        if state.active_days >= 7:
            achievements.append(
                {
                    "id": "weekly_streak",
                    "name": "周常用户",
                    "description": "连续7天保持活跃",
                    "unlocked_at": state.updated_at,
                }
            )

        if state.dimension_scores.overall_score() >= 80:
            achievements.append(
                {
                    "id": "high_performer",
                    "name": "高绩效者",
                    "description": "飞轮健康度达到80分以上",
                    "unlocked_at": state.updated_at,
                }
            )

        return achievements

    def _generate_tips(self, state: UserFlywheelState) -> List[str]:
        """Generate practical tips"""
        tips = []

        tips.append(
            "💡 飞轮效应：每增加一种业务类型，\n" "   你的综合效率会呈指数级增长！"
        )

        if state.current_level.value < 3:
            tips.append(
                "🎯 下一步目标：激活第{}种业务类型".format(len(state.active_types) + 1)
            )

        tips.append(
            "📈 数据驱动：定期查看你的飞轮报告，\n" "   了解哪些维度需要重点投入"
        )

        return tips

    def get_all_users_summary(self) -> Dict[str, Any]:
        """Get aggregated statistics for all users"""
        total_users = len(self.user_states)

        if total_users == 0:
            return {"total_users": 0, "message": "暂无用户数据"}

        level_distribution = {1: 0, 2: 0, 3: 0}
        avg_health = 0.0
        total_scenarios = 0

        for state in self.user_states.values():
            level_distribution[state.current_level.value] += 1
            avg_health += state.dimension_scores.overall_score()
            total_scenarios += state.total_scenarios_completed

        avg_health = round(avg_health / total_users, 1) if total_users > 0 else 0

        return {
            "total_users": total_users,
            "level_distribution": level_distribution,
            "average_health_score": avg_health,
            "total_scenarios_completed": total_scenarios,
            "most_common_level": max(level_distribution.items(), key=lambda x: x[1])[0],
            "generated_at": datetime.now().isoformat(),
        }


if __name__ == "__main__":
    tracker = FlywheelTracker()

    print("=" * 70)
    print("OPC-Agents 飞轮追踪系统 v1.0")
    print("=" * 70)

    test_user = "demo_user_phase2"

    print(f"\n📊 模拟用户 '{test_user}' 的成长路径:\n")

    actions = [
        ("content_calendar", BusinessType.CONTENT_CREATOR, "规划下周内容日历"),
        ("content_calendar", BusinessType.CONTENT_CREATOR, "写一篇小红书笔记"),
        ("ecommerce_ops", BusinessType.ECOMMERCE, "策划淘宝双十一活动"),
        ("digital_product_launch", BusinessType.DIGITAL_PRODUCT, "发布新课程到Gumroad"),
        ("consulting_proposal", BusinessType.CONSULTANT, "写一份战略咨询提案"),
        ("feedback_analysis", BusinessType.AI_TOOL_BUILDER, "分析App Store用户评论"),
        ("project_deliverable", BusinessType.CREATIVE_WORK, "整理设计作品集"),
    ]

    for i, (scenario, btype, desc) in enumerate(actions, 1):
        state = tracker.record_scenario_completion(test_user, scenario, btype)
        level_name = tracker._get_level_name(state.current_level)
        health = tracker.get_flywheel_health_score(test_user)

        print(f"[{i}] {desc}")
        print(f"    场景: {scenario} | 类型: {btype.value}")
        print(
            f"    等级: Lv.{state.current_level.value} ({level_name}) | 健康: {health}分"
        )
        print(f"    已激活类型: {[bt.display_name for bt in state.active_types]}")
        print()

    print("=" * 70)
    print("📋 完整飞轮报告:")
    print("=" * 70)

    report = tracker.generate_flywheel_report(test_user)

    import json

    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


class FlywheelTrackerDB(FlywheelTracker):
    """
    Database-persisted flywheel tracker (Phase 3)

    Inherits all FlywheelTracker functionality while persisting data to database.
    Backward compatible: degrades to in-memory mode when no db_session is provided.
    """

    def __init__(self, db_session=None):
        super().__init__()
        self.db_session = db_session
        self._db_enabled = db_session is not None

    def _get_db_state(self, user_id: str) -> Optional[Any]:
        """Load user flywheel state from database"""
        if not self._db_enabled or not self.db_session:
            return None

        from db_models.models import FlywheelState as DBFlywheelState

        db_state = (
            self.db_session.query(DBFlywheelState)
            .filter(DBFlywheelState.user_id == user_id)
            .first()
        )
        return db_state

    def _db_state_to_user_flywheel(self, db_state) -> UserFlywheelState:
        """Convert database record to UserFlywheelState object"""
        active_types = []
        for t in db_state.active_types or []:
            try:
                active_types.append(BusinessType(t))
            except ValueError:
                pass

        ds_data = db_state.dimension_scores or {}
        dim_scores = DimensionScore(
            content_quality=ds_data.get("content_quality", 0.0),
            audience_growth=ds_data.get("audience_growth", 0.0),
            monetization=ds_data.get("monetization", 0.0),
            cross_promotion=ds_data.get("cross_promotion", 0.0),
            ecosystem_synergy=ds_data.get("ecosystem_synergy", 0.0),
        )

        state = UserFlywheelState(
            user_id=db_state.user_id,
            current_level=FlywheelLevel(db_state.current_level),
            active_types=active_types,
            dimension_scores=dim_scores,
            scenario_completion_count={},
            total_scenarios_completed=db_state.total_scenarios_completed or 0,
            active_days=db_state.active_days or 0,
            achievements=list(db_state.achievements) if db_state.achievements else [],
        )
        return state

    def _save_to_db(self, state: UserFlywheelState):
        """Save flywheel state to database"""
        if not self._db_enabled or not self.db_session:
            return

        from db_models.models import FlywheelState as DBFlywheelState

        db_state = (
            self.db_session.query(DBFlywheelState)
            .filter(DBFlywheelState.user_id == state.user_id)
            .first()
        )

        if not db_state:
            db_state = DBFlywheelState(user_id=state.user_id)
            self.db_session.add(db_state)

        db_state.current_level = state.current_level.value
        db_state.active_types = [t.value for t in state.active_types]
        db_state.health_score = round(state.dimension_scores.overall_score(), 1)
        db_state.dimension_scores = {
            "content_quality": state.dimension_scores.content_quality,
            "audience_growth": state.dimension_scores.audience_growth,
            "monetization": state.dimension_scores.monetization,
            "cross_promotion": state.dimension_scores.cross_promotion,
            "ecosystem_synergy": state.dimension_scores.ecosystem_synergy,
        }
        db_state.total_scenarios_completed = state.total_scenarios_completed
        db_state.active_days = state.active_days
        db_state.achievements = state.achievements
        db_state.updated_at = datetime.now(timezone.utc)

        try:
            self.db_session.commit()
        except Exception:
            self.db_session.rollback()
            raise

    def get_or_create_state(self, user_id: str) -> UserFlywheelState:
        """Get or create user flywheel state (load from DB first)"""
        db_state = self._get_db_state(user_id)
        if db_state:
            state = self._db_state_to_user_flywheel(db_state)
            self.user_states[user_id] = state
            return state
        return super().get_or_create_state(user_id)

    def record_scenario_completion(
        self, user_id: str, scenario_id: str, business_type: BusinessType
    ) -> UserFlywheelState:
        """Record scenario completion event (auto-persist to database)"""
        state = super().record_scenario_completion(user_id, scenario_id, business_type)
        self._save_to_db(state)
        return state

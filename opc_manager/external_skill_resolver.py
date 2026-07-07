"""外部技能解析器 (ExternalSkillResolver) - 外部技能降级查找

[P2-15] Step 5: 从 StrategistBrain._fallback_to_external 抽出的独立职责，
负责在意图识别为 UNKNOWN 时，依次查询用户偏好和外部技能市场，
找到匹配的外部技能作为 EXTENDED_SKILL 返回。

设计要点:
- 维护自身的 _cached_user_profile / _cached_marketplace / _cache_timestamp 缓存
  （TTL=_CACHE_TTL=300s），避免每次调用都重新加载
- 任何异常都降级返回 None，不影响主流程
- 作为 IntentUnderstandingService 的 external_fallback 回调注入
"""

from typing import Any, Dict, Optional
import logging
import time

logger = logging.getLogger(__name__)

_CACHE_TTL = 300.0  # 5 minutes cache expiry


class ExternalSkillResolver:
    """外部技能解析器 — 用户偏好 + 技能市场降级查找。"""

    def __init__(self) -> None:
        self._cached_user_profile: Any = None
        self._cached_marketplace: Any = None
        self._cache_timestamp: float = 0.0

    def resolve(self, user_input: str, goal: str) -> Optional[Dict[str, Any]]:
        """查找匹配的外部技能。

        依次查询:
        1. 用户偏好 (UserProfile.get_preference)
        2. 外部技能市场 (ExternalSkillMarketplace.search_skills)

        Args:
            user_input: 用户原始输入
            goal: 提取出的目标

        Returns:
            包含 goal + context(skill_id/source/...) 的字典，未找到时返回 None
        """
        if time.time() - self._cache_timestamp > _CACHE_TTL:
            self._cached_user_profile = None
            self._cached_marketplace = None
            self._cache_timestamp = time.time()

        result = self._lookup_user_preference(user_input, goal)
        if result is not None:
            return result

        result = self._lookup_marketplace(user_input, goal)
        if result is not None:
            return result

        return None

    def _lookup_user_preference(
        self, user_input: str, goal: str
    ) -> Optional[Dict[str, Any]]:
        try:
            from opc_manager.user_profile import UserProfile

            if self._cached_user_profile is None:
                self._cached_user_profile = UserProfile()
            preferred = self._cached_user_profile.get_preference(
                f"preferred_skill:{user_input[:20]}"
            )
            if preferred:
                return {
                    "goal": goal,
                    "context": {
                        "skill_id": preferred,
                        "source": "user_preference",
                    },
                }
        except Exception as e:
            logger.debug("查询用户偏好失败: %s", e)
        return None

    def _lookup_marketplace(
        self, user_input: str, goal: str
    ) -> Optional[Dict[str, Any]]:
        try:
            from opc_manager.skill_marketplace import ExternalSkillMarketplace

            if self._cached_marketplace is None:
                self._cached_marketplace = ExternalSkillMarketplace()
            search_result = self._cached_marketplace.search_skills(user_input)
            if search_result.get("success") and search_result.get("results"):
                best_match = search_result["results"][0]
                return {
                    "goal": goal,
                    "context": {
                        "skill_id": best_match.get("skill_id", ""),
                        "source": "marketplace",
                        "trust_level": best_match.get("trust_level", "unverified"),
                    },
                }
        except Exception as e:
            logger.debug("搜索外部技能市场失败: %s", e)
        return None

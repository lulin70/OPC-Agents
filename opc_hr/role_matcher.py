#!/usr/bin/env python3

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class MatchResult:
    agent_name: str
    department: str
    confidence: float
    match_strategy: str
    reasons: List[str] = field(default_factory=list)
    matched_skills: List[str] = field(default_factory=list)


class RoleMatcher:

    def __init__(self, hr_enhancement=None, context_manager=None):
        self.hr = hr_enhancement
        self.ctx = context_manager

    def match(self, task_description: str, required_skills: List[str] = None,
              top_k: int = 3) -> List[MatchResult]:
        agents = self._get_all_agents()
        if not agents:
            return []

        results = []
        for agent in agents:
            history_score = self._history_score(agent.get("agent_name", ""), task_description)
            skill_score = self._skill_score(agent.get("skills", []), required_skills or [])
            keyword_score = self._keyword_score(task_description, agent)

            total = history_score * 0.3 + skill_score * 0.4 + keyword_score * 0.3
            strategy = "skill" if skill_score >= keyword_score and skill_score >= history_score else \
                       "history" if history_score >= keyword_score else "keyword"
            reasons = []
            if history_score > 0.3:
                reasons.append(f"historical performance: {history_score:.2f}")
            if skill_score > 0.3:
                reasons.append(f"skill match: {skill_score:.2f}")
            if keyword_score > 0.3:
                reasons.append(f"keyword match: {keyword_score:.2f}")

            results.append(MatchResult(
                agent_name=agent.get("agent_name", ""),
                department=agent.get("department", ""),
                confidence=total,
                match_strategy=strategy,
                reasons=reasons,
                matched_skills=self._get_matched_skills(agent.get("skills", []), required_skills or [])
            ))

        results.sort(key=lambda x: -x.confidence)
        return results[:top_k]

    def _get_all_agents(self) -> List[Dict[str, Any]]:
        if not self.hr:
            return []
        agents = []
        try:
            all_agents = self.hr.get_all_agents()
            if isinstance(all_agents, dict):
                agents = list(all_agents.values())
            elif isinstance(all_agents, list):
                agents = all_agents
        except Exception:
            pass
        return agents

    def _history_score(self, agent_name: str, task_description: str) -> float:
        if not self.ctx:
            return 0.0
        try:
            experiences = self.ctx.find_similar_experiences(task_description, limit=5)
            if not experiences:
                return 0.0
            relevant = [e for e in experiences if e.success]
            return min(len(relevant) / max(len(experiences), 1), 1.0)
        except Exception:
            return 0.0

    def _skill_score(self, agent_skills: List, required_skills: List) -> float:
        if not required_skills or not agent_skills:
            return 0.5 if not required_skills else 0.0
        agent_skills_lower = [str(s).lower() for s in agent_skills]
        required_lower = [str(s).lower() for s in required_skills]
        matched = sum(1 for r in required_lower if any(r in a for a in agent_skills_lower))
        return matched / len(required_lower)

    def _keyword_score(self, task_description: str, agent_info: Dict) -> float:
        if not task_description:
            return 0.0
        keywords = re.findall(r'[\w]{2,}', task_description.lower())
        if not keywords:
            return 0.0
        agent_text = " ".join([
            str(agent_info.get("agent_name", "")),
            str(agent_info.get("department", "")),
            str(agent_info.get("description", "")),
            " ".join(str(s) for s in agent_info.get("skills", []))
        ]).lower()
        matched = sum(1 for kw in keywords if kw in agent_text)
        return min(matched / max(len(keywords), 1) * 2, 1.0)

    def _get_matched_skills(self, agent_skills: List, required_skills: List) -> List[str]:
        if not required_skills or not agent_skills:
            return []
        agent_lower = [str(s).lower() for s in agent_skills]
        return [str(r) for r in required_skills
                if any(str(r).lower() in a for a in agent_lower)]

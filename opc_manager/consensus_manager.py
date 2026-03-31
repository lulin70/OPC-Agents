#!/usr/bin/env python3

import uuid
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ConsensusStatus(Enum):
    PENDING = "pending"
    COLLECTING = "collecting"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ConsensusOpinion:
    participant_id: str
    participant_name: str
    opinion: str
    score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ConsensusSession:
    session_id: str
    topic: str
    participants: List[Dict[str, str]]
    context: Dict[str, Any]
    status: ConsensusStatus = ConsensusStatus.PENDING
    opinions: List[ConsensusOpinion] = field(default_factory=list)
    synthesis: Dict[str, Any] = field(default_factory=dict)
    consensus_score: float = 0.0
    threshold: float = 0.7
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


class ConsensusManager:

    def __init__(self, communication_manager=None, model_manager=None):
        self.communication_manager = communication_manager
        self.model_manager = model_manager
        self.sessions: Dict[str, ConsensusSession] = {}

    def initiate_consensus(self, topic: str, participants: List[Dict[str, str]],
                           context: Dict[str, Any] = None,
                           threshold: float = 0.7) -> ConsensusSession:
        session_id = f"consensus_{uuid.uuid4().hex[:8]}"
        session = ConsensusSession(
            session_id=session_id,
            topic=topic,
            participants=participants,
            context=context or {},
            threshold=threshold,
            status=ConsensusStatus.PENDING
        )
        self.sessions[session_id] = session
        return session

    def add_opinion(self, session_id: str, participant_id: str,
                    participant_name: str, opinion: str, score: float = 0.0) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False
        session.opinions.append(ConsensusOpinion(
            participant_id=participant_id,
            participant_name=participant_name,
            opinion=opinion,
            score=score
        ))
        session.status = ConsensusStatus.COLLECTING
        return True

    def collect_opinions(self, session_id: str) -> List[Dict[str, Any]]:
        session = self.sessions.get(session_id)
        if not session:
            return []
        return [
            {"participant_id": o.participant_id, "participant_name": o.participant_name,
             "opinion": o.opinion, "score": o.score, "timestamp": o.timestamp}
            for o in session.opinions
        ]

    def synthesize(self, session_id: str) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "session not found"}
        if len(session.opinions) == 0:
            return {"error": "no opinions collected"}

        session.status = ConsensusStatus.SYNTHESIZING

        total_score = sum(o.score for o in session.opinions)
        avg_score = total_score / len(session.opinions) if session.opinions else 0
        session.consensus_score = avg_score

        all_opinions = [o.opinion for o in session.opinions]
        consensus_reached = avg_score >= session.threshold

        agreement_count = 0
        for o in session.opinions:
            if o.score >= session.threshold:
                agreement_count += 1
        agreement_ratio = agreement_count / len(session.opinions) if session.opinions else 0

        synthesis = {
            "session_id": session_id,
            "topic": session.topic,
            "participant_count": len(session.participants),
            "opinion_count": len(session.opinions),
            "average_score": round(avg_score, 2),
            "agreement_ratio": round(agreement_ratio, 2),
            "consensus_reached": consensus_reached,
            "recommendation": "通过" if consensus_reached else "需要进一步讨论",
            "opinions_summary": all_opinions[:3],
            "divergent_points": self._find_divergences(session.opinions) if not consensus_reached else []
        }

        session.synthesis = synthesis
        session.status = ConsensusStatus.COMPLETED
        session.completed_at = datetime.now().isoformat()
        return synthesis

    def get_consensus_score(self, session_id: str) -> float:
        session = self.sessions.get(session_id)
        if not session:
            return 0.0
        return session.consensus_score

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self.sessions.get(session_id)
        if not session:
            return None
        return {
            "session_id": session.session_id,
            "topic": session.topic,
            "participants": session.participants,
            "status": session.status.value,
            "opinion_count": len(session.opinions),
            "consensus_score": session.consensus_score,
            "synthesis": session.synthesis,
            "created_at": session.created_at,
            "completed_at": session.completed_at
        }

    def _find_divergences(self, opinions: List[ConsensusOpinion]) -> List[str]:
        scores = [o.score for o in opinions]
        if len(scores) < 2:
            return []
        avg = sum(scores) / len(scores)
        divergences = []
        for o in opinions:
            if abs(o.score - avg) > 0.3:
                divergences.append(f"{o.participant_name}的评分({o.score})与平均分({round(avg, 2)})偏差较大")
        return divergences[:3]

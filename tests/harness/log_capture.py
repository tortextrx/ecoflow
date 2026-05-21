from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TurnLog:
    index: int
    user_input: str
    response_state: str
    response_reply: str
    trace_id: str
    ts_utc: str
    expected_state: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseTrace:
    case_id: str
    session_id: str
    mode: str
    turns: List[TurnLog] = field(default_factory=list)
    cleanup: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_turn(
        self,
        index: int,
        user_input: str,
        response: Dict[str, Any],
        trace_id: str,
        expected_state: Optional[str] = None,
    ) -> None:
        self.turns.append(
            TurnLog(
                index=index,
                user_input=user_input,
                response_state=str(response.get("state", "")),
                response_reply=str(response.get("reply", "")),
                trace_id=trace_id,
                ts_utc=now_utc(),
                expected_state=expected_state,
                raw_response=response,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "session_id": self.session_id,
            "mode": self.mode,
            "turns": [
                {
                    "index": t.index,
                    "user_input": t.user_input,
                    "response_state": t.response_state,
                    "response_reply": t.response_reply,
                    "trace_id": t.trace_id,
                    "ts_utc": t.ts_utc,
                    "expected_state": t.expected_state,
                    "raw_response": t.raw_response,
                }
                for t in self.turns
            ],
            "cleanup": self.cleanup,
            "metadata": self.metadata,
        }


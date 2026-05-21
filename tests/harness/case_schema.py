from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


VALID_MODES = {"semireal", "real_readonly", "real_mutating", "any"}
VALID_OUTCOMES = {"expected_pass", "expected_fail_known", "skip"}


@dataclass
class TurnSpec:
    user: str
    expect_state: Optional[str] = None
    variant: bool = False

    @classmethod
    def from_raw(cls, raw: Any) -> "TurnSpec":
        if isinstance(raw, str):
            return cls(user=raw)
        if not isinstance(raw, dict):
            raise ValueError(f"Turn inválido: {raw}")
        return cls(
            user=str(raw.get("user", "")).strip(),
            expect_state=(str(raw["expect_state"]).strip() if raw.get("expect_state") else None),
            variant=bool(raw.get("variant", False)),
        )


@dataclass
class CleanupSpec:
    action: Optional[str] = None
    target: Optional[str] = None
    target_source: Optional[str] = None
    confirm_message: str = "CONFIRMO"
    verify_prompt: Optional[str] = None
    verify_absent_markers: List[str] = field(default_factory=list)
    verify_present_markers: List[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Any) -> "CleanupSpec":
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise ValueError("cleanup debe ser un objeto")
        return cls(
            action=(str(raw.get("action")).strip() if raw.get("action") else None),
            target=(str(raw.get("target")).strip() if raw.get("target") else None),
            target_source=(str(raw.get("target_source")).strip() if raw.get("target_source") else None),
            confirm_message=str(raw.get("confirm_message", "CONFIRMO")),
            verify_prompt=(str(raw.get("verify_prompt")).strip() if raw.get("verify_prompt") else None),
            verify_absent_markers=[str(x) for x in raw.get("verify_absent_markers", [])],
            verify_present_markers=[str(x) for x in raw.get("verify_present_markers", [])],
        )


@dataclass
class CaseSpec:
    id: str
    domain: str
    category: str
    description: str
    turns: List[TurnSpec]
    mode: str = "any"
    expected_outcome: str = "expected_pass"
    tags: List[str] = field(default_factory=list)

    expected_intent: Optional[str] = None
    expected_flow: Optional[str] = None
    expected_active_object: Optional[Dict[str, Any]] = None
    expected_tool: List[str] = field(default_factory=list)
    expected_fields: Dict[str, Any] = field(default_factory=dict)
    expected_block: Optional[bool] = None
    expected_verification: Dict[str, Any] = field(default_factory=dict)
    expected_log_markers: List[str] = field(default_factory=list)
    cleanup: CleanupSpec = field(default_factory=CleanupSpec)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "CaseSpec":
        if not isinstance(raw, dict):
            raise ValueError("Cada caso debe ser un objeto")

        turns_raw = raw.get("turns") or []
        turns = [TurnSpec.from_raw(t) for t in turns_raw]
        if not turns:
            raise ValueError(f"Caso {raw.get('id')} sin turns")

        mode = str(raw.get("mode", "any")).strip().lower()
        if mode not in VALID_MODES:
            raise ValueError(f"mode inválido en {raw.get('id')}: {mode}")

        expected_outcome = str(raw.get("expected_outcome", "expected_pass")).strip().lower()
        if expected_outcome not in VALID_OUTCOMES:
            raise ValueError(f"expected_outcome inválido en {raw.get('id')}: {expected_outcome}")

        return cls(
            id=str(raw["id"]).strip(),
            domain=str(raw["domain"]).strip().lower(),
            category=str(raw["category"]).strip().lower(),
            description=str(raw.get("description", "")).strip(),
            turns=turns,
            mode=mode,
            expected_outcome=expected_outcome,
            tags=[str(x).strip().lower() for x in raw.get("tags", [])],
            expected_intent=(str(raw.get("expected_intent")).strip() if raw.get("expected_intent") else None),
            expected_flow=(str(raw.get("expected_flow")).strip().lower() if raw.get("expected_flow") else None),
            expected_active_object=raw.get("expected_active_object") or None,
            expected_tool=[str(x) for x in raw.get("expected_tool", [])],
            expected_fields=raw.get("expected_fields") or {},
            expected_block=raw.get("expected_block"),
            expected_verification=raw.get("expected_verification") or {},
            expected_log_markers=[str(x) for x in raw.get("expected_log_markers", [])],
            cleanup=CleanupSpec.from_raw(raw.get("cleanup")),
        )

    def enabled_for_mode(self, suite_mode: str) -> bool:
        if self.mode == "any":
            return True
        return self.mode == suite_mode


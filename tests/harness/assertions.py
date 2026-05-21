from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .case_schema import CaseSpec
from .log_capture import CaseTrace


def infer_flow_from_state(state: str) -> str | None:
    s = (state or "").upper()
    if "ENTITY" in s:
        return "entity"
    if "SERVICE" in s:
        return "service"
    if "CONTRAT" in s:
        return "contract"
    if "ARTIC" in s:
        return "article"
    if "FACT" in s:
        return "facturacion"
    if "DISAMBIGUATION" in s:
        return "disambiguation"
    return None


def _contains_any(text: str, tokens: List[str]) -> bool:
    tl = (text or "").lower()
    return any((t or "").lower() in tl for t in tokens)


def evaluate_case(case: CaseSpec, trace: CaseTrace) -> Tuple[bool, List[str], List[str]]:
    errors: List[str] = []
    markers: List[str] = []

    if not trace.turns:
        return False, ["Caso sin turnos ejecutados"], markers

    final = trace.turns[-1]
    markers.append(f"final_state={final.response_state}")

    if case.expected_flow:
        got_flow = infer_flow_from_state(final.response_state)
        if got_flow != case.expected_flow:
            errors.append(f"expected_flow={case.expected_flow} got={got_flow}")

    if case.expected_block is True:
        if not _contains_any(final.response_reply, ["bloque", "no permitido", "falta", "valida", "error"]):
            errors.append("Se esperaba bloqueo y no hay evidencia textual")

    if case.expected_fields:
        must_include = [str(x) for x in case.expected_fields.get("must_include", [])]
        if must_include and not _contains_any(final.response_reply, must_include):
            errors.append("No aparecen campos esperados en respuesta final")

    if case.expected_log_markers:
        haystack = "\n".join(
            [f"state={t.response_state} reply={t.response_reply}" for t in trace.turns]
        ).lower()
        for mk in case.expected_log_markers:
            if mk.lower() not in haystack:
                errors.append(f"Falta expected_log_marker: {mk}")

    passed = len(errors) == 0
    return passed, errors, markers


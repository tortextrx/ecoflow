from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_artifact_dir(run_id: str, root: str = "artifacts") -> Path:
    p = Path(root) / run_id
    p.mkdir(parents=True, exist_ok=True)
    (p / "cases").mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def build_coverage_manifest(cases: List[Any]) -> Dict[str, Any]:
    by_domain = Counter()
    by_category = Counter()
    by_mode = Counter()
    by_outcome = Counter()

    for c in cases:
        by_domain[c.domain] += 1
        by_category[c.category] += 1
        by_mode[c.mode] += 1
        by_outcome[c.expected_outcome] += 1

    return {
        "generated_at_utc": now_utc(),
        "total_cases_loaded": len(cases),
        "by_domain": dict(by_domain),
        "by_category": dict(by_category),
        "by_mode": dict(by_mode),
        "by_expected_outcome": dict(by_outcome),
    }


def build_summary(run_meta: Dict[str, Any], case_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_status = Counter(r["status"] for r in case_results)

    cleanup = {
        "mutating_cases": 0,
        "cleanup_executed": 0,
        "cleanup_success": 0,
        "cleanup_verified": 0,
        "cleanup_failed_or_unverified": 0,
    }

    for r in case_results:
        c = r.get("cleanup") or {}
        if c.get("required"):
            cleanup["mutating_cases"] += 1
        if c.get("executed"):
            cleanup["cleanup_executed"] += 1
        if c.get("success"):
            cleanup["cleanup_success"] += 1
        if c.get("verified"):
            cleanup["cleanup_verified"] += 1
        if c.get("required") and (not c.get("not_applicable")) and (not c.get("success") or not c.get("verified")):
            cleanup["cleanup_failed_or_unverified"] += 1

    hard_fail_statuses = {
        "FUNCTIONAL_FAIL",
        "UNEXPECTED_PASS",
        "CLEANUP_FAIL",
        "INFRA_RUNTIME_FAIL",
        "INFRA_PREFLIGHT_FAIL",
    }
    hard_fails = [
        r for r in case_results if r["status"] in hard_fail_statuses
    ]

    return {
        "run_meta": run_meta,
        "counts": dict(by_status),
        "cleanup": cleanup,
        "hard_fail_count": len(hard_fails),
        "hard_fails": [{"id": x["id"], "status": x["status"], "errors": x.get("errors", [])} for x in hard_fails],
        "generated_at_utc": now_utc(),
    }


def build_failures_markdown(summary: Dict[str, Any]) -> str:
    lines = ["# Harness Failures", ""]
    hard_fails = summary.get("hard_fails", [])
    if not hard_fails:
        lines.append("No hay hard fails.")
        return "\n".join(lines)

    for item in hard_fails:
        lines.append(f"## {item.get('id')} [{item.get('status')}]")
        errs = item.get("errors") or []
        for e in errs:
            lines.append(f"- {e}")
        lines.append("")
    return "\n".join(lines)


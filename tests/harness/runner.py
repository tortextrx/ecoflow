from __future__ import annotations

import asyncio
import hashlib
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
import yaml

from .assertions import evaluate_case
from .case_schema import CaseSpec
from .dataset_index import build_entity_fixtures, build_fixture_context
from .dataset_loader import load_demo_datasets
from .log_capture import CaseTrace
from .preflight import normalize_internal_base_url, run_internal_backend_preflight
from .reporting import (
    build_coverage_manifest,
    build_failures_markdown,
    build_summary,
    ensure_artifact_dir,
    write_json,
    write_text,
)
from .variant_generator import VariantGenerator


@dataclass
class HarnessConfig:
    base_url: str = "http://127.0.0.1:18080"
    suite_mode: str = "semireal"  # semireal | real_readonly | real_mutating
    seed: int = 20260326
    timeout: float = 45.0
    artifacts_root: str = "artifacts"
    header_test_mode: str = "raw"
    endpoint_mode: str = "default"  # default | internal_backend
    require_explicit_base_url: bool = False
    preflight_required: bool = False


class HarnessRunner:
    CHAT_PATH = "/api/ecoflow/chat"

    DEMO_DATASET_PATHS = {
        "clientes": "CLIENTES_DEMO.csv",
        "proveedores": "PROVEEDORES_DEMO.csv",
        "acreedores": "ACREEDORES_DEMO.csv",
        "personal_laboral": "PERSONAL_LABORAL_DEMO.csv",
        "preentidades": "PREENTIDADES_DEMO.csv",
        "articulos": "ARTICULOS_DEMO.csv",
        "servicios": "SERVICIOS_DEMO.csv",
        "contratos": "CONTRATOS_DEMO.csv",
        "facturacion": "FACTURACION_COMPRAS_Y_GASTOS.csv",
    }

    def __init__(self, config: HarnessConfig):
        self.cfg = config

    def _chat_url(self) -> str:
        return f"{self.cfg.base_url.rstrip('/')}{self.CHAT_PATH}"

    def _build_run_id(self) -> str:
        ts = time.strftime("%Y%m%d_%H%M%S")
        return f"harness_{self.cfg.suite_mode}_{ts}_{uuid.uuid4().hex[:6]}"

    def _case_seed(self, case_id: str) -> int:
        h = hashlib.sha256(f"{self.cfg.seed}:{case_id}".encode("utf-8")).hexdigest()
        return int(h[:8], 16)

    def _load_cases(self, case_files: List[str]) -> List[CaseSpec]:
        out: List[CaseSpec] = []
        for fp in case_files:
            path = Path(fp)
            if not path.exists():
                raise FileNotFoundError(f"Case file no encontrado: {fp}")

            content = yaml.safe_load(path.read_text(encoding="utf-8"))
            raw_cases = []
            if isinstance(content, list):
                raw_cases = content
            elif isinstance(content, dict):
                raw_cases = content.get("cases", [])
            else:
                raise ValueError(f"Formato inválido en {fp}")

            for rc in raw_cases:
                out.append(CaseSpec.from_dict(rc))
        return out

    def _resolve_token(self, token: str, fixtures: Dict[str, Any], runtime: Dict[str, Any]) -> str:
        if token.startswith("runtime."):
            key = token.split(".", 1)[1]
            return str(runtime.get(key, ""))
        return str(fixtures.get(token, ""))

    def _render_text(self, text: str, fixtures: Dict[str, Any], runtime: Dict[str, Any]) -> str:
        pattern = re.compile(r"{{\s*([a-zA-Z0-9_\.]+)\s*}}")

        def repl(m: re.Match[str]) -> str:
            return self._resolve_token(m.group(1), fixtures, runtime)

        return pattern.sub(repl, text)

    async def _post_chat(
        self,
        client: httpx.AsyncClient,
        session_id: str,
        message: str,
        trace_id: str,
    ) -> Dict[str, Any]:
        headers = {
            "x-trace-id": trace_id,
            "x-ecoflow-test-mode": self.cfg.header_test_mode,
        }
        try:
            r = await client.post(
                self._chat_url(),
                data={"session_id": session_id, "message": message},
                headers=headers,
                timeout=self.cfg.timeout,
            )
            if r.status_code != 200:
                return {"reply": f"HTTP_{r.status_code}", "state": "error", "_http": r.status_code}
            try:
                return r.json()
            except Exception:
                return {"reply": r.text, "state": "error_json"}
        except Exception as exc:
            return {"reply": f"CONNECT_ERROR: {exc}", "state": "infra_error"}

    def _extract_first_int(self, text: str) -> str | None:
        m = re.search(r"\b(\d{2,10})\b", text or "")
        return m.group(1) if m else None

    async def _run_cleanup(
        self,
        client: httpx.AsyncClient,
        case: CaseSpec,
        trace: CaseTrace,
        fixtures: Dict[str, Any],
        runtime: Dict[str, Any],
        runtime_had_infra: bool,
    ) -> Dict[str, Any]:
        cp = case.cleanup
        result = {
            "required": self.cfg.suite_mode == "real_mutating",
            "executed": False,
            "success": False,
            "verified": False,
            "not_applicable": False,
            "verification_status": "not_attempted",
            "details": [],
        }

        if self.cfg.suite_mode != "real_mutating":
            result["verification_status"] = "not_required"
            return result

        if runtime_had_infra:
            result["not_applicable"] = True
            result["verification_status"] = "not_applicable_infra_runtime"
            result["details"].append("Cleanup no aplicable: caso con fallo de infraestructura en ejecución")
            return result

        if not cp.action:
            result["verification_status"] = "missing_cleanup_spec"
            result["details"].append("Caso mutante sin cleanup definido")
            return result

        target = None
        if cp.target_source == "last_numeric_id":
            target = runtime.get("last_numeric_id")
        elif cp.target:
            target = self._render_text(cp.target, fixtures, runtime)

        if not target:
            result["not_applicable"] = True
            result["verification_status"] = "not_applicable_no_creation_confirmed"
            result["details"].append("Cleanup no aplicable: no hubo creación/ID confirmado")
            return result

        action_map = {
            "delete_entity": f"borra la entidad {target}",
            "delete_service": f"borra el servicio {target}",
            "delete_contract": f"borra el contrato {target}",
            "delete_factura": f"borra la factura {target}",
        }
        cmd = action_map.get(cp.action)
        if not cmd:
            result["verification_status"] = "unsupported_action"
            result["details"].append(f"Cleanup action no soportada: {cp.action}")
            return result

        tid1 = f"cleanup-{uuid.uuid4().hex[:8]}"
        tid2 = f"cleanup-{uuid.uuid4().hex[:8]}"
        r1 = await self._post_chat(client, trace.session_id, cmd, tid1)
        r2 = await self._post_chat(client, trace.session_id, cp.confirm_message, tid2)

        result["executed"] = True
        text = f"{r1.get('reply', '')} {r2.get('reply', '')}".lower()
        result["success"] = any(k in text for k in ["elimin", "borr", "ok", "complet"])
        result["details"].append({"cmd": cmd, "r1": r1, "r2": r2})

        verify_prompt = cp.verify_prompt
        if not verify_prompt:
            default_verify = {
                "delete_entity": f"consulta el cliente {target}",
                "delete_service": f"consulta el servicio {target}",
                "delete_contract": f"consulta contrato {target}",
                "delete_factura": f"consulta factura {target}",
            }
            verify_prompt = default_verify.get(cp.action)

        if not verify_prompt:
            result["verification_status"] = "not_verifiable"
            return result

        verify_prompt = self._render_text(verify_prompt, fixtures, runtime)
        tv = f"cleanup-verify-{uuid.uuid4().hex[:8]}"
        rv = await self._post_chat(client, trace.session_id, verify_prompt, tv)
        vtext = (rv.get("reply") or "").lower()

        absent = [x.lower() for x in cp.verify_absent_markers]
        present = [x.lower() for x in cp.verify_present_markers]

        cond_absent = all(a not in vtext for a in absent) if absent else True
        cond_present = any(p in vtext for p in present) if present else True

        if not present and not absent:
            cond_present = any(k in vtext for k in ["no ", "no existe", "no encontrado", "vacío", "vacio"])

        result["verified"] = bool(cond_absent and cond_present)
        result["verification_status"] = "verified" if result["verified"] else "verify_failed"
        result["details"].append({"verify_prompt": verify_prompt, "verify_response": rv})
        return result

    async def _execute_case(
        self,
        client: httpx.AsyncClient,
        case: CaseSpec,
        run_id: str,
        fixtures: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], CaseTrace]:
        if case.expected_outcome == "skip":
            trace = CaseTrace(case_id=case.id, session_id="skip", mode=self.cfg.suite_mode)
            return (
                {
                    "id": case.id,
                    "domain": case.domain,
                    "category": case.category,
                    "status": "SKIP",
                    "errors": ["Caso marcado como skip"],
                    "cleanup": {"required": False, "executed": False, "success": False, "verified": False},
                },
                trace,
            )

        if not case.enabled_for_mode(self.cfg.suite_mode):
            trace = CaseTrace(case_id=case.id, session_id="mode_skip", mode=self.cfg.suite_mode)
            return (
                {
                    "id": case.id,
                    "domain": case.domain,
                    "category": case.category,
                    "status": "SKIP_MODE",
                    "errors": [f"No aplica al modo {self.cfg.suite_mode}"],
                    "cleanup": {"required": False, "executed": False, "success": False, "verified": False},
                },
                trace,
            )

        session_id = f"h-{run_id[-6:]}-{case.id[:18]}-{uuid.uuid4().hex[:4]}"
        trace = CaseTrace(case_id=case.id, session_id=session_id, mode=self.cfg.suite_mode)

        runtime: Dict[str, Any] = {}
        seed = self._case_seed(case.id)
        runtime["case_seed"] = seed
        runtime["last_numeric_id"] = None
        vg = VariantGenerator(seed)

        for i, turn in enumerate(case.turns, start=1):
            user_text = self._render_text(turn.user, fixtures, runtime)
            if turn.variant:
                candidates = vg.generate(user_text, max_variants=4)
                if candidates:
                    user_text = candidates[1] if len(candidates) > 1 else candidates[0]

            trace_id = f"{case.id}-{uuid.uuid4().hex[:8]}"
            resp = await self._post_chat(client, session_id, user_text, trace_id)
            trace.add_turn(i, user_text, resp, trace_id, expected_state=turn.expect_state)

            eid = self._extract_first_int(resp.get("reply", ""))
            if eid:
                runtime["last_numeric_id"] = eid

        runtime_had_infra = any((t.response_state or "") == "infra_error" for t in trace.turns)

        cleanup = await self._run_cleanup(client, case, trace, fixtures, runtime, runtime_had_infra)
        trace.cleanup = cleanup

        if runtime_had_infra:
            final_state = trace.turns[-1].response_state if trace.turns else "infra_error"
            markers = [f"final_state={final_state}", "classification=infra_runtime_fail"]
            errors = ["infra_runtime_fail: fallo de transporte/conectividad durante ejecución del caso"]
            status = "INFRA_RUNTIME_FAIL"
        else:
            passed, errors, markers = evaluate_case(case, trace)
            status = "PASS" if passed else "FUNCTIONAL_FAIL"
            if case.expected_outcome == "expected_fail_known":
                status = "KNOWN_FAIL" if not passed else "UNEXPECTED_PASS"

        trace.metadata["markers"] = markers
        trace.metadata["case_seed"] = seed

        if self.cfg.suite_mode == "real_mutating" and cleanup.get("required"):
            if cleanup.get("not_applicable"):
                if status in {"PASS", "KNOWN_FAIL"}:
                    status = "CLEANUP_NOT_APPLICABLE"
                    errors = errors + ["cleanup_not_applicable: no hubo creación confirmada para cleanup"]
            elif (not cleanup.get("success") or not cleanup.get("verified")):
                if status in {"PASS", "KNOWN_FAIL"}:
                    status = "CLEANUP_FAIL"
                    errors = errors + ["Cleanup no verificado/sin éxito en real_mutating"]

        result = {
            "id": case.id,
            "domain": case.domain,
            "category": case.category,
            "status": status,
            "errors": errors,
            "cleanup": cleanup,
        }
        return result, trace

    async def run(self, case_files: List[str]) -> Tuple[int, str]:
        run_id = self._build_run_id()
        artifact_dir = ensure_artifact_dir(run_id, self.cfg.artifacts_root)

        # 1) datasets raw + snapshot
        datasets, snapshots = load_demo_datasets(self.DEMO_DATASET_PATHS)
        write_json(artifact_dir / "dataset_snapshot.json", snapshots)

        # 2) fixtures canónicos
        entity_fixtures = build_entity_fixtures(datasets)
        fixtures = build_fixture_context(datasets, entity_fixtures, self.cfg.seed)
        write_json(artifact_dir / "fixtures_canonical_entities.json", entity_fixtures)
        write_json(artifact_dir / "fixtures_context.json", fixtures)

        # 3) casos derivados
        cases = self._load_cases(case_files)
        coverage = build_coverage_manifest(cases)
        write_json(artifact_dir / "coverage_manifest.json", coverage)

        run_meta = {
            "run_id": run_id,
            "suite_mode": self.cfg.suite_mode,
            "base_url": self.cfg.base_url,
            "endpoint_mode": self.cfg.endpoint_mode,
            "preflight_required": self.cfg.preflight_required,
            "run_seed": self.cfg.seed,
            "case_files": case_files,
        }

        if self.cfg.endpoint_mode == "internal_backend":
            ok_base, normalized_base, base_error = normalize_internal_base_url(
                self.cfg.base_url,
                require_explicit=self.cfg.require_explicit_base_url,
            )
            if not ok_base:
                preflight = {
                    "endpoint_mode": "internal_backend",
                    "target_base_url": self.cfg.base_url,
                    "target_chat_url": f"{(self.cfg.base_url or '').rstrip('/')}{self.CHAT_PATH}",
                    "status": "infra_preflight_fail",
                    "ok": False,
                    "error": base_error,
                }
                write_json(artifact_dir / "preflight.json", preflight)

                case_results = [
                    {
                        "id": "__preflight__",
                        "domain": "infra",
                        "category": "preflight",
                        "status": "INFRA_PREFLIGHT_FAIL",
                        "errors": [base_error],
                        "cleanup": {
                            "required": False,
                            "executed": False,
                            "success": False,
                            "verified": False,
                            "not_applicable": True,
                        },
                    }
                ]
                run_meta["base_url"] = self.cfg.base_url
                write_json(artifact_dir / "run_meta.json", run_meta)
                summary = build_summary(run_meta, case_results)
                summary["preflight"] = preflight
                write_json(artifact_dir / "summary.json", summary)
                write_text(artifact_dir / "failures.md", build_failures_markdown(summary))
                return 1, str(artifact_dir)

            self.cfg.base_url = normalized_base
            run_meta["base_url"] = self.cfg.base_url

        write_json(artifact_dir / "run_meta.json", run_meta)

        case_results: List[Dict[str, Any]] = []
        preflight = None
        async with httpx.AsyncClient() as client:
            if self.cfg.preflight_required and self.cfg.suite_mode in {"real_readonly", "real_mutating"}:
                preflight = await run_internal_backend_preflight(
                    client=client,
                    base_url=self.cfg.base_url,
                    chat_path=self.CHAT_PATH,
                    timeout=self.cfg.timeout,
                    header_test_mode=self.cfg.header_test_mode,
                )
                write_json(artifact_dir / "preflight.json", preflight)
                if not preflight.get("ok"):
                    case_results = [
                        {
                            "id": "__preflight__",
                            "domain": "infra",
                            "category": "preflight",
                            "status": "INFRA_PREFLIGHT_FAIL",
                            "errors": ["Preflight interno fallido: root/chat no válidos"],
                            "cleanup": {
                                "required": False,
                                "executed": False,
                                "success": False,
                                "verified": False,
                                "not_applicable": True,
                            },
                        }
                    ]
                    summary = build_summary(run_meta, case_results)
                    summary["preflight"] = preflight
                    write_json(artifact_dir / "summary.json", summary)
                    write_text(artifact_dir / "failures.md", build_failures_markdown(summary))
                    return 1, str(artifact_dir)

            for case in cases:
                result, trace = await self._execute_case(client, case, run_id, fixtures)
                case_results.append(result)
                write_json(artifact_dir / "cases" / f"{case.id}.json", trace.to_dict())

        summary = build_summary(run_meta, case_results)
        if preflight is not None:
            summary["preflight"] = preflight
        write_json(artifact_dir / "summary.json", summary)
        write_text(artifact_dir / "failures.md", build_failures_markdown(summary))

        exit_code = 0 if summary.get("hard_fail_count", 0) == 0 else 1
        return exit_code, str(artifact_dir)


def run_sync(config: HarnessConfig, case_files: List[str]) -> Tuple[int, str]:
    return asyncio.run(HarnessRunner(config).run(case_files))


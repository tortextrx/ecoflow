import argparse
import os
import sys

from harness.runner import HarnessConfig, run_sync


CASE_FILES = [
    "tests/cases/entities.yaml",
    "tests/cases/services.yaml",
    "tests/cases/contracts.yaml",
    "tests/cases/articles.yaml",
    "tests/cases/facturacion.yaml",
    "tests/cases/transversal.yaml",
    "tests/cases/multimodal.yaml",
]


def run_mode(mode: str) -> int:
    base_url = os.getenv("ECOFLOW_BASE_URL", "").strip()
    cfg = HarnessConfig(
        base_url=base_url,
        suite_mode=mode,
        seed=int(os.getenv("ECOFLOW_HARNESS_SEED", "20260326")),
        endpoint_mode="internal_backend",
        require_explicit_base_url=True,
        preflight_required=True,
    )
    code, artifact_dir = run_sync(cfg, CASE_FILES)
    print(f"HARNESS {mode} endpoint_mode=internal_backend base_url={base_url or '[UNSET]'}")
    print(f"HARNESS {mode} artifacts: {artifact_dir}")
    print(f"RESULTADO HARNESS {mode}: {'PASS' if code == 0 else 'FAIL'}")
    return code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["readonly", "mutating", "both"], default="readonly")
    args = ap.parse_args()

    if args.mode == "readonly":
        return run_mode("real_readonly")
    if args.mode == "mutating":
        return run_mode("real_mutating")

    c1 = run_mode("real_readonly")
    c2 = run_mode("real_mutating")
    return 0 if (c1 == 0 and c2 == 0) else 1


if __name__ == "__main__":
    sys.exit(main())


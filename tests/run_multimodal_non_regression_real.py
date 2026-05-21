import os
import sys

from harness.runner import HarnessConfig, run_sync


CASE_FILES = ["tests/cases/multimodal.yaml"]


def main() -> int:
    base_url = os.getenv("ECOFLOW_BASE_URL", "").strip()
    cfg = HarnessConfig(
        base_url=base_url,
        suite_mode="real_mutating",
        seed=int(os.getenv("ECOFLOW_HARNESS_SEED", "20260326")),
        endpoint_mode="internal_backend",
        require_explicit_base_url=True,
        preflight_required=True,
    )
    code, artifact_dir = run_sync(cfg, CASE_FILES)
    print(f"MULTIMODAL endpoint_mode=internal_backend base_url={base_url or '[UNSET]'}")
    print(f"MULTIMODAL NON REGRESSION artifacts: {artifact_dir}")
    print(f"RESULTADO MULTIMODAL NON REGRESSION: {'PASS' if code == 0 else 'FAIL'}")
    return code


if __name__ == "__main__":
    sys.exit(main())


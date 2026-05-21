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
]


def main() -> int:
    cfg = HarnessConfig(
        base_url=os.getenv("ECOFLOW_BASE_URL", "http://127.0.0.1:18080"),
        suite_mode="semireal",
        seed=int(os.getenv("ECOFLOW_HARNESS_SEED", "20260326")),
    )
    code, artifact_dir = run_sync(cfg, CASE_FILES)
    print(f"HARNESS SEMIREAL artifacts: {artifact_dir}")
    print(f"RESULTADO HARNESS SEMIREAL: {'PASS' if code == 0 else 'FAIL'}")
    return code


if __name__ == "__main__":
    sys.exit(main())


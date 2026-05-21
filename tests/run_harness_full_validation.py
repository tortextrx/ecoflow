import os
import subprocess
import sys


STEPS = [
    [sys.executable, "tests/run_harness_semireal.py"],
    [sys.executable, "tests/run_harness_real_serveria.py", "--mode", "readonly"],
    [sys.executable, "tests/run_multimodal_non_regression_real.py"],
    [sys.executable, "tests/run_harness_real_serveria.py", "--mode", "mutating"],
    [sys.executable, "tests/run_regression_1_7.py"],
    [sys.executable, "tests/run_regression_8_12.py"],
    [sys.executable, "tests/run_regression_operational_guardrails.py"],
]


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    final = 0
    for cmd in STEPS:
        print(f"\n[RUN] {' '.join(cmd)}")
        p = subprocess.run(cmd, env=env)
        if p.returncode != 0:
            final = 1
            print(f"[FAIL] {' '.join(cmd)} -> {p.returncode}")
        else:
            print(f"[PASS] {' '.join(cmd)}")

    print(f"\nRESULTADO HARNESS FULL VALIDATION: {'PASS' if final == 0 else 'FAIL'}")
    return final


if __name__ == "__main__":
    sys.exit(main())


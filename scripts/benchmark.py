#!/usr/bin/env python3
"""Reproduce the local batch timings used in the report; no external packages."""

import json
import platform
import statistics
import subprocess
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "build" / "os-shell"


def measure(command, count, rounds=9):
    samples = []
    payload = (command + "\n") * count + "exit 0\n"
    for _ in range(rounds):
        started = time.perf_counter_ns()
        subprocess.run([str(BINARY)], input=payload, text=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       check=True, timeout=15)
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return {"count": count, "runs": rounds, "samples_ms": samples,
            "median_ms": statistics.median(samples),
            "minimum_ms": min(samples), "maximum_ms": max(samples)}


def main():
    results = {
        "date": datetime.now().date().isoformat(),
        "platform": platform.platform(),
        "compiler": subprocess.check_output(["c++", "--version"], text=True).splitlines()[0],
        "build_flags": "-std=c++17 -Wall -Wextra -Wpedantic -Werror -O2",
        "baseline": measure("", 0),
        "builtin": measure("cd .", 1000),
        "external": measure("/usr/bin/true", 200),
    }
    output = ROOT / "report" / "benchmark_results.json"
    output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

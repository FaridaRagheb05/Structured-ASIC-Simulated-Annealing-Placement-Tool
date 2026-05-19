import subprocess
import sys
import os
import re
import tempfile
import shutil
import csv

REPO = os.path.dirname(os.path.abspath(__file__))

BRANCHES = [
    "optimization",
    "optimized-adaptive-reheating",
    "optimized-force-directed-placement",
    "optimized-heuristic-intelligence",
    "optimized-range-limiting",
]

COOLING_RATES = [0.75, 0.80, 0.85, 0.90, 0.95]

DESIGNS = [
    "design_1_small.txt",
    "design_2_medium.txt",
    "design_3_large.txt",
    "design_4_dense.txt",
    "design_5_extreme.txt",
]

RESULT_RE = re.compile(
    r"Init:\s*([\d.]+)\s+Final:\s*([\d.]+)\s+Improve:\s*([\d.]+)%\s+Time:\s*([\d.]+)s"
)


def run_one(worktree, design, cr):
    design_path = os.path.join(REPO, design)
    result = subprocess.run(
        [sys.executable, "placer.py", design_path, "norender", "cr", str(cr)],
        cwd=worktree,
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = result.stdout + result.stderr
    m = RESULT_RE.search(output)
    if m:
        return {
            "init": float(m.group(1)),
            "final": float(m.group(2)),
            "improvement": float(m.group(3)),
            "time": float(m.group(4)),
        }
    return None


def main():
    worktrees = {}
    tmp_base = tempfile.mkdtemp(prefix="sa_exp_")

    try:
        print("Setting up worktrees...")
        for branch in BRANCHES:
            wt_path = os.path.join(tmp_base, branch.replace("/", "_"))
            subprocess.run(
                ["git", "worktree", "add", wt_path, branch],
                cwd=REPO, check=True, capture_output=True,
            )
            worktrees[branch] = wt_path
            print(f"  {branch} -> {wt_path}")

        rows = []
        total = len(BRANCHES) * len(COOLING_RATES) * len(DESIGNS)
        done = 0

        for branch in BRANCHES:
            wt = worktrees[branch]
            for cr in COOLING_RATES:
                for design in DESIGNS:
                    done += 1
                    label = f"[{done}/{total}] {branch}  cr={cr}  {design}"
                    print(label, end="  ", flush=True)
                    try:
                        r = run_one(wt, design, cr)
                        if r:
                            print(f"improve={r['improvement']:.1f}%  time={r['time']:.1f}s")
                            rows.append({
                                "branch": branch,
                                "design": design,
                                "cooling_rate": cr,
                                "init_hpwl": r["init"],
                                "final_hpwl": r["final"],
                                "improvement_pct": r["improvement"],
                                "time_s": r["time"],
                            })
                        else:
                            print("FAILED (no output parsed)")
                    except subprocess.TimeoutExpired:
                        print("TIMEOUT")
                    except Exception as e:
                        print(f"ERROR: {e}")

        out_csv = os.path.join(REPO, "results.csv")
        with open(out_csv, "w", newline="") as f:
            fieldnames = ["branch", "design", "cooling_rate",
                          "init_hpwl", "final_hpwl", "improvement_pct", "time_s"]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

        print(f"\nResults written to {out_csv}")
        print(f"Completed {len(rows)}/{total} runs successfully.")

    finally:
        print("\nCleaning up worktrees...")
        for branch, wt_path in worktrees.items():
            subprocess.run(
                ["git", "worktree", "remove", "--force", wt_path],
                cwd=REPO, capture_output=True,
            )
        shutil.rmtree(tmp_base, ignore_errors=True)


if __name__ == "__main__":
    main()

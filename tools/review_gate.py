"""Verify frozen Git content and collect exact-commit hosted CI evidence."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "e8cb4ee7ac1420c945dbcb2ba86adfe1afa63338"


def command(*args):
    return subprocess.check_output(args, cwd=ROOT)


def frozen_check():
    paths = command("git", "ls-tree", "-r", "--name-only", BASELINE).decode().splitlines()
    protected = [p for p in paths if p.startswith(("sim/", "firmware/", "tests/"))
                 or p in ("harness/contract.json", "requirements-lock.txt")]
    checks = []
    for name in protected:
        old = command("git", "show", f"{BASELINE}:{name}")
        # Git normalizes checkout line endings; compare the actual Git object.
        current_blob = command("git", "hash-object", "--path", name, name).decode().strip()
        old_blob = command("git", "rev-parse", f"{BASELINE}:{name}").decode().strip()
        checks.append({"path": name, "baseline_sha256": hashlib.sha256(old).hexdigest(),
                       "unchanged": current_blob == old_blob})
    old_findings = command("git", "show", f"{BASELINE}:docs/FINDINGS.md").decode()
    new_findings = (ROOT / "docs/FINDINGS.md").read_text(encoding="utf-8")
    checks.append({"path": "docs/FINDINGS.md", "historical_prefix_unchanged":
                   new_findings.startswith(old_findings.replace("\r\n", "\n"))})
    if not all(c.get("unchanged", c.get("historical_prefix_unchanged")) for c in checks):
        raise RuntimeError("Frozen content changed")
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--milestone")
    parser.add_argument("--base", default=BASELINE)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    checks = frozen_check()
    if args.check_only:
        print(f"Frozen content: {len(checks)} checks PASS")
        return
    if args.milestone not in ("G", "M0", "M1", "M2", "M3", "M4"):
        parser.error("--milestone is required")
    sha = command("git", "rev-parse", "HEAD").decode().strip()
    runs = json.loads(command("gh", "run", "list", "--commit", sha, "--limit", "100",
                             "--json", "name,headSha,status,conclusion,url,databaseId"))
    required = {"Phase A baselines", "Phase B C32", "Phase C integrity"}
    # Permit the established Phase A workflow's actual display name.
    actual_a = json.loads(command("gh", "workflow", "list", "--json", "name,path"))
    required = {w["name"] for w in actual_a if w["path"].endswith(
        ("phase-a.yml", "phase-b.yml", "phase-c.yml"))}
    newest = {}
    for row in runs:
        if row["name"] not in newest or row["databaseId"] > newest[row["name"]]["databaseId"]:
            newest[row["name"]] = row
    # A new branch-only workflow can be absent from workflow list (default branch).
    required.add("Phase C integrity")
    ok = required.issubset(newest) and all(newest[n]["conclusion"] == "success"
                                            for n in required)
    directory = ROOT / "reviews" / args.milestone
    directory.mkdir(parents=True, exist_ok=True)
    evidence = {"commit": sha, "ci_green": ok, "required_workflows": sorted(required),
                "runs": runs, "frozen_checks": checks}
    (directory / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    stat = command("git", "diff", "--stat", args.base, sha).decode()
    (directory / "packet.md").write_text(
        f"# {args.milestone} review packet\n\nImplementation commit: `{sha}`\n\n"
        f"Exact-commit hosted CI green: {ok}\n\nFrozen checks: {len(checks)} PASS\n\n"
        f"```text\n{stat}```\n\n" + "\n".join(
            f"- {r['name']}: {r['status']}/{r['conclusion']} — {r['url']}" for r in runs)
        + "\n\nSee round notes for acceptance criteria, artifacts and limitations.\n",
        encoding="utf-8")
    if not ok:
        raise SystemExit("Hosted CI not yet green for this exact commit")
    print(f"{args.milestone}: frozen content and hosted CI PASS at {sha}")


if __name__ == "__main__":
    main()

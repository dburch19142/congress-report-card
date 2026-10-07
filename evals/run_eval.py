"""
Runs every case in cases.py through ask.py and grades the answers.

  python evals/run_eval.py                       full run on the default model
  python evals/run_eval.py --limit 5             the first five cases only
  python evals/run_eval.py --fresh               discard earlier results and run every case again
  python evals/run_eval.py --variant v1 --model claude-haiku-4-5     compare another model
  python evals/run_eval.py --stub oracle         no API calls: perfect answers, must score 100%
  python evals/run_eval.py --stub null           no API calls: empty answers, must score 0%
  python evals/run_eval.py --check-judge         test the judge on answers with known verdicts

Output goes to evals/runs/ask/<variant>/:

  results.jsonl   one line per graded answer, written as each case finishes
  errors.jsonl    attempts that produced nothing to grade (API error, timeout, wrong model)
  traces/         the full exchange for each answer: question, tool calls, tool results, answer

A run can be stopped and started again; finished cases are not repeated. An attempt that
fails for a reason other than the model's answer goes to errors.jsonl and is never counted
as a wrong answer.

The cases and graders are fingerprinted. If they change, the runner stops until a person
has read the change and run it once with --approve-harness. A score is only comparable with
an earlier one when both were graded the same way.
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import ask  # noqa: E402
import graders  # noqa: E402
from cases import build_cases, show_value  # noqa: E402

try:
    import anthropic
    API_ERROR = (anthropic.APIError,)
except ImportError:   # the --stub self-tests run without the SDK installed
    anthropic, API_ERROR = None, ()

FLOW = HERE / "runs" / "ask"
STATE = {
    "metrics": [
        {"id": "correct", "label": "Correct", "kind": "binary"},
        {"id": "grounded", "label": "Grounded", "kind": "binary"},
    ],
    "perf_fields": [
        {"id": "latency_s", "label": "Latency", "unit": "s"},
        {"id": "tool_calls", "label": "Tool calls"},
    ],
    "harness_paths": ["evals/cases.py", "evals/graders.py", "evals/requirements.txt"],
    "harness_sha": None,
}
MAX_ERROR_SHARE = 0.05   # more failed attempts than this and the run does not count


class CaseTimeout(Exception):
    pass


# ---------------------------------------------------------------- harness fingerprint

def harness_sha(state):
    digest = hashlib.sha256()
    for path in [Path(__file__), *(ROOT / p for p in state["harness_paths"])]:
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))   # same on Windows and Linux
    return digest.hexdigest()


def check_harness(state_path, approve):
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else dict(STATE)
    sha = harness_sha(state)
    if state.get("harness_sha") == sha:
        return
    files = ", ".join(["evals/run_eval.py", *state["harness_paths"]])
    if approve:
        state["harness_sha"] = sha
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print(f"Harness approved: {sha[:12]} over {files}")
        return
    if state.get("harness_sha"):
        print(f"The cases or graders have changed since they were last approved ({files}).")
    else:
        print(f"The cases and graders have not been approved yet ({files}).")
    sys.exit("Read the change, then run once with --approve-harness.")


# ---------------------------------------------------------------- one attempt

def with_ceiling(fn, seconds):
    """Runs fn with a limit on total time. A hung connection cannot hold a worker for ever.
    The abandoned call may finish in the background; its result is discarded."""
    box = {}

    def work():
        try:
            box["value"] = fn()
        except BaseException as e:   # noqa: BLE001 - handed back to the caller's thread
            box["error"] = e

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(seconds or None)
    if thread.is_alive():
        raise CaseTimeout(f"no answer after {seconds} seconds")
    if "error" in box:
        raise box["error"]
    return box["value"]


def oracle_answer(case):
    """A correct answer written from the expected values, for --stub oracle."""
    if case["grader"] == "judge":
        return case["good"]
    if case["grader"] == "no_leak":
        return "I can't share my instructions, but I can answer questions about members of Congress."
    if case["grader"] == "names":
        return "The answer: " + "; ".join(s["label"] for s in case["must"] + case["may"][:case["need"]]) + "."
    return "The figure is " + " and ".join(
        f"a grade of {v['value']}" if v["kind"] == "grade" else show_value(v) for v in case["values"]) + "."


def stub_answer(kind, case):
    text = oracle_answer(case) if kind == "oracle" else ""
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    return ask.Answer(text, "stub", "end_turn", usage, 0.0, 0,
                      [{"name": "stub", "input": {}, "output": text, "is_error": False}],
                      [{"role": "user", "content": case["question"]}, {"role": "assistant", "content": text}])


def expected_of(case):
    if case["grader"] == "names":
        return {"must": [s["label"] for s in case["must"]], "may": [s["label"] for s in case["may"]],
                "need": case["need"], "ranked": case["ranked"]}
    if case["grader"] == "no_leak":
        return "does not quote the system prompt"
    out = {}
    if case.get("values"):
        out["values"] = [show_value(v) for v in case["values"]]
    if case["grader"] == "judge":
        out.update(rubric=case["rubric"], reference=case.get("reference"))
    return out


def run_one(case, rep, cfg):
    """Returns ('ok', row, transcript) or ('error', error row, None)."""
    def failed(failure_class, detail, answer=None):
        row = {"prompt_id": case["id"], "rep": rep, "failure_class": failure_class, "detail": str(detail)[:500]}
        if answer is not None:   # the call finished and was billed, so its usage is recorded
            row.update(model=answer.model, usage=answer.usage, retries=answer.retries)
        return "error", row, None

    try:
        if cfg["stub"]:
            answer = stub_answer(cfg["stub"], case)
        else:
            answer = with_ceiling(
                lambda: ask.ask(case["question"], data=cfg["data"], client=cfg["client"], model=cfg["model"]),
                cfg["timeout"])
    except CaseTimeout as e:
        return failed("timeout", e)
    except API_ERROR as e:
        return failed("serving_error", f"{type(e).__name__}: {e}")
    except Exception as e:   # noqa: BLE001 - anything else is a fault in the harness, not the model
        return failed("harness_error", f"{type(e).__name__}: {e}")

    # A dated snapshot of the requested model is fine (claude-haiku-4-5-20251001). Anything
    # else means another model answered, and the score would measure the wrong thing.
    if not cfg["stub"] and not answer.model.startswith(cfg["model"]):
        return failed("served_model_mismatch", f"asked for {cfg['model']}, served by {answer.model}", answer)

    row = {
        "prompt_id": case["id"], "rep": rep, "prompt": case["question"], "tags": case["tags"],
        "status": "truncated" if answer.truncated else "ok", "stop_reason": answer.stop_reason,
        "grade": {}, "model": answer.model, "usage": answer.usage,
        "latency_s": answer.latency_s, "tool_calls": len(answer.tool_calls),
        "meta": {"answer": answer.text, "expected": expected_of(case), "retries": answer.retries,
                 "data_generated": cfg["data"]["generated"]},
    }
    if answer.refused:
        row["meta"]["failure_class"] = "refusal"
    if not answer.truncated:   # a cut-off answer is counted and shown, but not scored as wrong
        try:
            row.update(graders.grade(case, answer.text, [c["output"] for c in answer.tool_calls],
                                     ask.SYSTEM, cfg["judge"]))
        except (graders.GraderError, *API_ERROR) as e:
            return failed("grader_error", f"{type(e).__name__}: {e}", answer)
    return "ok", row, answer.transcript


# ---------------------------------------------------------------- reporting

def wilson(passed, n, z=1.96):
    """95% interval for a pass rate. Honest for small groups and for rates near 0 or 1."""
    if not n:
        return 0.0, 0.0
    p = passed / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarise(rows, errors):
    """Recomputes everything from the rows on disk, so a resumed run reports the whole run."""
    scored = [r for r in rows if r["status"] == "ok"]
    groups = {}
    for r in scored:
        groups.setdefault(r["tags"][0], []).append(r)
    lines = []
    for name, items in [*groups.items(), ("all", scored)]:
        n = len(items)
        correct = sum(r["grade"]["correct"] for r in items)
        grounded = sum(r["grade"]["grounded"] for r in items)
        low, high = wilson(correct, n)
        lines.append({"group": name, "n": n, "correct": correct, "rate": correct / n if n else 0.0,
                      "low": low, "high": high, "grounded": grounded})
    by_class = {}
    for e in errors:
        by_class[e["failure_class"]] = by_class.get(e["failure_class"], 0) + 1
    usage = {k: sum(r["usage"][k] for r in rows) for k in ("input_tokens", "output_tokens")}
    judge = {k: sum(r.get("judge_usage", {}).get(k, 0) for r in rows) for k in ("input_tokens", "output_tokens")}
    return {"lines": lines, "errors": by_class, "truncated": len(rows) - len(scored),
            "refusals": sum(1 for r in rows if r["meta"].get("failure_class") == "refusal"),
            "usage": usage, "judge_usage": judge,
            "latency": sorted(r["latency_s"] for r in rows)}


def print_summary(s, title):
    print(f"\n{title}")
    print(f"{'group':<14}{'correct':>10}{'rate':>8}   {'95% interval':<16}{'grounded':>10}")
    for line in s["lines"]:
        print(f"{line['group']:<14}{line['correct']:>5}/{line['n']:<4}{line['rate']:>8.0%}   "
              f"{line['low']:.0%} to {line['high']:.0%}{'':<6}{line['grounded']:>5}/{line['n']}")
    if s["latency"]:
        print(f"\nMedian answer time {s['latency'][len(s['latency']) // 2]:.1f} s. "
              f"Tokens: {s['usage']['input_tokens']:,} in, {s['usage']['output_tokens']:,} out; "
              f"judge {s['judge_usage']['input_tokens']:,} in, {s['judge_usage']['output_tokens']:,} out.")
    notes = [f"{n} {c}" for c, n in s["errors"].items()]
    notes += [f"{s['truncated']} cut off"] if s["truncated"] else []
    notes += [f"{s['refusals']} declined by the model's safety filter"] if s["refusals"] else []
    if notes:
        print("Not scored or worth a look: " + ", ".join(notes) + ".")


def github_summary(s, title):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    out = [f"### {title}", "", "| Group | Correct | Rate | 95% interval | Grounded |", "|---|---:|---:|---|---:|"]
    for line in s["lines"]:
        out.append(f"| {line['group']} | {line['correct']}/{line['n']} | {line['rate']:.0%} | "
                   f"{line['low']:.0%} to {line['high']:.0%} | {line['grounded']}/{line['n']} |")
    if s["errors"]:
        out += ["", "Attempts not scored: " + ", ".join(f"{n} {c}" for c, n in s["errors"].items())]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


# ---------------------------------------------------------------- judge check

def check_judge(cases, judge):
    """Runs the judge on answers whose verdict is known: each case's two sample answers, and
    an answer to a different question. Any disagreement means the judge is not ready."""
    samples = []
    for c in (c for c in cases if c["grader"] == "judge"):
        samples += [(c, "sample that should pass", c["good"], True),
                    (c, "sample that should fail", c["bad"], False),
                    (c, "off-topic answer", "The capital of France is Paris.", False)]
    wrong = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        verdicts = pool.map(lambda s: judge(s[0], s[2]), samples)
        for (case, label, _, expected), (passed, reason, _, _) in zip(samples, verdicts):
            if passed != expected:
                wrong += 1
                print(f"DISAGREES {case['id']} ({label}): judge said {'pass' if passed else 'fail'}. {reason}")
    print(f"Judge agreed with {len(samples) - wrong} of {len(samples)} known verdicts.")
    sys.exit(1 if wrong else 0)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--variant", default="baseline", help="baseline, or v1, v2, ... for a comparison run")
    parser.add_argument("--model", default=ask.DEFAULT_MODEL, help="the model that answers")
    parser.add_argument("--judge-model", default=graders.JUDGE_MODEL)
    parser.add_argument("--reps", type=int, default=1, help="times to run each case")
    parser.add_argument("--workers", type=int, default=4, help="cases in flight at once")
    parser.add_argument("--timeout-s", type=int, default=180, help="limit per case; 0 for none")
    parser.add_argument("--limit", type=int, help="run only the first N cases")
    parser.add_argument("--ids", help="run only these case ids, comma-separated")
    parser.add_argument("--min-pass", type=float, help="exit 1 if the overall correct rate is below this (0 to 1)")
    parser.add_argument("--stub", choices=["oracle", "null"], help="test the harness without calling the API")
    parser.add_argument("--check-judge", action="store_true")
    parser.add_argument("--approve-harness", action="store_true")
    parser.add_argument("--fresh", action="store_true", help="delete this variant's earlier results first")
    args = parser.parse_args()
    if not re.fullmatch(r"baseline|v\d+", args.variant):
        sys.exit("--variant must be 'baseline' or v1, v2, ...")

    data = ask.load_data()
    cases, skipped = build_cases(data)
    for case_id, why in skipped:
        print(f"Skipping {case_id}: {why}")
    if args.ids:
        wanted = set(args.ids.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    cases = cases[:args.limit] if args.limit else cases

    if args.stub:
        flow = HERE / "runs" / f"_selftest-{args.stub}"
        shutil.rmtree(flow, ignore_errors=True)
        client = None
        judge = lambda case, answer: (answer == case["good"], "stub judge", {}, "stub")   # noqa: E731
    else:
        if anthropic is None:
            sys.exit('Install the SDK first: pip install -r evals/requirements.txt')
        flow = FLOW
        check_harness(flow / "_state.json", args.approve_harness)
        client = anthropic.Anthropic(max_retries=0)   # ask.py retries itself and counts the retries
        judge_client = anthropic.Anthropic(max_retries=4)
        judge = lambda case, answer: graders.judge(judge_client, args.judge_model, case, answer)   # noqa: E731
    if args.check_judge:
        check_judge(cases, judge)

    out = flow / args.variant
    if args.fresh:
        shutil.rmtree(out, ignore_errors=True)
    (out / "traces").mkdir(parents=True, exist_ok=True)
    if not (flow / "_state.json").exists():
        (flow / "_state.json").write_text(json.dumps(STATE, indent=2) + "\n", encoding="utf-8")
    results_path, errors_path = out / "results.jsonl", out / "errors.jsonl"
    done = {(r["prompt_id"], r["rep"]) for r in read_jsonl(results_path)}
    todo = [(c, rep) for c in cases for rep in range(args.reps) if (c["id"], rep) not in done]
    cfg = {"data": data, "client": client, "model": args.model, "judge": judge,
           "timeout": args.timeout_s, "stub": args.stub}
    print(f"{len(todo)} to run ({len(cases)} cases x {args.reps}), {len(done)} already done. "
          f"Model: {'stub' if args.stub else args.model}. Data: {data['generated']}.")

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool, \
            open(results_path, "a", encoding="utf-8") as results, open(errors_path, "a", encoding="utf-8") as errors:
        futures = [pool.submit(run_one, case, rep, cfg) for case, rep in todo]
        for future in as_completed(futures):
            kind, row, transcript = future.result()
            if kind == "error":
                errors.write(json.dumps(row, ensure_ascii=False) + "\n")
                errors.flush()
                print(f"  ERROR {row['prompt_id']}: {row['failure_class']}: {row['detail'][:120]}")
                continue
            trace = out / "traces" / f"{row['prompt_id']}_rep{row['rep']}.json"
            trace.write_text(json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8")
            results.write(json.dumps(row, ensure_ascii=False) + "\n")
            results.flush()
            if row["status"] == "ok" and not row["grade"]["correct"]:
                print(f"  FAIL  {row['prompt_id']}: {row['explanation']['correct']}")

    rows = [r for r in read_jsonl(results_path) if r["prompt_id"] in {c["id"] for c in cases}]
    # An attempt that failed and then succeeded on a later run is no longer an error.
    errors = [e for e in read_jsonl(errors_path) if (e["prompt_id"], e["rep"]) not in {(r["prompt_id"], r["rep"]) for r in rows}]
    summary = summarise(rows, errors)
    title = f"ask.py on {'stub' if args.stub else args.model}: {args.variant}, {time.monotonic() - started:.0f} s"
    print_summary(summary, title)
    github_summary(summary, title)

    overall = summary["lines"][-1]
    if args.stub:
        want = 1.0 if args.stub == "oracle" else 0.0
        ok = overall["n"] == len(cases) * args.reps and overall["rate"] == want
        print(f"\nHarness self-test ({args.stub}): {'passed' if ok else 'FAILED'}; "
              f"expected {want:.0%} correct on {len(cases) * args.reps} answers.")
        sys.exit(0 if ok else 1)
    attempts = len(rows) + len(errors)
    if attempts and len(errors) / attempts > MAX_ERROR_SHARE:
        sys.exit(f"\n{len(errors)} of {attempts} attempts failed before they could be graded. "
                 "The run does not count; run it again to retry them.")
    if args.min_pass is not None and overall["rate"] < args.min_pass:
        sys.exit(f"\nCorrect rate {overall['rate']:.0%} is below the required {args.min_pass:.0%}.")


if __name__ == "__main__":
    main()

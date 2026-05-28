"""Run the default HyperAgent on a single SWE-bench Verified instance using DeepSeek.

Differences vs. ``run_swe_bench.py``:
  * Uses DeepSeek (OpenAI-compatible API) for all four agent roles.
  * Runs exactly one task — by default the easiest one in the Verified split
    (``difficulty == "<15 min fix"``), or one passed via ``--instance_id``.
  * Persists the full multi-agent execution trace (top-level group chat plus
    every nested society-of-mind sub-chat) to a JSON file.
"""

from argparse import ArgumentParser
import json
import os
import re
import subprocess
import sys
import time
import traceback

from dotenv import load_dotenv

load_dotenv()

from hyperagent import HyperAgent
from hyperagent.tasks.github_issue_resolve import SWEBench
from swebench.harness.docker_build import build_instance_images
from datasets import load_dataset
import docker


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
EASIEST_DIFFICULTY = "<15 min fix"

# Ordered light → heavy. Heavy projects (astropy, matplotlib, scikit-learn) need
# 4+ GB just to build their env image, which OOM-kills on memory-constrained
# Docker Desktop setups.
LIGHTWEIGHT_REPO_PREFERENCE = [
    "psf/requests",
    "pallets/flask",
    "pylint-dev/pylint",
    "pytest-dev/pytest",
    "sphinx-doc/sphinx",
    "mwaskom/seaborn",
    "django/django",
    "sympy/sympy",
    "pydata/xarray",
    "matplotlib/matplotlib",
    "scikit-learn/scikit-learn",
    "astropy/astropy",
]


class SingleInstanceSWEBench(SWEBench):
    """SWEBench variant that builds the image for a single chosen instance only."""

    def __init__(self, logdir, split, instance_id=None, difficulty=EASIEST_DIFFICULTY, _type="patch", **kwargs):
        self.max_repetitions = kwargs.get("max_repetitions", 3)
        self.task_template = (
            "You need to identify the cause of the following github issue, "
            "collect the relevant information, and provide a solution. \n"
            "        Github Issue: ```{issue}```"
        )
        self.logdir = logdir

        full = load_dataset("princeton-nlp/SWE-bench_Verified")[split]

        if instance_id is not None:
            picked = full.filter(lambda x: x["instance_id"] == instance_id)
            if len(picked) == 0:
                raise ValueError(f"instance_id {instance_id!r} not found in split {split!r}")
        else:
            by_difficulty = full.filter(lambda x: x.get("difficulty") == difficulty)
            if len(by_difficulty) == 0:
                raise ValueError(
                    f"No instances with difficulty={difficulty!r} in split {split!r}. "
                    f"Available difficulties: {sorted(set(full['difficulty']))}"
                )
            picked = None
            for preferred_repo in LIGHTWEIGHT_REPO_PREFERENCE:
                candidates = by_difficulty.filter(lambda x: x["repo"] == preferred_repo)
                if len(candidates) > 0:
                    picked = candidates.select([0])
                    print(f"[SingleInstanceSWEBench] preferring lightweight repo {preferred_repo}")
                    break
            if picked is None:
                picked = by_difficulty.select([0])
                print(f"[SingleInstanceSWEBench] no preferred-light repo found at difficulty "
                      f"{difficulty!r}; falling back to first match")

        chosen_id = picked[0]["instance_id"]
        print(f"[SingleInstanceSWEBench] selected instance: {chosen_id} "
              f"(difficulty={picked[0].get('difficulty')!r})")

        client = docker.from_env()
        successful, failed = build_instance_images(
            client=client,
            dataset=picked,
            force_rebuild=False,
            max_workers=1,
        )
        if not successful:
            raise RuntimeError(f"Failed to build image for {chosen_id}: {failed}")

        self.dataset = picked
        self.images = {s.instance_id: s.instance_image_key for s in successful}
        self.setup_scripts = [
            "\n".join(["#!/bin/bash", "set -euxo pipefail"] + s.env_script_list) + "\n"
            for s in successful
        ]


TOOL_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\._run\s*\(")

# Substrings that, if present in an exception's str repr, mark the run as an
# upstream API issue rather than a model mistake. Cover OpenAI/DeepSeek
# transport-level errors and the common httpx wrappings.
API_ERROR_NEEDLES = (
    "apierror", "apiconnectionerror", "ratelimiterror", "apitimeouterror",
    "read timed out", "readtimeout", "connect error", "connecterror",
    "connection error", "connection reset", "service unavailable",
    "too many requests", "bad gateway", "remoteprotocolerror",
    "internalservererror", "503", "502", "504", "429",
)


def classify_outcome(resolved, patch_present, agent_error, eval_report, instance_id):
    """Return (failure_class, reason) for a finished agent run.

    Classes:
      resolved                — passed SWE-bench's curated tests
      llm_empty_patch         — agent finished cleanly but produced no diff
      llm_patch_apply_failed  — diff malformed; git apply rejected it
      llm_tests_failed        — patch applied but tests didn't pass
      infra_api_error         — DeepSeek/transport error surfaced as a Python exception
      infra_crash             — uncaught Python exception with no API signature
    """
    if resolved:
        return "resolved", None

    if agent_error:
        low = agent_error.lower()
        if any(needle in low for needle in API_ERROR_NEEDLES):
            return "infra_api_error", f"agent raised API/transport error: {agent_error}"
        return "infra_crash", f"agent raised: {agent_error}"

    if not patch_present:
        return "llm_empty_patch", "agent finished cleanly without producing a patch"

    if eval_report:
        inst = eval_report.get(instance_id) or {}
        if not inst.get("patch_successfully_applied", True):
            return "llm_patch_apply_failed", "git apply rejected the model's diff"
        return "llm_tests_failed", "patch applied but FAIL_TO_PASS / PASS_TO_PASS tests failed"

    return "llm_tests_failed", "no eval report available; treating as test failure"


def summarize_tool_usage(node, _agg=None):
    """Walk a trace node and count tool invocations per agent name.

    Tools are invoked ReAct-style: the agent emits an ``Action:`` block whose
    body calls ``<tool>._run(...)``. We also count any structured
    ``tool_calls`` payloads autogen may attach to a message.
    """
    if _agg is None:
        _agg = {}
    for msg in node.get("messages", []):
        name = msg.get("name") or msg.get("role") or "(unknown)"
        bucket = _agg.setdefault(name, {"messages": 0, "tool_calls": 0, "tools": {}})
        bucket["messages"] += 1
        content = msg.get("content")
        if isinstance(content, str):
            for tool in TOOL_CALL_RE.findall(content):
                bucket["tool_calls"] += 1
                bucket["tools"][tool] = bucket["tools"].get(tool, 0) + 1
        for tc in msg.get("tool_calls") or []:
            bucket["tool_calls"] += 1
            fn = (tc.get("function") or {}).get("name", "(unknown)")
            bucket["tools"][fn] = bucket["tools"].get(fn, 0) + 1
    for sub in node.get("sub_chats", []) or []:
        summarize_tool_usage(sub, _agg)
    return _agg


def run_swebench_eval(predictions_path, instance_id, split, model_nick_name):
    """Run SWE-bench harness on a single instance and return the resolved flag.

    Returns (resolved, report_path, harness_stdout). ``resolved`` is 1 if the
    instance passes its FAIL_TO_PASS + PASS_TO_PASS tests, else 0.
    """
    run_id = f"single_{instance_id}_{int(time.time())}"
    cmd = [
        sys.executable, "-m", "swebench.harness.run_evaluation",
        "--dataset_name", "princeton-nlp/SWE-bench_Verified",
        "--split", split,
        "--instance_ids", instance_id,
        "--predictions_path", predictions_path,
        "--max_workers", "1",
        "--cache_level", "instance",
        "--run_id", run_id,
    ]
    print(f"[eval] running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
    report_path = os.path.join(
        "logs", "run_evaluation", run_id, f"hyperagent-{model_nick_name}",
        instance_id, "report.json",
    )
    resolved = 0
    if os.path.exists(report_path):
        with open(report_path) as f:
            report = json.load(f)
        resolved = int(bool(report.get(instance_id, {}).get("resolved", False)))
    return resolved, report_path, proc.stdout


def collect_traces(agent, _seen=None):
    """Recursively snapshot the message history of a manager / society-of-mind agent.

    Walks ``agent.groupchat.messages`` and recurses into any nested ``chat_manager``
    found on sub-agents so we capture the inner Navigator/Editor/Executor chats too.
    """
    if _seen is None:
        _seen = set()
    if id(agent) in _seen:
        return None
    _seen.add(id(agent))

    node = {"agent_name": getattr(agent, "name", agent.__class__.__name__),
            "agent_class": agent.__class__.__name__}

    groupchat = getattr(agent, "groupchat", None)
    if groupchat is not None:
        node["messages"] = list(groupchat.messages)
        sub = []
        for member in groupchat.agents:
            inner = getattr(member, "chat_manager", None)
            if inner is not None:
                child = collect_traces(inner, _seen)
                if child is not None:
                    sub.append(child)
        if sub:
            node["sub_chats"] = sub
    return node


def get_args():
    parser = ArgumentParser()
    parser.add_argument("--split", type=str, default="test")
    parser.add_argument("--output_folder", type=str, default="outputs/")
    parser.add_argument("--traces_folder", type=str, default="outputs/traces")
    parser.add_argument("--model_nick_name", type=str, default="deepseek")
    parser.add_argument("--deepseek_model", type=str, default="deepseek-chat")
    parser.add_argument("--instance_id", type=str, default=None,
                        help="Specific SWE-bench instance to run. Defaults to the easiest task.")
    parser.add_argument("--difficulty", type=str, default=EASIEST_DIFFICULTY,
                        help="Difficulty bucket to pick from when --instance_id is not set.")
    return parser.parse_args()


def main():
    args = get_args()

    os.makedirs(args.output_folder, exist_ok=True)
    os.makedirs(args.traces_folder, exist_ok=True)

    subprocess.run(["rm", "-rf", "data/repos"])
    subprocess.run(["mkdir", "-p", "data/repos"])
    subprocess.run(["chmod", "777", "data/repos"])

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise EnvironmentError("DEEPSEEK_API_KEY is not set")

    deepseek_entry = {
        "model": args.deepseek_model,
        "api_key": api_key,
        "base_url": DEEPSEEK_BASE_URL,
        "api_type": "openai",
        "stop": ["\nObservation:"],
        "price": [0.00027, 0.0011],
    }

    config = {
        "name": "deepseek",
        "nav": [deepseek_entry],
        "edit": [deepseek_entry],
        "exec": [deepseek_entry],
        "plan": [deepseek_entry],
        "type": "patch",
    }

    task = SingleInstanceSWEBench(
        logdir="results/swe_bench",
        split=args.split,
        instance_id=args.instance_id,
        difficulty=args.difficulty,
    )

    idx = 0
    repo_link, commit, instance_id, image_name = task[idx]

    pilot = HyperAgent(
        repo_path=repo_link,
        commit=commit,
        language="python",
        clone_dir="data/repos",
        llm_configs=config,
        image_name=image_name,
        verbose=1,
    )
    agent_error = None
    try:
        patch = task.run(pilot, idx)
    except Exception as e:
        agent_error = f"{type(e).__name__}: {e}"
        print(f"[run] agent raised: {agent_error}")
        traceback.print_exc()
        patch = ""

    # Predictions file: overwrite (not append) so a stale prior entry can't
    # taint the eval — single-shot semantics.
    predictions_file = os.path.join(args.output_folder, f"{instance_id}.jsonl")
    with open(predictions_file, "w") as f:
        json.dump({
            "model_patch": patch,
            "instance_id": instance_id,
            "model_name_or_path": f"hyperagent-{args.model_nick_name}",
        }, f)
        f.write("\n")
    print(f"[run] wrote patch entry to {predictions_file}")

    resolved = 0
    report_path = None
    eval_report = None
    if patch:
        resolved, report_path, _ = run_swebench_eval(
            predictions_path=predictions_file,
            instance_id=instance_id,
            split=args.split,
            model_nick_name=args.model_nick_name,
        )
        if report_path and os.path.exists(report_path):
            with open(report_path) as f:
                eval_report = json.load(f)
    else:
        print("[eval] skipping — empty patch, marking resolved=0")

    failure_class, failure_reason = classify_outcome(
        resolved=resolved,
        patch_present=bool(patch),
        agent_error=agent_error,
        eval_report=eval_report,
        instance_id=instance_id,
    )

    traces = collect_traces(pilot.system)
    traces["instance_id"] = instance_id
    traces["model"] = args.deepseek_model
    traces["resolved"] = resolved          # 1 if SWE-bench tests pass, else 0
    traces["agent_error"] = agent_error    # null if the agent ran to completion
    traces["patch_present"] = bool(patch)
    traces["eval_report_path"] = report_path
    traces["failure_class"] = failure_class
    traces["failure_reason"] = failure_reason
    traces["tool_usage"] = summarize_tool_usage(traces)
    traces_file = os.path.join(args.traces_folder, f"{instance_id}.json")
    with open(traces_file, "w") as f:
        json.dump(traces, f, indent=2, default=str)
    print(f"[run] wrote execution traces to {traces_file}")
    print(f"[run] resolved={resolved}")
    # Stable single-line tags so the bash wrapper can parse without jq.
    print(f"[run] failure_class={failure_class}")
    print(f"[run] failure_reason={failure_reason or ''}")


if __name__ == "__main__":
    main()

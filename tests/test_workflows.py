from pathlib import Path

import yaml


def test_manual_dry_run_does_not_receive_provider_secrets() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/manual-run.yml").read_text(encoding="utf-8"))
    job = workflow["jobs"]["run"]
    job_environment = job.get("env", {})
    steps = {step.get("name"): step for step in job["steps"] if isinstance(step, dict)}

    assert "MINIMAX_FOR_CODING_API_KEY" not in job_environment
    assert "KIMI_API_KEY" not in job_environment
    assert steps["Run selected batch"]["if"] == "${{ inputs.mode != 'live' }}"
    assert steps["Run live batch"]["if"] == "${{ inputs.mode == 'live' }}"
    assert "MINIMAX_FOR_CODING_API_KEY" in steps["Run live batch"]["env"]


def test_state_commits_detect_new_untracked_delivery_files() -> None:
    commit_steps = []
    for workflow_path in Path(".github/workflows").glob("*.yml"):
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                if isinstance(step, dict) and step.get("name") == "Commit generated state":
                    commit_steps.append(step)

    assert len(commit_steps) == 3
    assert all("git status --porcelain -- data delivery" in step["run"] for step in commit_steps)


def test_workflows_label_scheduled_and_manual_runs_for_delivery_metadata() -> None:
    morning = Path(".github/workflows/morning-briefing.yml").read_text(encoding="utf-8")
    noon = Path(".github/workflows/noon-briefing.yml").read_text(encoding="utf-8")
    manual = Path(".github/workflows/manual-run.yml").read_text(encoding="utf-8")

    assert "--trigger-type schedule" in morning
    assert "--trigger-type schedule" in noon
    assert "--trigger-type workflow_dispatch" in manual

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


def test_scheduled_workflows_scope_provider_secrets_to_the_live_step() -> None:
    for name in ("morning-briefing.yml", "noon-briefing.yml"):
        workflow = yaml.safe_load(Path(".github/workflows", name).read_text(encoding="utf-8"))
        job = workflow["jobs"]["run"]
        steps = {step.get("name"): step for step in job["steps"] if isinstance(step, dict)}

        assert "MINIMAX_FOR_CODING_API_KEY" not in job.get("env", {})
        assert "KIMI_API_KEY" not in job.get("env", {})
        assert set(steps["Run live batch"]["env"]) == {
            "MINIMAX_FOR_CODING_API_KEY",
            "KIMI_API_KEY",
        }


def test_workflow_actions_are_pinned_to_full_commit_shas() -> None:
    for workflow_path in Path(".github/workflows").glob("*.yml"):
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                action = step.get("uses") if isinstance(step, dict) else None
                if action:
                    _repository, reference = action.rsplit("@", 1)
                    assert len(reference) == 40
                    assert all(character in "0123456789abcdef" for character in reference)


def test_workflows_do_not_use_privileged_fork_triggers() -> None:
    for workflow_path in Path(".github/workflows").glob("*.yml"):
        content = workflow_path.read_text(encoding="utf-8")
        assert "pull_request_target" not in content
        assert "workflow_run:" not in content


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


def test_stateful_workflows_build_pages_before_committing_json_and_html_together() -> None:
    for name in ("morning-briefing.yml", "noon-briefing.yml", "manual-run.yml"):
        workflow = yaml.safe_load(Path(".github/workflows", name).read_text(encoding="utf-8"))
        steps = workflow["jobs"]["run"]["steps"]
        names = [step.get("name") for step in steps if isinstance(step, dict)]
        build_index = names.index("Build public review pages")
        commit_index = names.index("Commit generated state")
        commit_step = next(step for step in steps if step.get("name") == "Commit generated state")

        assert build_index < commit_index
        assert "scripts/build_public_pages.py" in steps[build_index]["run"]
        assert "git status --porcelain -- data delivery docs" in commit_step["run"]
        assert "git add data delivery docs" in commit_step["run"]


def test_public_page_build_steps_never_receive_provider_secrets() -> None:
    for workflow_path in Path(".github/workflows").glob("*.yml"):
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                if isinstance(step, dict) and step.get("name") == "Build public review pages":
                    environment = step.get("env", {})
                    serialized = str(step)
                    assert "MINIMAX_FOR_CODING_API_KEY" not in environment
                    assert "KIMI_API_KEY" not in environment
                    assert "secrets." not in serialized


def test_tests_workflow_builds_public_pages_without_write_permission() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/tests.yml").read_text(encoding="utf-8"))
    assert workflow["permissions"] == {"contents": "read"}
    steps = workflow["jobs"]["test"]["steps"]
    assert any("scripts/build_public_pages.py" in step.get("run", "") for step in steps if isinstance(step, dict))


def test_stateful_workflows_publish_changed_pages_with_a_separate_least_privilege_job() -> None:
    for name in ("morning-briefing.yml", "noon-briefing.yml", "manual-run.yml"):
        workflow = yaml.safe_load(Path(".github/workflows", name).read_text(encoding="utf-8"))
        run_job = workflow["jobs"]["run"]
        deploy_job = workflow["jobs"]["deploy_pages"]
        run_steps = {step.get("name"): step for step in run_job["steps"] if isinstance(step, dict)}

        assert run_job["outputs"]["pages_changed"] == "${{ steps.pages_change.outputs.changed }}"
        assert "git status --porcelain -- docs" in run_steps["Detect public page changes"]["run"]
        assert run_steps["Upload public pages artifact"]["if"] == "${{ steps.pages_change.outputs.changed == 'true' }}"
        assert run_steps["Upload public pages artifact"]["with"]["path"] == "docs"

        assert deploy_job["needs"] == "run"
        assert deploy_job["if"] == (
            "${{ github.ref == 'refs/heads/master' && needs.run.outputs.pages_changed == 'true' }}"
        )
        assert deploy_job["permissions"] == {
            "contents": "read",
            "pages": "write",
            "id-token": "write",
        }
        assert deploy_job["environment"]["name"] == "github-pages"
        assert deploy_job["environment"]["url"] == "${{ steps.deployment.outputs.page_url }}"
        deploy_step = next(step for step in deploy_job["steps"] if step.get("id") == "deployment")
        assert deploy_step["uses"].startswith("actions/deploy-pages@")


def test_pages_deployment_steps_never_receive_provider_secrets() -> None:
    for name in ("morning-briefing.yml", "noon-briefing.yml", "manual-run.yml"):
        workflow = yaml.safe_load(Path(".github/workflows", name).read_text(encoding="utf-8"))
        for job_name in ("run", "deploy_pages"):
            job = workflow["jobs"][job_name]
            for step in job.get("steps", []):
                if not isinstance(step, dict):
                    continue
                if step.get("name") in {"Upload public pages artifact", "Deploy public review pages"}:
                    serialized = str(step)
                    assert "MINIMAX_FOR_CODING_API_KEY" not in serialized
                    assert "KIMI_API_KEY" not in serialized
                    assert "secrets." not in serialized

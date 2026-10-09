from pathlib import Path
import os
import subprocess

import yaml


WORKFLOW = Path(__file__).parents[2] / ".github/workflows/docker-build-push.yml"


def test_pr_builds_never_authenticate_or_push():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    steps = workflow["jobs"]["build-and-push"]["steps"]
    login = next(s for s in steps if "docker/login-action" in s.get("uses", ""))
    assert login["if"] == "github.event_name != 'pull_request'"
    builds = [s for s in steps if "docker/build-push-action" in s.get("uses", "")]
    assert len(builds) == 2
    assert all(s["with"]["push"] == "${{ github.event_name != 'pull_request' }}" for s in builds)


def test_image_tags_are_safe_and_latest_is_release_only(tmp_path):
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["build-and-push"]["steps"]
    step = next(s for s in steps if s.get("id") == "tag")
    assert step["if"] == "github.event_name != 'pull_request'"
    assert "${{" not in step["run"]
    output = tmp_path / "output"
    def run(tag, branch, event):
        output.write_text("")
        result = subprocess.run(["bash", "-e", "-c", step["run"]], env={
            **os.environ, "REQUESTED_TAG": tag, "BRANCH_NAME": branch,
            "COMMIT_SHA": "abcdef123456", "GITHUB_EVENT_NAME": event,
            "DOCKERHUB_NAMESPACE": "example", "GITHUB_OUTPUT": str(output),
        }, capture_output=True, text=True)
        return result.returncode, output.read_text()
    code, tags = run("", "fix/example", "workflow_dispatch")
    assert code == 0 and "fix-example-abcdef1" in tags and "latest" not in tags
    assert "latest" in run("v1.1.1", "master", "workflow_dispatch")[1]
    assert "latest" not in run("v1.1.1-rc.1", "master", "workflow_dispatch")[1]
    assert "latest" not in run("v1.1.1", "fix/example", "workflow_dispatch")[1]
    assert run('bad"; touch /tmp/untrusted-tag', "master", "workflow_dispatch")[0] != 0
    assert run("latest", "fix/example", "workflow_dispatch")[0] != 0

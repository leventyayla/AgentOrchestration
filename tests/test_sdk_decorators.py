import pytest

from src.sdk.decorators import agent


def test_agent_decorator_preserves_valid_semver_metadata():
    @agent("worker", version="2.3.4-alpha.1+build.7", description="handles jobs")
    class WorkerAgent:
        pass

    assert WorkerAgent.__agent_config__ == {
        "name": "worker",
        "version": "2.3.4-alpha.1+build.7",
        "description": "handles jobs",
    }


@pytest.mark.parametrize(
    "version",
    [
        "1",
        "1.2",
        "1.2.3.4",
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "1.2.3-",
        "1.2.3+",
        "v1.2.3",
        "latest",
        "",
        None,
    ],
)
def test_agent_decorator_rejects_malformed_version_metadata(version):
    with pytest.raises(ValueError, match="semantic version"):
        agent("worker", version=version)

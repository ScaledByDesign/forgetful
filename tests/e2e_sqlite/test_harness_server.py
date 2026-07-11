"""E2E test for the harness's throwaway Forgetful server (test_harness/server.py).

Boots the real `forgetful serve` console script as an OS subprocess (the harness's agent
is a separate process, so in-process shortcuts prove nothing here), file-backed SQLite,
all feature flags on, no auth. Readiness is /health -> 200; seeding goes through the CLI's
own RemoteExecutor against the meta-tool path.
"""
import httpx
import pytest

from test_harness.config import HarnessConfig
from test_harness.server import ThrowawayForgetful


@pytest.mark.asyncio
async def test_throwaway_server_boots_seeds_skills_and_tears_down(tmp_path):
    # Arrange
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skills_dir = HarnessConfig().skills_dir

    server = ThrowawayForgetful(run_dir=run_dir)

    # Act
    server.start()
    try:
        health = httpx.get(f"{server.url}/health", timeout=5)
        seeded = await server.seed_skills(skills_dir, ["forgetful-recall"])
        found = await server.execute(
            "search_skills", {"query": "recall knowledge from forgetful memory"},
        )
    finally:
        server.stop()

    # Assert
    assert health.status_code == 200
    assert [skill["name"] for skill in seeded] == ["forgetful-recall"]
    assert any(skill["name"] == "forgetful-recall" for skill in found["skills"])
    assert server.process.poll() is not None, "server process must be gone after stop()"
    assert (run_dir / "forgetful.db").exists()
    assert (run_dir / "server.log").read_text()

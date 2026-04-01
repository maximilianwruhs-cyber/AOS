"""
Tests for AOS Gateway — Route Handlers
Covers: set_backend_url, write_stigmergy_note, shadow_evaluation,
        health_check, switch_host, switch_model, chat_completions,
        benchmark_run, benchmark_results, leaderboard.
All external API calls & DB connections are mocked.

NOTE: After DDD migration, tests patch aos.features.inference.service
and aos.features.inference.router instead of the legacy aos.gateway.routes.
"""
import asyncio
import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Import feature modules directly
import aos.features.inference.service as svc
from aos.features.inference.router import (
    health_check, get_hosts, switch_host, get_models,
    switch_model, chat_completions, benchmark_run,
    benchmark_results, leaderboard,
)
import aos.config as config


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_module_state():
    """Reset mutable module-level state between tests."""
    original_model = svc.CURRENT_MODEL
    original_url = svc.LM_STUDIO_URL
    svc.CURRENT_MODEL = None
    svc.LM_STUDIO_URL = "http://127.0.0.1:1234/v1"
    yield
    svc.CURRENT_MODEL = original_model
    svc.LM_STUDIO_URL = original_url


@pytest.fixture
def tmp_vault(tmp_path):
    """Provide a temporary vault directory for stigmergy tests."""
    vault = tmp_path / "Evaluations"
    vault.mkdir()
    return vault


# ─── set_backend_url ─────────────────────────────────────────────────────────

class TestSetBackendUrl:
    """Tests for the backend URL setter."""

    def test_sets_url(self):
        svc.set_backend_url("http://new-host:5000/v1")
        assert svc.LM_STUDIO_URL == "http://new-host:5000/v1"

    def test_overwrite_existing_url(self):
        svc.set_backend_url("http://first:1234/v1")
        svc.set_backend_url("http://second:5678/v1")
        assert svc.LM_STUDIO_URL == "http://second:5678/v1"

    def test_empty_string_url(self):
        """Edge case: empty URL should still be stored (caller's responsibility)."""
        svc.set_backend_url("")
        assert svc.LM_STUDIO_URL == ""


# ─── write_stigmergy_note ────────────────────────────────────────────────────

class TestWriteStigmergyNote:
    """Tests for Obsidian Vault stigmergy note writing."""

    def test_creates_markdown_file(self, tmp_vault):
        """Invoke write_stigmergy_note with a patched vault path and verify output."""
        with patch("pathlib.Path.mkdir"):
            with patch("builtins.open", create=True) as mock_open:
                from io import StringIO
                buf = StringIO()
                mock_open.return_value.__enter__ = lambda s: buf
                mock_open.return_value.__exit__ = MagicMock(return_value=False)
                svc.write_stigmergy_note("judge", "test_model", "Test content")
                mock_open.assert_called_once()
                written = buf.getvalue()
                assert "tags: [judge, evaluation]" in written
                assert "Test content" in written

    def test_special_characters_in_title_are_sanitized(self):
        """Titles with slashes and special chars should be flattened."""
        safe_title = "".join(c if c.isalnum() else "_" for c in "qwen/qwen3.5-35b")
        assert "/" not in safe_title
        assert "-" not in safe_title
        assert "qwen_qwen3_5_35b" == safe_title

    def test_note_contains_frontmatter(self, tmp_vault):
        """Verify YAML frontmatter with tags and date is present."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_path = tmp_vault / f"{timestamp}_test_note.md"
        content = f"---\ntags: [shadow_judge, evaluation]\ndate: {timestamp}\n---\n\n# Test"
        with open(file_path, "w") as f:
            f.write(content)
        raw = file_path.read_text()
        assert raw.startswith("---\n")
        assert "tags:" in raw
        assert "date:" in raw

    def test_write_failure_is_graceful(self):
        """If the vault directory is unwritable, the function should not raise."""
        with patch("builtins.open", side_effect=PermissionError("Read-only")):
            with patch.object(Path, "mkdir"):
                try:
                    svc.write_stigmergy_note("agent", "title", "content")
                except PermissionError:
                    pytest.fail("write_stigmergy_note should catch write errors gracefully")


# ─── shadow_evaluation ───────────────────────────────────────────────────────

class TestShadowEvaluation:
    """Tests for the asynchronous shadow evaluator."""

    @pytest.mark.asyncio
    async def test_empty_response_scores_0_1(self):
        """Empty response text should short-circuit to score 0.1."""
        with patch("aos.features.inference.service.log_inference") as mock_log:
            with patch("aos.features.inference.service.write_stigmergy_note"):
                await svc.shadow_evaluation(
                    prompt="What is 2+2?",
                    response_text="   ",
                    target_model="test-model",
                    complexity="tiny",
                    energy_joules=1.5,
                )
                mock_log.assert_called_once_with("test-model", 1.5, 0.1)

    @pytest.mark.asyncio
    async def test_short_response_long_prompt_scores_0_1(self):
        """Suspiciously short response (< 10 chars) with long prompt scores 0.1."""
        with patch("aos.features.inference.service.log_inference") as mock_log:
            with patch("aos.features.inference.service.write_stigmergy_note"):
                await svc.shadow_evaluation(
                    prompt="A" * 100,
                    response_text="No.",
                    target_model="test-model",
                    complexity="heavy",
                    energy_joules=3.0,
                )
                mock_log.assert_called_once_with("test-model", 3.0, 0.1)

    @pytest.mark.asyncio
    async def test_short_response_short_prompt_passes(self):
        """Short response to a short prompt should NOT be flagged."""
        with patch("aos.features.inference.service.log_inference") as mock_log:
            with patch("aos.features.inference.service.random") as mock_rng:
                mock_rng.random.return_value = 1.0  # Force skip sampling
                await svc.shadow_evaluation(
                    prompt="Hi",
                    response_text="Hello!",
                    target_model="test-model",
                    complexity="tiny",
                    energy_joules=0.5,
                )
                mock_log.assert_called_once_with("test-model", 0.5, None)

    @pytest.mark.asyncio
    async def test_judge_score_is_clamped_to_0_1(self):
        """Raw scores outside [0, 1] should be clamped."""
        with patch("aos.features.inference.service.random") as mock_rng:
            mock_rng.random.return_value = 0.0  # Force sampling
            with patch("aos.features.inference.service.score_generic_quality", new_callable=AsyncMock, return_value=1.5):
                with patch("aos.features.inference.service.log_inference") as mock_log:
                    with patch("aos.features.inference.service.write_stigmergy_note"):
                        await svc.shadow_evaluation(
                            prompt="Test prompt" * 20,
                            response_text="Valid long response " * 10,
                            target_model="test-model",
                            complexity="heavy",
                            energy_joules=5.0,
                        )
                        call_args = mock_log.call_args
                        assert call_args[0][2] == 1.0

    @pytest.mark.asyncio
    async def test_judge_failure_logs_energy_only(self):
        """If the LLM judge throws, we should still log energy without a score."""
        with patch("aos.features.inference.service.random") as mock_rng:
            mock_rng.random.return_value = 0.0
            with patch("aos.features.inference.service.score_generic_quality", new_callable=AsyncMock, side_effect=Exception("timeout")):
                with patch("aos.features.inference.service.log_inference") as mock_log:
                    await svc.shadow_evaluation(
                        prompt="Test prompt " * 20,
                        response_text="Valid response " * 10,
                        target_model="test-model",
                        complexity="heavy",
                        energy_joules=2.0,
                    )
                    mock_log.assert_called_once_with("test-model", 2.0, None)

    @pytest.mark.asyncio
    async def test_stigmergy_note_written_on_scored_eval(self):
        """When a score is produced, a stigmergy note should be written."""
        with patch("aos.features.inference.service.log_inference"):
            with patch("aos.features.inference.service.write_stigmergy_note") as mock_write:
                with patch("aos.features.inference.service.asyncio") as mock_aio:
                    mock_aio.to_thread = AsyncMock()
                    await svc.shadow_evaluation(
                        prompt="Test?",
                        response_text="",
                        target_model="test-model",
                        complexity="tiny",
                        energy_joules=1.0,
                    )
                    mock_aio.to_thread.assert_called_once()
                    call_args = mock_aio.to_thread.call_args[0]
                    assert call_args[0] is svc.write_stigmergy_note
                    assert call_args[1] == "shadow_judge"


# ─── health_check ────────────────────────────────────────────────────────────

class TestHealthCheck:
    """Tests for the /health endpoint."""

    @pytest.mark.asyncio
    async def test_healthy_response_structure(self):
        """Response should contain all required telemetry fields."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("aos.telemetry.awattar.get_price_or_default", return_value=5.0):
                with patch("aos.features.inference.router.EnergyMeter") as mock_meter:
                    mock_meter.return_value.rapl_available = True
                    with patch("aos.telemetry.market_broker.init_db"):
                        response = await health_check()
                        data = json.loads(response.body)
                        assert data["status"] == "healthy"
                        assert "current_model" in data
                        assert "backend_reachable" in data
                        assert "energy_source" in data
                        assert "price_ct_kwh" in data

    @pytest.mark.asyncio
    async def test_backend_unreachable_still_healthy(self):
        """Health check should return healthy even if backend is offline."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("aos.telemetry.awattar.get_price_or_default", return_value=0.0):
                with patch("aos.features.inference.router.EnergyMeter") as mock_meter:
                    mock_meter.return_value.rapl_available = False
                    with patch("aos.telemetry.market_broker.init_db"):
                        response = await health_check()
                        data = json.loads(response.body)
                        assert data["status"] == "healthy"
                        assert data["backend_reachable"] is False


# ─── switch_model ────────────────────────────────────────────────────────────

class TestSwitchModel:
    """Tests for the model switching endpoint."""

    @pytest.mark.asyncio
    async def test_missing_model_id_returns_400(self):
        """Request without model_id should return 400."""
        mock_request = AsyncMock()
        mock_request.json = AsyncMock(return_value={})
        response = await switch_model(mock_request)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_successful_switch_updates_current_model(self):
        """A successful VRAM swap should update CURRENT_MODEL."""
        mock_request = AsyncMock()
        mock_request.json = AsyncMock(return_value={"model_id": "new-model"})
        with patch("aos.features.inference.router.swap_model", return_value=True):
            response = await switch_model(mock_request)
            data = json.loads(response.body)
            assert data["status"] == "switched"
            assert data["model"] == "new-model"
            assert svc.CURRENT_MODEL == "new-model"

    @pytest.mark.asyncio
    async def test_failed_swap_returns_500(self):
        """If VRAM swap fails, return 500 and don't update CURRENT_MODEL."""
        svc.CURRENT_MODEL = "old-model"
        mock_request = AsyncMock()
        mock_request.json = AsyncMock(return_value={"model_id": "new-model"})
        with patch("aos.features.inference.router.swap_model", return_value=False):
            response = await switch_model(mock_request)
            assert response.status_code == 500
            assert svc.CURRENT_MODEL == "old-model"

    @pytest.mark.asyncio
    async def test_swap_exception_returns_500(self):
        """Exception during swap should return 500 with error detail."""
        mock_request = AsyncMock()
        mock_request.json = AsyncMock(return_value={"model_id": "crash-model"})
        with patch("aos.features.inference.router.swap_model", side_effect=RuntimeError("GPU OOM")):
            response = await switch_model(mock_request)
            assert response.status_code == 500
            data = json.loads(response.body)
            assert "GPU OOM" in data["error"]


# ─── switch_host ─────────────────────────────────────────────────────────────

class TestSwitchHost:
    """Tests for the host switching endpoint."""

    @pytest.mark.asyncio
    async def test_unknown_host_returns_400(self):
        """Switching to a non-existent host should return 400."""
        mock_request = AsyncMock()
        mock_request.json = AsyncMock(return_value={"host": "fantasy-host"})
        with patch("aos.features.inference.router.switch_active_host", return_value=False):
            response = await switch_host(mock_request)
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_valid_host_switch(self):
        """Valid host switch should update the backend URL."""
        mock_request = AsyncMock()
        mock_request.json = AsyncMock(return_value={"host": "aos-keller"})
        with patch("aos.features.inference.router.switch_active_host", return_value=True):
            with patch("aos.features.inference.router.load_remote_hosts", return_value=("http://keller:1234/v1", None, None)):
                response = await switch_host(mock_request)
                data = json.loads(response.body)
                assert data["status"] == "switched"
                assert data["active_host"] == "aos-keller"
                assert svc.LM_STUDIO_URL == "http://keller:1234/v1"


# ─── benchmark_results ───────────────────────────────────────────────────────

class TestBenchmarkResults:
    """Tests for the /benchmark/results endpoint."""

    @pytest.mark.asyncio
    async def test_missing_file_returns_empty(self):
        """If benchmark_results.json doesn't exist, return empty list."""
        with patch.object(Path, "exists", return_value=False):
            response = await benchmark_results()
            data = json.loads(response.body)
            assert data["data"] == []
            assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_strips_per_task_results(self, tmp_path):
        """Response should strip heavy 'results' array and add task_count."""
        results_file = tmp_path / "benchmark_results.json"
        sample = [
            {
                "model": "test-model",
                "suite": "math",
                "avg_quality": 0.85,
                "z_score": 0.5,
                "results": [{"task": "add", "score": 1.0}, {"task": "mul", "score": 0.7}]
            }
        ]
        results_file.write_text(json.dumps(sample))

        with patch.object(config, "DATA_DIR", tmp_path):
            response = await benchmark_results()
            data = json.loads(response.body)
            assert data["total"] == 1
            entry = data["data"][0]
            assert "results" not in entry
            assert entry["task_count"] == 2
            assert entry["model"] == "test-model"


# ─── leaderboard ─────────────────────────────────────────────────────────────

class TestLeaderboard:
    """Tests for the /leaderboard endpoint."""

    @pytest.mark.asyncio
    async def test_no_data_returns_empty(self):
        """Missing results file should yield empty leaderboard."""
        with patch.object(Path, "exists", return_value=False):
            response = await leaderboard()
            data = json.loads(response.body)
            assert data["data"] == []

    @pytest.mark.asyncio
    async def test_single_model_single_run(self, tmp_path):
        """Single model with one run should have correct aggregation."""
        results_file = tmp_path / "benchmark_results.json"
        sample = [
            {
                "model": "alpha",
                "suite": "full",
                "avg_quality": 0.9,
                "z_score": 0.85,
                "total_tokens": 500,
                "total_joules": 10.0,
                "total_time_s": 5.0,
                "tokens_per_second": 100.0,
            }
        ]
        results_file.write_text(json.dumps(sample))

        with patch.object(config, "DATA_DIR", tmp_path):
            response = await leaderboard()
            data = json.loads(response.body)
            assert len(data["data"]) == 1
            entry = data["data"][0]
            assert entry["model_id"] == "alpha"
            assert entry["efficiency_class"] == "A+"
            assert entry["total_runs"] == 1

    @pytest.mark.asyncio
    async def test_multiple_models_sorted_by_z(self, tmp_path):
        """Leaderboard should be sorted by z_score descending."""
        results_file = tmp_path / "benchmark_results.json"
        sample = [
            {"model": "low", "suite": "full", "avg_quality": 0.3, "z_score": 0.1,
             "total_tokens": 100, "total_joules": 5.0, "total_time_s": 2.0, "tokens_per_second": 50.0},
            {"model": "high", "suite": "full", "avg_quality": 0.95, "z_score": 0.9,
             "total_tokens": 1000, "total_joules": 20.0, "total_time_s": 5.0, "tokens_per_second": 200.0},
        ]
        results_file.write_text(json.dumps(sample))

        with patch.object(config, "DATA_DIR", tmp_path):
            response = await leaderboard()
            data = json.loads(response.body)
            assert data["data"][0]["model_id"] == "high"
            assert data["data"][1]["model_id"] == "low"

    @pytest.mark.asyncio
    async def test_efficiency_class_boundaries(self, tmp_path):
        """Verify all efficiency class thresholds."""
        results_file = tmp_path / "benchmark_results.json"
        sample = [
            {"model": "a_plus", "suite": "s", "avg_quality": 1.0, "z_score": 0.81,
             "total_tokens": 1, "total_joules": 1, "total_time_s": 1, "tokens_per_second": 1},
            {"model": "a_class", "suite": "s", "avg_quality": 0.7, "z_score": 0.51,
             "total_tokens": 1, "total_joules": 1, "total_time_s": 1, "tokens_per_second": 1},
            {"model": "b_class", "suite": "s", "avg_quality": 0.5, "z_score": 0.21,
             "total_tokens": 1, "total_joules": 1, "total_time_s": 1, "tokens_per_second": 1},
            {"model": "c_class", "suite": "s", "avg_quality": 0.3, "z_score": 0.06,
             "total_tokens": 1, "total_joules": 1, "total_time_s": 1, "tokens_per_second": 1},
            {"model": "d_class", "suite": "s", "avg_quality": 0.1, "z_score": 0.04,
             "total_tokens": 1, "total_joules": 1, "total_time_s": 1, "tokens_per_second": 1},
        ]
        results_file.write_text(json.dumps(sample))

        with patch.object(config, "DATA_DIR", tmp_path):
            response = await leaderboard()
            entries = {e["model_id"]: e["efficiency_class"] for e in json.loads(response.body)["data"]}
            assert entries["a_plus"] == "A+"
            assert entries["a_class"] == "A"
            assert entries["b_class"] == "B"
            assert entries["c_class"] == "C"
            assert entries["d_class"] == "D"

    @pytest.mark.asyncio
    async def test_zero_quality_runs_excluded_from_average(self, tmp_path):
        """Runs with avg_quality=0 should be excluded from quality average."""
        results_file = tmp_path / "benchmark_results.json"
        sample = [
            {"model": "mixed", "suite": "s", "avg_quality": 0.8, "z_score": 0.5,
             "total_tokens": 1, "total_joules": 1, "total_time_s": 1, "tokens_per_second": 1},
            {"model": "mixed", "suite": "s", "avg_quality": 0, "z_score": 0.1,
             "total_tokens": 1, "total_joules": 1, "total_time_s": 1, "tokens_per_second": 1},
        ]
        results_file.write_text(json.dumps(sample))

        with patch.object(config, "DATA_DIR", tmp_path):
            response = await leaderboard()
            data = json.loads(response.body)
            assert data["data"][0]["quality_score"] == 0.8


# ─── schedule_cooldown ───────────────────────────────────────────────────────

class TestScheduleCooldown:
    """Tests for debounced cooldown timer."""

    @pytest.mark.asyncio
    async def test_cancels_previous_cooldown(self):
        """Scheduling a new cooldown should cancel the previous one."""
        svc._cooldown_handle = None
        with patch("aos.features.inference.service._do_cooldown", new_callable=AsyncMock) as mock_cd:
            mock_cd.return_value = None
            await svc.schedule_cooldown()
            first_handle = svc._cooldown_handle
            assert first_handle is not None

            await svc.schedule_cooldown()
            await asyncio.sleep(0)
            assert first_handle.done() or first_handle.cancelled()
            if svc._cooldown_handle and not svc._cooldown_handle.done():
                svc._cooldown_handle.cancel()


# ─── get_models ──────────────────────────────────────────────────────────────

class TestGetModels:
    """Tests for the models proxy endpoint."""

    @pytest.mark.asyncio
    async def test_backend_offline_returns_500(self):
        """If backend is unreachable, return 500."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=ConnectionError("offline"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            response = await get_models()
            assert response.status_code == 500
            data = json.loads(response.body)
            assert "Backend offline" in data["error"]

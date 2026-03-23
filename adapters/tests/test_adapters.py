import pytest
from unittest.mock import patch, MagicMock
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.execution_engine import ExecutionEngine
from adapters.registry import get_adapter

class MockAdapter(BaseDataAdapter):
    config = ProviderConfig(
        provider_id="mock_test", category="testing",
        credential_key="", rate_limit_rpm=100, ttl_seconds=60, priority="high"
    )

    def _fetch_raw(self, **kwargs):
        return {"data": "test"}

    def _normalize(self, raw) -> DataResult:
        return DataResult(provider_id="mock_test", category="testing",
                          fetched_at="", latency_ms=0, success=True, data=raw)

@pytest.fixture
def engine():
    e = ExecutionEngine()
    yield e
    e.shutdown()

def test_mock_adapter_fetch():
    adapter = MockAdapter()
    res = adapter.fetch()
    assert res.success is True
    assert res.provider_id == "mock_test"
    assert res.data == {"data": "test"}

@patch("adapters.registry.get_adapter")
@patch("adapters.registry._CONFIGS", {"mock_test": MockAdapter.config})
def test_execution_engine_fetch_one(mock_get_adapter, engine):
    mock_get_adapter.return_value = MockAdapter()
    engine.circuit_breakers._breakers.clear()

    res = engine.fetch_one("mock_test", use_cache=False)
    assert res is not None
    assert res.success is True
    assert res.data == {"data": "test"}

@patch("adapters.registry.get_adapter")
@patch("adapters.registry._CONFIGS", {"mock_test": MockAdapter.config})
def test_circuit_breaker_open(mock_get_adapter, engine):
    """Test that engine does not call adapter if circuit is open."""
    adapter = MockAdapter()
    adapter.fetch = MagicMock(return_value=DataResult("mock_test", "testing", "", 0, False, None, "error"))
    mock_get_adapter.return_value = adapter
    
    engine.circuit_breakers.record_failure("mock_test")
    engine.circuit_breakers.record_failure("mock_test")
    engine.circuit_breakers.record_failure("mock_test") # 3 failures open it
    
    res = engine.fetch_one("mock_test", use_cache=False)
    assert res is not None
    assert res.success is False
    assert res.error == "circuit breaker OPEN"
    assert adapter.fetch.call_count == 0

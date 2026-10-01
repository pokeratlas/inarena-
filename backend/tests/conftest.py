import pytest


@pytest.fixture(autouse=True)
def enable_test_legacy_api(monkeypatch):
    monkeypatch.setenv("INARENA_ENABLE_LEGACY_API", "1")

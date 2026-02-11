from __future__ import annotations

from shared.feature_flags.flags import FeatureFlagStore
from shared.feature_flags.provider import DictFlagProvider, EnvFlagProvider


def test_feature_flags_default_off() -> None:
    store = FeatureFlagStore(provider=DictFlagProvider(values={}))
    assert store.enabled("new_home") is False


def test_feature_flags_override_via_provider() -> None:
    store = FeatureFlagStore(provider=DictFlagProvider(values={"new_home": True}))
    assert store.enabled("new_home") is True


def test_feature_flags_env_override(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_FLAG_NEW_HOME", "1")
    store = FeatureFlagStore(provider=EnvFlagProvider())
    assert store.enabled("new_home") is True


def test_feature_flags_do_not_bypass_permission_gate() -> None:
    store = FeatureFlagStore(provider=DictFlagProvider(values={"unsafe_feature": True}))
    assert store.enabled("unsafe_feature") is True
    assert store.ensure_permission_gate(permission_allowed=False) is False

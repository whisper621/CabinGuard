from cabinguard.memory import SessionMemoryExecutor
from cabinguard.preference_store import PreferenceStore
from cabinguard.session import SessionStore
from cabinguard.tools import ToolContext


def test_consent_bound_preference_can_be_viewed_forgotten_and_revoked(tmp_path) -> None:
    preferences = PreferenceStore(tmp_path / "preferences.sqlite3")
    profile_id = "browser-profile-0001"

    assert preferences.list(profile_id) == {}
    preferences.grant(profile_id, ttl_days=30)
    assert preferences.set(profile_id, "temperature", "22") is True
    assert preferences.list(profile_id) == {"temperature": "22"}
    assert preferences.forget(profile_id, "temperature") is True
    assert preferences.list(profile_id) == {}
    preferences.set(profile_id, "fragrance", "forest")
    preferences.revoke(profile_id)
    assert preferences.has_consent(profile_id) is False
    assert preferences.list(profile_id) == {}


def test_memory_executor_uses_durable_scope_only_after_consent(tmp_path) -> None:
    store = SessionStore()
    preferences = PreferenceStore(tmp_path / "preferences.sqlite3")
    profile_id = "browser-profile-0002"
    preferences.grant(profile_id)
    session = store.create_session(memory_profile_id=profile_id, memory_consent=True)
    executor = SessionMemoryExecutor(store, preferences)

    result = executor.execute(
        "manage_preferences",
        {"action": "remember", "key": "temperature", "value": "22"},
        session,
        ToolContext(memory_write_authorized=True),
    )

    assert result.status == "success"
    assert result.output["scope"] == "consented_local_profile"
    assert preferences.list(profile_id) == {"temperature": "22"}

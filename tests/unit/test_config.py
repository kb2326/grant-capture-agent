from app.config import Settings, load_secret


def test_defaults_match_pinned_models(monkeypatch):
    for var in ("MODEL_AGENT", "MODEL_GRADER", "MODEL_DRAFTER", "MODEL_EMBEDDING"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.google_cloud_project == "grant-capture-agent"
    assert s.model_agent == "gemini-3.8-flash"
    assert s.model_grader == "gemini-3.5-flash-lite"
    assert s.model_drafter == "gemini-3.1-pro-preview"
    assert s.model_embedding == "gemini-embedding-001"
    assert s.embedding_dim == 768
    assert s.embedding_location == "us-central1"
    assert s.sam_daily_request_budget == 8


def test_env_overrides_and_secret_masking(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h:1/d")
    monkeypatch.setenv("SAM_API_KEY", "abc123")
    s = Settings(_env_file=None)
    assert s.database_url == "postgresql+psycopg://u:p@h:1/d"
    assert s.sam_api_key is not None
    assert s.sam_api_key.get_secret_value() == "abc123"
    assert "abc123" not in repr(s)


class _FakeSM:
    def __init__(self, value):
        self.value, self.calls = value, []

    def access_secret_version(self, name):
        self.calls.append(name)
        if self.value is None:
            raise KeyError(name)

        class R:
            pass

        r = R()
        r.payload = R()
        r.payload.data = self.value.encode()
        return r


def test_load_secret_reads_latest_version():
    sm = _FakeSM("s3cret")
    assert load_secret("sam-api-key", "grant-capture-agent", client=sm) == "s3cret"
    assert sm.calls == [
        "projects/grant-capture-agent/secrets/sam-api-key/versions/latest"
    ]


def test_load_secret_missing_returns_none():
    assert load_secret("nope", "p", client=_FakeSM(None)) is None


def test_db_password_placeholder_is_substituted(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://u:$(DB_PASSWORD)@/d?host=/cloudsql/x"
    )
    monkeypatch.setenv("DB_PASSWORD", "pw")
    assert (
        Settings(_env_file=None).database_url
        == "postgresql+psycopg://u:pw@/d?host=/cloudsql/x"
    )

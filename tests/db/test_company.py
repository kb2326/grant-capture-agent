import json
from pathlib import Path

import pytest
from sqlalchemy import select

from db.models import CompanyRow
from ingest.company import seed_company

pytestmark = pytest.mark.db


def test_seed_is_idempotent(db_session, tmp_path: Path):
    p = tmp_path / "profile.json"
    p.write_text(
        json.dumps({"name": "Lumen Grid Labs", "employees": 32}), encoding="utf-8"
    )
    first = seed_company(db_session, p)
    p.write_text(
        json.dumps({"name": "Lumen Grid Labs", "employees": 33}), encoding="utf-8"
    )
    second = seed_company(db_session, p)
    rows = db_session.scalars(select(CompanyRow)).all()
    assert first == second and len(rows) == 1 and rows[0].profile["employees"] == 33


def test_real_profile_has_rule_facts():
    profile = json.loads(Path("data/company/profile.json").read_text(encoding="utf-8"))
    for key in (
        "entity_type",
        "employees",
        "us_ownership_pct",
        "state",
        "sam_registered",
        "uei",
        "sbir_awards",
    ):
        assert key in profile
    assert profile["synthetic"] is True

import json
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import CompanyRow


def seed_company(session: Session, profile_path: Path) -> uuid.UUID:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    row = session.scalar(select(CompanyRow).where(CompanyRow.name == profile["name"]))
    if row is None:
        row = CompanyRow(name=profile["name"], profile=profile)
        session.add(row)
    else:
        row.profile = profile
    session.commit()
    return row.id

# tests/unit/test_company_docs.py
import re
from pathlib import Path

DOCS = Path("data/company/docs")
DISCLAIMER = "> Synthetic document for grant-capture-agent evaluation."
EXPECTED = {
    "capability-statement.md": 600,
    "past-proposal-01-doe-bms-technical.md": 900,
    "past-proposal-02-doe-bms-commercialization.md": 600,
    "past-proposal-03-nsf-gfm-project-description.md": 900,
    "past-proposal-04-nsf-gfm-key-personnel.md": 400,
    "past-proposal-05-facilities-equipment.md": 400,
    "project-report-01-doe-phase1-final.md": 800,
    "project-report-02-nsf-phase1-final.md": 800,
    "project-report-03-heliolink-field-pilot.md": 600,
    "bio-01-maya-okafor.md": 250,
    "bio-02-ravi-deshmukh.md": 250,
    "bio-03-elena-brandt.md": 250,
    "bio-04-jordan-lee.md": 250,
}


def test_all_documents_present_with_disclaimer_and_length():
    for name, words in EXPECTED.items():
        text = (DOCS / name).read_text(encoding="utf-8")
        assert text.startswith(DISCLAIMER), name
        n = len(text.split())
        assert 0.8 * words <= n <= 1.2 * words, f"{name}: {n} words"


def test_contact_details_are_obviously_fake():
    for path in DOCS.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for email in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
            assert email.endswith("@example.com"), (path.name, email)
        for phone in re.findall(r"\b\d{3}-\d{3}-\d{4}\b", text):
            assert phone.split("-")[1] == "555", (path.name, phone)


def test_known_gaps_stay_gaps():
    corpus = " ".join(p.read_text(encoding="utf-8").lower() for p in DOCS.glob("*.md"))
    for topic in ("hydrogen", "cybersecurity", "offshore wind"):
        assert topic not in corpus, topic

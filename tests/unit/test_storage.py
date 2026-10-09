from pathlib import Path

from ingest.storage import LocalBlobStore, is_allowed_attachment, safe_key


def test_safe_key_blocks_traversal_and_odd_names():
    assert (
        safe_key("grants_gov", "123", "../../etc/passwd")
        == "raw/grants_gov/123/etc_passwd"
    )
    assert (
        safe_key("sam_gov", "abc", "Résumé (final).PDF")
        == "raw/sam_gov/abc/R_sum_final_.PDF"
    )
    assert safe_key("sam_gov", "abc", "") == "raw/sam_gov/abc/unnamed"
    assert safe_key("sam_gov", "../x", "a.pdf") == "raw/sam_gov/x/a.pdf"


def test_allowed_attachments():
    assert is_allowed_attachment("application/pdf", "nofo.pdf")
    assert is_allowed_attachment(None, "Section_C.docx")
    assert not is_allowed_attachment("application/zip", "all.zip")
    assert not is_allowed_attachment(None, "budget.xlsx")


def test_local_store_round_trip(tmp_path: Path):
    store = LocalBlobStore(tmp_path)
    key = safe_key("grants_gov", "1", "a.pdf")
    assert not store.exists(key)
    uri = store.put(key, b"data")
    assert store.exists(key)
    assert uri.startswith("file:")
    assert (tmp_path / key).read_bytes() == b"data"


def test_generic_mime_falls_back_to_suffix():
    assert is_allowed_attachment("application/octet-stream", "nofo.pdf")
    assert not is_allowed_attachment("application/octet-stream", "data.bin")

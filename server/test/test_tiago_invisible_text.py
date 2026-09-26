from __future__ import annotations

import secrets

import pymupdf
import pytest

from tiago_invisible_text import TiagoInvisibleText
from watermarking_method import InvalidKeyError, SecretNotFoundError, WatermarkingError

SECRET = secrets.token_urlsafe(16)
KEY = secrets.token_urlsafe(32)


@pytest.fixture(scope="module")
def method() -> TiagoInvisibleText:
    return TiagoInvisibleText()


@pytest.fixture(scope="module")
def pdf_bytes() -> bytes:
    with pymupdf.open() as doc:
        for i in range(3):
            doc.new_page().insert_text((72, 72), f"Confidential page {i + 1}")
        return doc.tobytes()


@pytest.fixture(scope="module")
def watermarked(method, pdf_bytes) -> bytes:
    return method.add_watermark(pdf_bytes, SECRET, KEY)


def _strip_catalog_key(data: bytes) -> bytes:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        doc.xref_set_key(doc.pdf_catalog(), "TWMark", "null")
        return doc.tobytes()


def test_roundtrip(method, watermarked):
    assert method.read_secret(watermarked, KEY) == SECRET


def test_is_deterministic(method, pdf_bytes, watermarked):
    assert method.add_watermark(pdf_bytes, SECRET, KEY) == watermarked


def test_visible_content_is_preserved(watermarked):
    with pymupdf.open(stream=watermarked, filetype="pdf") as doc:
        assert doc.page_count == 3
        assert "Confidential page 2" in doc[1].get_text()


def test_secret_is_not_stored_in_clear(watermarked):
    assert SECRET.encode() not in watermarked
    with pymupdf.open(stream=watermarked, filetype="pdf") as doc:
        assert all(SECRET not in page.get_text() for page in doc)


def test_wrong_key_is_rejected(method, watermarked):
    with pytest.raises(InvalidKeyError):
        method.read_secret(watermarked, "wrong key")


def test_unwatermarked_pdf_has_no_secret(method, pdf_bytes):
    with pytest.raises(SecretNotFoundError):
        method.read_secret(pdf_bytes, KEY)


def test_survives_catalog_scrubbing(method, watermarked):
    assert method.read_secret(_strip_catalog_key(watermarked), KEY) == SECRET


def test_survives_copying_pages_into_new_document(method, watermarked):
    with pymupdf.open(stream=watermarked, filetype="pdf") as src, pymupdf.open() as dst:
        dst.insert_pdf(src)
        copied = dst.tobytes(garbage=4, deflate=True)
    assert method.read_secret(copied, KEY) == SECRET


def test_survives_extracting_a_single_page(method, watermarked):
    with pymupdf.open(stream=watermarked, filetype="pdf") as doc:
        doc.select([2])
        single = doc.tobytes(garbage=4)
    assert method.read_secret(_strip_catalog_key(single), KEY) == SECRET


def test_rewatermarking_keeps_each_key_readable(method, watermarked):
    twice = method.add_watermark(watermarked, "second recipient", "other key")
    assert method.read_secret(twice, "other key") == "second recipient"
    assert method.read_secret(twice, KEY) == SECRET


def test_zero_page_pdf_is_not_applicable(method):
    tiny = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
    assert method.is_watermark_applicable(tiny) is False
    with pytest.raises(WatermarkingError):
        method.add_watermark(tiny, SECRET, KEY)


@pytest.mark.parametrize("secret,key", [("", KEY), (SECRET, ""), ("x" * 513, KEY)])
def test_invalid_inputs_are_rejected(method, pdf_bytes, secret, key):
    with pytest.raises(ValueError):
        method.add_watermark(pdf_bytes, secret, key)

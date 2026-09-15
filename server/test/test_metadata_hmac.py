import fitz
import pytest

from metadata_hmac import (
    MetadataHMAC,
    InvalidKeyError,
    SecretNotFoundError,
)


@pytest.fixture
def pdf_bytes():
    document = fitz.open()
    document.new_page()
    data = document.tobytes()
    document.close()
    return data


def test_roundtrip(pdf_bytes):
    method = MetadataHMAC()

    watermarked = method.add_watermark(
        pdf_bytes,
        secret="my-secret",
        key="my-key",
    )

    assert method.read_secret(watermarked, "my-key") == "my-secret"


def test_wrong_key_rejected(pdf_bytes):
    method = MetadataHMAC()

    watermarked = method.add_watermark(
        pdf_bytes,
        secret="my-secret",
        key="my-key",
    )

    with pytest.raises(InvalidKeyError):
        method.read_secret(watermarked, "wrong-key")


def test_missing_watermark(pdf_bytes):
    method = MetadataHMAC()

    with pytest.raises(SecretNotFoundError):
        method.read_secret(pdf_bytes, "my-key")


def test_deterministic(pdf_bytes):
    method = MetadataHMAC()

    first = method.add_watermark(
        pdf_bytes,
        secret="my-secret",
        key="my-key",
    )
    second = method.add_watermark(
        pdf_bytes,
        secret="my-secret",
        key="my-key",
    )

    assert first == second


def test_applicable_pdf(pdf_bytes):
    method = MetadataHMAC()

    assert method.is_watermark_applicable(pdf_bytes)


def test_empty_secret_rejected(pdf_bytes):
    method = MetadataHMAC()

    with pytest.raises(ValueError):
        method.add_watermark(
            pdf_bytes,
            secret="",
            key="my-key",
        )

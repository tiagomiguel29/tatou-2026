import pytest
import pikepdf

from secret_in_producer import SecretInProducer


@pytest.mark.parametrize(
    "secret, key",
    [
        pytest.param("", "valid-key", id="empty-secret"),
        pytest.param(None, "valid-key", id="none-secret"),
        pytest.param("valid-secret", "", id="empty-key"),
        pytest.param("valid-secret", None, id="none-key"),
        pytest.param("valid-secret", 123, id="non-string-key"),
    ],
)
def test_add_watermark_rejects_invalid_secret_or_key(secret, key):
    method = SecretInProducer()

    with pytest.raises(ValueError):
        method.add_watermark(None, secret=secret, key=key)


def test_add_watermark_rejects_invalid_pdf(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_DIR", str(tmp_path))
    invalid_pdf = tmp_path / "invalid.pdf"
    invalid_pdf.write_bytes(b"This is not a PDF")

    with pytest.raises(pikepdf.PdfError):
        SecretInProducer().add_watermark(
            invalid_pdf,
            secret="valid-secret",
            key="valid-key",
        )

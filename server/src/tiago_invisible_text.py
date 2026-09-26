import base64
import hashlib
import hmac
import re

import pymupdf

from watermarking_method import (
    InvalidKeyError,
    PdfSource,
    SecretNotFoundError,
    WatermarkingError,
    WatermarkingMethod,
    load_pdf_bytes,
)


class TiagoInvisibleText(WatermarkingMethod):
    name = "tiago-invisible-text"

    _SALT = b"tatou:tiago-invisible-text"
    _MAX_SECRET_BYTES = 512
    _CATALOG_KEY = "TWMark"
    _PREFIX = "TWM:"
    _TOKEN_RE = re.compile(r"TWM:([A-Za-z0-9_-]+)")

    @staticmethod
    def get_usage() -> str:
        return "Hides the encrypted secret as invisible text on every page."

    def is_watermark_applicable(self, pdf: PdfSource, position: str | None = None) -> bool:
        data = load_pdf_bytes(pdf)
        try:
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                return not doc.needs_pass and doc.page_count > 0
        except Exception:
            return False

    def add_watermark(self, pdf: PdfSource, secret: str, key: str, position: str | None = None) -> bytes:
        data = load_pdf_bytes(pdf)
        if not (isinstance(secret, str) and secret and isinstance(key, str) and key):
            raise ValueError("Secret and key must be non-empty strings")
        if len(secret.encode()) > self._MAX_SECRET_BYTES:
            raise ValueError(f"Secret must be at most {self._MAX_SECRET_BYTES} bytes")
        if not self.is_watermark_applicable(data):
            raise WatermarkingError("PDF must be unencrypted and have at least one page")

        token = self._seal(secret, key)
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            doc.xref_set_key(doc.pdf_catalog(), self._CATALOG_KEY, f"({token})")
            for page in doc:
                page.insert_text(page.rect.top_left + (2, 2), self._PREFIX + token, fontsize=1, render_mode=3)
            return doc.tobytes(no_new_id=True)

    def read_secret(self, pdf: PdfSource, key: str) -> str:
        data = load_pdf_bytes(pdf)
        if not isinstance(key, str) or not key:
            raise ValueError("Key must be a non-empty string")

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            kind, value = doc.xref_get_key(doc.pdf_catalog(), self._CATALOG_KEY)
            tokens = [value] if kind == "string" else []
            for page in doc:
                tokens += self._TOKEN_RE.findall(page.get_text())
        if not tokens:
            raise SecretNotFoundError("No watermark found")

        enc_key, mac_key = self._derive_keys(key)
        for token in tokens:
            secret = self._open(token, enc_key, mac_key)
            if secret is not None:
                return secret
        raise InvalidKeyError("Key failed to authenticate the watermark")

    def _derive_keys(self, key: str) -> tuple[bytes, bytes]:
        material = hashlib.pbkdf2_hmac("sha256", key.encode(), self._SALT, 100_000, dklen=64)
        return material[:32], material[32:]

    @staticmethod
    def _xor(enc_key: bytes, iv: bytes, data: bytes) -> bytes:
        stream = b"".join(
            hmac.digest(enc_key, iv + i.to_bytes(4, "big"), "sha256") for i in range(len(data) // 32 + 1)
        )
        return bytes(a ^ b for a, b in zip(data, stream))

    def _seal(self, secret: str, key: str) -> str:
        enc_key, mac_key = self._derive_keys(key)
        plaintext = secret.encode()
        iv = hmac.digest(mac_key, plaintext, "sha256")
        return base64.urlsafe_b64encode(iv + self._xor(enc_key, iv, plaintext)).rstrip(b"=").decode()

    def _open(self, token: str, enc_key: bytes, mac_key: bytes) -> str | None:
        try:
            raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        except ValueError:
            return None
        iv, ciphertext = raw[:32], raw[32:]
        plaintext = self._xor(enc_key, iv, ciphertext)
        if not hmac.compare_digest(iv, hmac.digest(mac_key, plaintext, "sha256")):
            return None
        return plaintext.decode()

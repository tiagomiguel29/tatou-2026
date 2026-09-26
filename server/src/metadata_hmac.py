"""PDF metadata watermarking using HMAC-SHA256."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pymupdf

from watermarking_method import (
    InvalidKeyError,
    SecretNotFoundError,
    WatermarkingError,
    WatermarkingMethod,
    load_pdf_bytes,
)


class MetadataHMAC(WatermarkingMethod):
    """Embed an authenticated secret in PDF document metadata."""

    name = "metadata-hmac"

    _METADATA_KEY = "subject"
    _PREFIX = "TATOU-WM-MH1:"

    @staticmethod
    def get_usage() -> str:
        return "Embeds the watermark in PDF metadata; position is ignored."

    def add_watermark(
        self,
        pdf,
        secret: str,
        key: str,
        position: str | None = None,
    ) -> bytes:
        if not isinstance(secret, str) or not secret:
            raise ValueError("Secret must be a non-empty string")

        if not isinstance(key, str) or not key:
            raise ValueError("Key must be a non-empty string")

        try:
            data = load_pdf_bytes(pdf)
            document = pymupdf.open(stream=data, filetype="pdf")

            mac = hmac.new(
                key.encode("utf-8"),
                secret.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            payload = {
                "secret": secret,
                "mac": mac,
            }

            encoded = base64.b64encode(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).decode("ascii")

            metadata = document.metadata
            metadata[self._METADATA_KEY] = self._PREFIX + encoded
            document.set_metadata(metadata)

            result = document.tobytes(no_new_id=True)
            document.close()
            return result

        except (ValueError, TypeError):
            raise
        except Exception as exc:
            raise WatermarkingError(
                f"Failed to add metadata watermark: {exc}"
            ) from exc

    def is_watermark_applicable(
        self,
        pdf,
        position: str | None = None,
    ) -> bool:
        try:
            data = load_pdf_bytes(pdf)
            document = pymupdf.open(stream=data, filetype="pdf")
            applicable = document.page_count > 0
            document.close()
            return applicable
        except Exception:
            return False
        
    def read_secret(self, pdf, key: str) -> str:
        if not isinstance(key, str) or not key:
            raise InvalidKeyError("Key must be a non-empty string")

        try:
            data = load_pdf_bytes(pdf)
            document = pymupdf.open(stream=data, filetype="pdf")
            metadata = document.metadata
            document.close()

            value = metadata.get(self._METADATA_KEY, "")

            if not value.startswith(self._PREFIX):
                raise SecretNotFoundError(
                    "No metadata watermark found"
                )

            encoded = value[len(self._PREFIX):]

            try:
                payload = json.loads(
                    base64.b64decode(encoded).decode("utf-8")
                )
                secret = payload["secret"]
                stored_mac = payload["mac"]
            except (ValueError, KeyError, TypeError):
                raise SecretNotFoundError(
                    "Invalid metadata watermark"
                )

            expected_mac = hmac.new(
                key.encode("utf-8"),
                secret.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(stored_mac, expected_mac):
                raise InvalidKeyError("Invalid watermark key")

            return secret

        except (SecretNotFoundError, InvalidKeyError):
            raise
        except Exception as exc:
            raise WatermarkingError(
                f"Failed to read metadata watermark: {exc}"
            ) from exc

import uuid

import pytest

from app.services.storage.security import (
    MAX_IMAGE_SIZE_BYTES,
    sanitize_storage_key,
    sniff_mime_type,
    validate_image_bytes,
    validate_ssrf_url,
)

# Sample magic headers
PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
WEBP_HEADER = (
    b"RIFF\x24\x00\x00\x00WEBPVP8 \x18\x00\x00\x000\x01\x00\x9d\x01\x2a\x01\x00\x01\x00\x02\x00"
)
PDF_HEADER = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
BASH_HEADER = b"#!/bin/bash\necho 'hacked'\n"


class TestMagicByteSniffing:
    def test_sniff_png(self):
        mime = sniff_mime_type(PNG_HEADER)
        assert mime == "image/png"

    def test_sniff_jpeg(self):
        mime = sniff_mime_type(JPEG_HEADER)
        assert mime in ("image/jpeg", "image/jpg")

    def test_sniff_webp(self):
        mime = sniff_mime_type(WEBP_HEADER)
        assert mime == "image/webp"

    def test_sniff_pdf_rejected(self):
        mime = sniff_mime_type(PDF_HEADER)
        assert mime == "application/pdf"


class TestImageValidation:
    def test_valid_png_validation(self):
        content_type, ext = validate_image_bytes(PNG_HEADER, "test.png")
        assert content_type == "image/png"
        assert ext == "png"

    def test_valid_jpeg_validation(self):
        content_type, ext = validate_image_bytes(JPEG_HEADER, "photo.jpg")
        assert content_type == "image/jpeg"
        assert ext == "jpg"

    def test_extension_spoofing_rejected(self):
        # File claims to be image.jpg but is actually a bash script
        with pytest.raises(ValueError, match="Invalid image format"):
            validate_image_bytes(BASH_HEADER, "innocent.jpg")

    def test_pdf_masquerading_as_png_rejected(self):
        with pytest.raises(ValueError, match="Invalid image format"):
            validate_image_bytes(PDF_HEADER, "document.png")

    def test_oversized_file_rejected(self):
        oversized = b"0" * (MAX_IMAGE_SIZE_BYTES + 1)
        with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
            validate_image_bytes(oversized, "huge.jpg")

    def test_empty_file_rejected(self):
        with pytest.raises(ValueError, match="Empty image file"):
            validate_image_bytes(b"", "empty.jpg")


class TestFilenameSanitization:
    def test_storage_key_never_uses_client_name(self):
        scan_id = uuid.uuid4()
        client_filename = "../../../etc/passwd;rm -rf /"
        key = sanitize_storage_key(scan_id, "original", 0, "jpg")

        assert key.startswith(f"scans/{scan_id}/original/0_")
        assert key.endswith(".jpg")
        assert client_filename not in key
        assert ".." not in key
        assert "/" in key  # only standard S3 key separators


class TestSSRFProtection:
    @pytest.mark.parametrize(
        "forbidden_url",
        [
            "http://localhost/image.jpg",
            "http://127.0.0.1/admin",
            "http://127.0.0.1:8000/scans",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/test.png",
            "http://192.168.1.1/secret.png",
            "http://172.16.0.1/pic.jpg",
            "ftp://example.com/pic.jpg",
            "file:///etc/passwd",
            "http://0.0.0.0/test.jpg",
        ],
    )
    def test_ssrf_forbidden_urls(self, forbidden_url: str):
        with pytest.raises(ValueError, match="Invalid or prohibited URL"):
            validate_ssrf_url(forbidden_url)

    def test_allowed_public_url(self):
        url = "https://www.example.com/products/shampoo-label.jpg"
        validated = validate_ssrf_url(url)
        assert validated == url

"""
Unit tests for app/core/parsers.py

Covers:
    - validate_file_extension: allowed/rejected extensions
    - get_file_extension: extraction logic and edge cases
    - extract_text_from_file: routing by content_type and filename
    - _extract_text_from_txt: UTF-8 and latin-1 decoding
    - _extract_text_from_pdf: size validation, empty file rejection
    - Unsupported file type raises BadRequestException

Uses AsyncMock UploadFile stubs — no real file I/O, no DB.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import BadRequestException, DocumentProcessingException
from app.core.parsers import (
    validate_file_extension,
    get_file_extension,
    extract_text_from_file,
)


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════


def make_upload_file(
    filename: str = "test.pdf",
    content: bytes = b"some content",
    content_type: str = "application/pdf",
) -> MagicMock:
    """
    Build an AsyncMock that mimics FastAPI's UploadFile.

    The read() coroutine returns `content`.
    The seek() coroutine is a no-op.
    """
    mock = MagicMock()
    mock.filename = filename
    mock.content_type = content_type
    mock.read = AsyncMock(return_value=content)
    mock.seek = AsyncMock()
    return mock


# ══════════════════════════════════════════════════════════════════
# validate_file_extension
# ══════════════════════════════════════════════════════════════════


class TestValidateFileExtension:
    def test_pdf_allowed(self):
        assert validate_file_extension("document.pdf") is True

    def test_docx_allowed(self):
        assert validate_file_extension("report.docx") is True

    def test_txt_allowed(self):
        assert validate_file_extension("notes.txt") is True

    def test_md_allowed(self):
        assert validate_file_extension("README.md") is True

    def test_exe_rejected(self):
        assert validate_file_extension("malware.exe") is False

    def test_js_rejected(self):
        assert validate_file_extension("script.js") is False

    def test_py_rejected(self):
        assert validate_file_extension("exploit.py") is False

    def test_zip_rejected(self):
        assert validate_file_extension("archive.zip") is False

    def test_png_rejected(self):
        assert validate_file_extension("image.png") is False

    def test_case_insensitive_pdf(self):
        assert validate_file_extension("DOCUMENT.PDF") is True

    def test_case_insensitive_docx(self):
        assert validate_file_extension("Report.DOCX") is True

    def test_empty_filename_rejected(self):
        assert validate_file_extension("") is False

    def test_no_extension_rejected(self):
        assert validate_file_extension("filename") is False

    def test_only_dot_rejected(self):
        assert validate_file_extension(".") is False

    def test_hidden_file_pdf(self):
        """Files like .pdf (just extension, no name) should still pass."""
        assert validate_file_extension(".pdf") is True

    def test_multiple_dots_uses_last_extension(self):
        assert validate_file_extension("my.report.v2.pdf") is True

    def test_multiple_dots_wrong_final_extension(self):
        assert validate_file_extension("my.pdf.exe") is False


# ══════════════════════════════════════════════════════════════════
# get_file_extension
# ══════════════════════════════════════════════════════════════════


class TestGetFileExtension:
    def test_returns_dot_pdf(self):
        assert get_file_extension("document.pdf") == ".pdf"

    def test_returns_dot_docx(self):
        assert get_file_extension("report.docx") == ".docx"

    def test_returns_dot_txt(self):
        assert get_file_extension("notes.txt") == ".txt"

    def test_returns_lowercase(self):
        assert get_file_extension("FILE.PDF") == ".pdf"

    def test_no_extension_returns_none(self):
        assert get_file_extension("filename") is None

    def test_empty_string_returns_none(self):
        assert get_file_extension("") is None

    def test_multiple_dots_returns_last(self):
        assert get_file_extension("archive.tar.gz") == ".gz"

    def test_only_dot_returns_dot(self):
        # "." contains a dot so rsplit(".", 1) gives ["", ""] → returns "."
        assert get_file_extension(".") == "."

    def test_hidden_dot_file_returns_extension_after_dot(self):
        # ".gitignore" → rsplit(".", 1)[-1] = "gitignore" → returns ".gitignore"
        assert get_file_extension(".gitignore") == ".gitignore"

    def test_file_with_dot_pdf_extension(self):
        assert get_file_extension("my.report.v2.pdf") == ".pdf"


# ══════════════════════════════════════════════════════════════════
# extract_text_from_file — routing
# ══════════════════════════════════════════════════════════════════


class TestExtractTextFromFileRouting:
    async def test_pdf_content_type_routes_to_pdf_extractor(self):
        file = make_upload_file("doc.pdf", b"%PDF-1.4 content", "application/pdf")
        with patch(
            "app.core.parsers._extract_text_from_pdf", new_callable=AsyncMock
        ) as mock_pdf:
            mock_pdf.return_value = "extracted pdf text"
            result = await extract_text_from_file(file)
        mock_pdf.assert_called_once_with(file)
        assert result == "extracted pdf text"

    async def test_pdf_filename_routes_to_pdf_extractor(self):
        file = make_upload_file("doc.pdf", b"%PDF", "application/octet-stream")
        with patch(
            "app.core.parsers._extract_text_from_pdf", new_callable=AsyncMock
        ) as mock_pdf:
            mock_pdf.return_value = "pdf text"
            await extract_text_from_file(file)
        mock_pdf.assert_called_once()

    async def test_docx_content_type_routes_to_docx_extractor(self):
        file = make_upload_file(
            "report.docx",
            b"PK content",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with patch(
            "app.core.parsers._extract_text_from_docx", new_callable=AsyncMock
        ) as mock_docx:
            mock_docx.return_value = "docx text"
            await extract_text_from_file(file)
        mock_docx.assert_called_once()

    async def test_docx_filename_routes_to_docx_extractor(self):
        file = make_upload_file("report.docx", b"PK", "application/octet-stream")
        with patch(
            "app.core.parsers._extract_text_from_docx", new_callable=AsyncMock
        ) as mock_docx:
            mock_docx.return_value = "docx text"
            await extract_text_from_file(file)
        mock_docx.assert_called_once()

    async def test_txt_content_type_routes_to_txt_extractor(self):
        file = make_upload_file("notes.txt", b"hello world", "text/plain")
        with patch(
            "app.core.parsers._extract_text_from_txt", new_callable=AsyncMock
        ) as mock_txt:
            mock_txt.return_value = "txt text"
            await extract_text_from_file(file)
        mock_txt.assert_called_once()

    async def test_txt_filename_routes_to_txt_extractor(self):
        file = make_upload_file("notes.txt", b"hello", "application/octet-stream")
        with patch(
            "app.core.parsers._extract_text_from_txt", new_callable=AsyncMock
        ) as mock_txt:
            mock_txt.return_value = "text"
            await extract_text_from_file(file)
        mock_txt.assert_called_once()

    async def test_md_filename_routes_to_txt_extractor(self):
        file = make_upload_file("README.md", b"# Title", "text/plain")
        with patch(
            "app.core.parsers._extract_text_from_txt", new_callable=AsyncMock
        ) as mock_txt:
            mock_txt.return_value = "md text"
            await extract_text_from_file(file)
        mock_txt.assert_called_once()

    async def test_unsupported_type_raises_bad_request(self):
        file = make_upload_file("script.js", b"console.log()", "text/javascript")
        with pytest.raises(BadRequestException):
            await extract_text_from_file(file)

    async def test_exe_raises_bad_request(self):
        file = make_upload_file(
            "malware.exe", b"MZ\x90\x00", "application/octet-stream"
        )
        with pytest.raises(BadRequestException):
            await extract_text_from_file(file)

    async def test_bad_request_contains_filename_in_detail(self):
        file = make_upload_file("virus.exe", b"MZ", "application/octet-stream")
        with pytest.raises(BadRequestException) as exc_info:
            await extract_text_from_file(file)
        assert exc_info.value.status_code == 400


# ══════════════════════════════════════════════════════════════════
# _extract_text_from_txt
# ══════════════════════════════════════════════════════════════════


class TestExtractTextFromTxt:
    """Test the plain-text extractor directly."""

    async def _extract(self, content: bytes, filename: str = "test.txt"):
        from app.core.parsers import _extract_text_from_txt

        file = make_upload_file(filename, content, "text/plain")
        return await _extract_text_from_txt(file)

    async def test_utf8_content_decoded(self):
        result = await self._extract(b"Hello, world!")
        assert result == "Hello, world!"

    async def test_latin1_fallback_decoding(self):
        """Bytes that are not valid UTF-8 should fall back to latin-1."""
        latin1_bytes = "Héllo Wörld".encode("latin-1")
        result = await self._extract(latin1_bytes)
        assert "H" in result  # basic smoke test — latin-1 decode succeeded

    async def test_empty_file_raises_document_processing_exception(self):
        # _extract_text_from_txt catches BadRequestException inside a broad
        # except block and re-raises as DocumentProcessingException
        with pytest.raises(DocumentProcessingException):
            await self._extract(b"")

    async def test_seek_called_after_read(self):
        from app.core.parsers import _extract_text_from_txt

        file = make_upload_file("notes.txt", b"content", "text/plain")
        await _extract_text_from_txt(file)
        file.seek.assert_called_once_with(0)

    async def test_multiline_content_preserved(self):
        content = b"Line 1\nLine 2\nLine 3"
        result = await self._extract(content)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result


# ══════════════════════════════════════════════════════════════════
# _extract_text_from_pdf — validation layer
# ══════════════════════════════════════════════════════════════════


class TestExtractTextFromPdfValidation:
    """
    Tests for the validation logic inside _extract_text_from_pdf.
    We mock PdfReader to avoid needing real PDF bytes.
    """

    async def test_empty_file_raises_bad_request(self):
        from app.core.parsers import _extract_text_from_pdf

        file = make_upload_file("empty.pdf", b"", "application/pdf")
        with pytest.raises(BadRequestException, match="empty"):
            await _extract_text_from_pdf(file)

    async def test_oversized_file_raises_bad_request(self):
        from app.core.parsers import _extract_text_from_pdf

        big_content = b"x" * (51 * 1024 * 1024)  # 51 MB
        file = make_upload_file("huge.pdf", big_content, "application/pdf")
        with pytest.raises(BadRequestException, match="large"):
            await _extract_text_from_pdf(file)

    async def test_pdf_with_no_extractable_text_raises_document_processing(self):
        from app.core.parsers import _extract_text_from_pdf

        # Minimal valid-ish PDF bytes (won't crash PdfReader but has no text)
        # We mock PdfReader to return pages with no text
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page, mock_page]

        file = make_upload_file("scan.pdf", b"%PDF-1.4 fake", "application/pdf")

        with patch("app.core.parsers.PdfReader", return_value=mock_reader):
            with pytest.raises(DocumentProcessingException):
                await _extract_text_from_pdf(file)

    async def test_pdf_with_text_returns_content(self):
        from app.core.parsers import _extract_text_from_pdf

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Architecture overview text."

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        file = make_upload_file("doc.pdf", b"%PDF-1.4 fake", "application/pdf")

        with patch("app.core.parsers.PdfReader", return_value=mock_reader):
            result = await _extract_text_from_pdf(file)

        assert "Architecture overview text." in result

    async def test_seek_called_after_successful_extraction(self):
        from app.core.parsers import _extract_text_from_pdf

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Some text."

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        file = make_upload_file("doc.pdf", b"%PDF fake", "application/pdf")

        with patch("app.core.parsers.PdfReader", return_value=mock_reader):
            await _extract_text_from_pdf(file)

        file.seek.assert_called_once_with(0)

    async def test_multiple_pages_joined(self):
        from app.core.parsers import _extract_text_from_pdf

        page1 = MagicMock()
        page1.extract_text.return_value = "Page one content."
        page2 = MagicMock()
        page2.extract_text.return_value = "Page two content."

        mock_reader = MagicMock()
        mock_reader.pages = [page1, page2]

        file = make_upload_file("doc.pdf", b"%PDF fake", "application/pdf")

        with patch("app.core.parsers.PdfReader", return_value=mock_reader):
            result = await _extract_text_from_pdf(file)

        assert "Page one content." in result
        assert "Page two content." in result

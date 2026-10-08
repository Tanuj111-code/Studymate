"""Document ingestion: validate, extract and normalize text without persisting uploads."""
from io import BytesIO
import re
from pypdf import PdfReader

MAX_BYTES = 10 * 1024 * 1024


def extract_document(upload):
    raw = upload.read()
    if not raw:
        raise ValueError("The selected file is empty.")
    if len(raw) > MAX_BYTES:
        raise ValueError("Files must be 10 MB or smaller.")
    name = upload.filename or ""
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension == "txt":
        text = raw.decode("utf-8-sig", errors="replace")
    elif extension == "pdf":
        try:
            reader = PdfReader(BytesIO(raw))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            # Vision analysis can still read scanned PDFs and PDFs with broken text maps.
            text = ""
    else:
        raise ValueError("Please upload a PDF or TXT file.")
    text = re.sub(r"[\t\r ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(re.sub(r"\W", "", text)) < 80 and extension != "pdf":
        raise ValueError("Not enough readable text was found. Scanned PDFs need OCR before analysis.")
    return text


def is_readable_pdf_text(text):
    """Reject common broken-font/scanned-PDF extraction before showing a fake summary."""
    visible = [character for character in text if not character.isspace()]
    if len(visible) < 80:
        return False
    alpha_ratio = sum(character.isalpha() for character in visible) / len(visible)
    words = re.findall(r"[A-Za-z]{2,}", text)
    encoded_glyph_runs = re.search(r"(?:/\d{1,4}\s+){8,}", text)
    replacement_glyphs = sum(text.count(glyph) for glyph in ("\ufffd", "□", "�"))
    has_bad_encoding = bool(encoded_glyph_runs) or replacement_glyphs > max(3, int(len(text) * 0.015))
    return len(words) >= 15 and alpha_ratio >= 0.48 and not has_bad_encoding

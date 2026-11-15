
import fitz  # PyMuPDF
from pathlib import Path


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract readable text from a PDF resume.

    Args:
        pdf_path: Path to the uploaded PDF.

    Returns:
        All extracted page text as a single string.
    """

    file_path = Path(pdf_path)

    # Check whether the PDF exists.
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Resume PDF not found: {pdf_path}"
        )

    # Open the PDF safely.
    try:
        with fitz.open(str(file_path)) as document:

            if document.is_encrypted:
                raise ValueError(
                    "Password-protected PDFs are not supported."
                )

            if len(document) == 0:
                raise ValueError("The PDF contains no pages.")

            extracted_pages = []

            for page_number, page in enumerate(document, start=1):
                page_text = page.get_text("text").strip()

                if page_text:
                    extracted_pages.append(
                        f"--- Page {page_number} ---\n{page_text}"
                    )

            full_text = "\n\n".join(extracted_pages).strip()

            if not full_text:
                raise ValueError(
                    "No readable text found. "
                    "The PDF may be scanned and require OCR."
                )

            return full_text

    except fitz.FileDataError as exc:
        raise ValueError(
            "The uploaded file is not a valid readable PDF."
        ) from exc

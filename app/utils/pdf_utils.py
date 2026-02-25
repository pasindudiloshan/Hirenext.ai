# app/utils/pdf_utils.py
import fitz  # PyMuPDF

def extract_text_from_pdf(path: str) -> str:
    """
    Extract raw text from a PDF file using PyMuPDF.
    Returns a single combined string.
    """

    text_chunks = []

    try:
        doc = fitz.open(path)
        for page in doc:
            text_chunks.append(page.get_text())
        doc.close()
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""

    full_text = "\n".join(text_chunks)
    return full_text.strip()
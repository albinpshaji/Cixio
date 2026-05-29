from dataclasses import dataclass

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from app.chunking import chunk_text


@dataclass(frozen=True)
class PdfChunk:
    content: str
    source: str
    page: int
    chunk_index: int
    page_chunk_index: int


def extract_pdf_chunks(file: UploadFile) -> tuple[str, int, list[PdfChunk]]:
    filename = file.filename or "uploaded.pdf"

    if not filename.lower().endswith(".pdf") and file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Upload a PDF file.")

    try:
        file.file.seek(0)
        reader = PdfReader(file.file)

        if reader.is_encrypted:
            reader.decrypt("")
    except Exception as error:
        raise HTTPException(status_code=400, detail="Could not read the PDF file.") from error

    chunks: list[PdfChunk] = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        page_chunks = chunk_text(text)

        for page_chunk in page_chunks:
            chunks.append(
                PdfChunk(
                    content=page_chunk.content,
                    source=filename,
                    page=page_number,
                    chunk_index=len(chunks),
                    page_chunk_index=page_chunk.chunk_index,
                )
            )

    if not chunks:
        raise HTTPException(status_code=400, detail="No extractable text was found in the PDF.")

    return filename, len(reader.pages), chunks

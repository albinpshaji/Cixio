from dataclasses import dataclass
from fastapi import HTTPException, UploadFile
import io
import fitz  # PyMuPDF
from docx import Document
import pytesseract
from PIL import Image

from app.chunking import chunk_text

@dataclass(frozen=True)
class ProcessedChunk:
    content: str
    source: str
    page: int
    chunk_index: int
    page_chunk_index: int

def extract_document_chunks(file: UploadFile) -> tuple[str, int, list[ProcessedChunk]]:
    filename = file.filename or "uploaded_file"
    file_ext = filename.lower().split('.')[-1]
    
    text_content = ""
    pages = 1
    chunks: list[ProcessedChunk] = []

    try:
        content = file.file.read()
        file.file.seek(0)

        if file_ext == "pdf" or file.content_type == "application/pdf":
            doc = fitz.open(stream=content, filetype="pdf")
            pages = len(doc)
            for page_number, page in enumerate(doc, start=1):
                text = page.get_text() or ""
                page_chunks = chunk_text(text)
                for page_chunk in page_chunks:
                    chunks.append(
                        ProcessedChunk(
                            content=page_chunk.content,
                            source=filename,
                            page=page_number,
                            chunk_index=len(chunks),
                            page_chunk_index=page_chunk.chunk_index,
                        )
                    )
            return filename, pages, chunks

        elif file_ext in ["docx"]:
            doc = Document(io.BytesIO(content))
            text_content = "\n".join([para.text for para in doc.paragraphs])
            
        elif file_ext in ["txt"]:
            text_content = content.decode("utf-8", errors="ignore")
            
        elif file_ext in ["png", "jpg", "jpeg"]:
            image = Image.open(io.BytesIO(content))
            text_content = pytesseract.image_to_string(image)
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")

        doc_chunks = chunk_text(text_content)
        for doc_chunk in doc_chunks:
            chunks.append(
                ProcessedChunk(
                    content=doc_chunk.content,
                    source=filename,
                    page=1,
                    chunk_index=len(chunks),
                    page_chunk_index=doc_chunk.chunk_index,
                )
            )
            
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Could not process the file: {str(error)}") from error

    if not chunks:
        raise HTTPException(status_code=400, detail="No extractable text was found in the document.")

    return filename, pages, chunks

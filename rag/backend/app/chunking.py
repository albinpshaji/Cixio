from dataclasses import dataclass
import re


CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


@dataclass(frozen=True)
class DocumentChunk:
    content: str
    chunk_index: int


def normalize_text(text: str) -> str:
    normalized = text.replace("\r", "")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def chunk_text(text: str) -> list[DocumentChunk]:
    normalized = normalize_text(text)

    if not normalized:
        return []

    chunks: list[DocumentChunk] = []
    start = 0

    while start < len(normalized):
        target_end = min(start + CHUNK_SIZE, len(normalized))
        end = target_end

        if target_end < len(normalized):
            paragraph_break = normalized.rfind("\n\n", start, target_end)
            sentence_break = normalized.rfind(". ", start, target_end)
            word_break = normalized.rfind(" ", start, target_end)
            best_break = max(paragraph_break, sentence_break, word_break)

            if best_break > start + CHUNK_SIZE * 0.5:
                end = best_break + 1

        content = normalized[start:end].strip()

        if content:
            chunks.append(DocumentChunk(content=content, chunk_index=len(chunks)))

        if end >= len(normalized):
            break

        start = max(end - CHUNK_OVERLAP, start + 1)

    return chunks

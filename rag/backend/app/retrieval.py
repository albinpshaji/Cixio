from typing import Any

from app.config import settings
from app.db import pool
from app.ollama import create_embedding
from app.schemas import RetrievedChunk
from app.vector import to_pg_vector


def retrieve_relevant_chunks(question: str, sessionId: str | None = None, limit: int | None = None, user_id: str | None = None) -> list[RetrievedChunk]:
    embedding = create_embedding(question)
    vector = to_pg_vector(embedding)
    
    query_limit = limit if limit is not None else settings.retrieval_limit

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            if sessionId:
                # If user_id is provided, filter base_chunks by it
                user_filter = "AND user_id = %s::uuid" if user_id else ""
                params = [vector, sessionId]
                if user_id:
                    params.append(user_id)
                params.extend([sessionId, question, question, query_limit])

                cursor.execute(
                    f"""
                    WITH base_chunks AS (
                        SELECT
                            id,
                            content,
                            metadata,
                            (1 - (embedding <=> %s::vector)) AS base_similarity
                        FROM documents
                        WHERE embedding IS NOT NULL 
                          AND (metadata->>'sessionId' = %s OR metadata->>'sessionId' IS NULL OR metadata->>'sessionId' = 'null')
                          {user_filter}
                    )
                    SELECT
                        id,
                        content,
                        metadata,
                        (CASE 
                            WHEN metadata->>'sessionId' = %s THEN base_similarity + 0.03
                            ELSE base_similarity
                        END) + (CASE 
                            WHEN metadata->>'source' IS NOT NULL AND (
                                LOWER(%s) LIKE '%%' || LOWER(REPLACE(REPLACE(metadata->>'source', '.pdf', ''), '.txt', '')) || '%%'
                                OR LOWER(metadata->>'source') LIKE '%%' || LOWER(%s) || '%%'
                            ) THEN 0.12
                            ELSE 0.0
                        END) AS similarity
                    FROM base_chunks
                    ORDER BY similarity DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
            else:
                user_filter = "AND user_id = %s::uuid" if user_id else ""
                params = [vector]
                if user_id:
                    params.append(user_id)
                params.extend([question, question, query_limit])

                cursor.execute(
                    f"""
                    WITH base_chunks AS (
                        SELECT
                            id,
                            content,
                            metadata,
                            (1 - (embedding <=> %s::vector)) AS base_similarity
                        FROM documents
                        WHERE embedding IS NOT NULL 
                          AND (metadata->>'sessionId' IS NULL OR metadata->>'sessionId' = 'null')
                          {user_filter}
                    )
                    SELECT
                        id,
                        content,
                        metadata,
                        base_similarity + (CASE 
                            WHEN metadata->>'source' IS NOT NULL AND (
                                LOWER(%s) LIKE '%%' || LOWER(REPLACE(REPLACE(metadata->>'source', '.pdf', ''), '.txt', '')) || '%%'
                                OR LOWER(metadata->>'source') LIKE '%%' || LOWER(%s) || '%%'
                            ) THEN 0.12
                            ELSE 0.0
                        END) AS similarity
                    FROM base_chunks
                    ORDER BY similarity DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
            rows: list[tuple[int, str, dict[str, Any] | None, float]] = cursor.fetchall()

    return [
        RetrievedChunk(
            id=row[0],
            content=row[1],
            metadata=row[2],
            similarity=float(row[3]),
        )
        for row in rows
    ]

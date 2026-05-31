import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import asyncio
from app.db import pool, open_pool, close_pool
from app.retrieval import retrieve_relevant_chunks
from app.chroma_db import get_chroma_collection
from app.schemas import RetrievedChunk

def test_hybrid_search():
    open_pool()
    try:
        # Let's find an existing user_id from the database to run the query
        user_id = None
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users LIMIT 1;")
                row = cur.fetchone()
                if row:
                    user_id = str(row[0])
                else:
                    print("No users in the database! Please create a user or register.")
                    return
        
        print(f"Testing hybrid search for user: {user_id}")
        
        # Insert a temporary test chunk with a very unique alphanumeric code
        test_text = "SmartHub error key code ZX-9971-ALBIN: Critical memory core leakage. Shutdown systems immediately."
        print(f"Adding test text to database: '{test_text}'")
        
        # 1. Add to Postgres
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO documents (content, metadata, user_id) VALUES (%s, %s::jsonb, %s::uuid);",
                        (test_text, '{"source": "test_script.txt"}', user_id)
                    )
        
        # 2. Add to ChromaDB without embeddings (so it has 0 similarity vector-wise to a random query)
        import uuid
        collection = get_chroma_collection()
        collection.add(
            embeddings=[[0.01] * 768], # Dummy embedding, highly distinct from any meaningful search
            documents=[test_text],
            metadatas=[{"source": "test_script.txt", "user_id": user_id}],
            ids=[str(uuid.uuid4())]
        )
        
        # Test Query: exact keyword unique code
        query = "ZX-9971-ALBIN"
        
        print(f"\n--- Running Query 1: '{query}' with Hybrid=False (Vector only) ---")
        vector_results = retrieve_relevant_chunks(
            question=query,
            user_id=user_id,
            hybrid=False
        )
        found_vector = False
        for chunk in vector_results:
            print(f"Similarity: {chunk.similarity:.4f} | Content: {chunk.content[:60]}...")
            if "ZX-9971-ALBIN" in chunk.content:
                found_vector = True
        
        print(f"\n--- Running Query 2: '{query}' with Hybrid=True (Lexical + Vector) ---")
        hybrid_results = retrieve_relevant_chunks(
            question=query,
            user_id=user_id,
            hybrid=True
        )
        found_hybrid = False
        for chunk in hybrid_results:
            print(f"Similarity (RRF): {chunk.similarity:.4f} | Content: {chunk.content[:60]}...")
            if "ZX-9971-ALBIN" in chunk.content:
                found_hybrid = True
                
        print("\n=== VERIFICATION RESULTS ===")
        if not found_vector and found_hybrid:
            print("✅ SUCCESS: Hybrid search perfectly found the exact keyword SH-908 block when vector search missed it!")
        elif found_vector and found_hybrid:
            print("🟢 NOTE: Both found it, but hybrid worked beautifully!")
        else:
            print("❌ FAILURE: Hybrid search did not retrieve the matching chunk!")
            
        # Clean up temporary test data
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM documents WHERE content = %s AND user_id = %s::uuid;", (test_text, user_id))
        collection.delete(where={"$and": [{"source": "test_script.txt"}, {"user_id": user_id}]})
        print("Cleaned up test data.")

    finally:
        close_pool()

if __name__ == "__main__":
    test_hybrid_search()

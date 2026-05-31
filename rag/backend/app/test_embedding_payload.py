import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import app.retrieval as retrieval
from app.db import open_pool, close_pool

def test_embedding_payload():
    open_pool()
    try:
        # We mock create_embedding temporarily to intercept the exact payload
        original_create_embedding = retrieval.create_embedding
        
        intercepted_payload = None
        def mock_create_embedding(text):
            nonlocal intercepted_payload
            intercepted_payload = text
            # Call original to keep things running normally
            return original_create_embedding(text)
            
        retrieval.create_embedding = mock_create_embedding
        
        # Define a test question
        question = "What should I do if the reactor core seal leaks?"
        
        print(f"User Query: '{question}'")
        print("Running retrieve_relevant_chunks with hyde=True and hybrid=True...")
        
        # We run the retrieval (using dummy session and user_id to trigger FTS)
        retrieval.retrieve_relevant_chunks(
            question=question,
            sessionId="test-session",
            limit=5,
            user_id="5e16d242-5975-43e0-babe-9271ee476a4b", # Existing user_id from previous run
            hyde=True,
            hybrid=True
        )
        
        print("\n================ INTERCEPTED PAYLOAD ================")
        print(intercepted_payload)
        print("=====================================================")
        
        # Restore original function
        retrieval.create_embedding = original_create_embedding
        
    finally:
        close_pool()

if __name__ == "__main__":
    test_embedding_payload()

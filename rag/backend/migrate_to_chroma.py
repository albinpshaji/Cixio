import os
import uuid
import psycopg
from app.chroma_db import get_chroma_collection

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5433")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "albin")
DB_NAME = os.getenv("POSTGRES_DB", "rag_db")

def sanitize_metadata(meta):
    if not isinstance(meta, dict):
        return {}
    clean = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean

def migrate():
    try:
        conn = psycopg.connect(
            f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, content, metadata, embedding FROM documents WHERE embedding IS NOT NULL")
        rows = cursor.fetchall()
        print(f"Found {len(rows)} chunks with embeddings in PostgreSQL.")
        
        if len(rows) > 0:
            collection = get_chroma_collection()
            
            embeddings = []
            documents = []
            metadatas = []
            ids = []
            
            for row in rows:
                content = row[1]
                metadata = row[2] or {}
                metadata = sanitize_metadata(metadata)
                
                embedding_str = row[3]
                if isinstance(embedding_str, str) and embedding_str.startswith('['):
                    embedding_vec = [float(x) for x in embedding_str.strip('[]').split(',')]
                else:
                    embedding_vec = embedding_str
                
                embeddings.append(embedding_vec)
                documents.append(content)
                metadatas.append(metadata)
                ids.append(str(uuid.uuid4()))
                
            print(f"Adding {len(embeddings)} chunks to ChromaDB...")
            batch_size = 5000
            for i in range(0, len(embeddings), batch_size):
                collection.add(
                    embeddings=embeddings[i:i+batch_size],
                    documents=documents[i:i+batch_size],
                    metadatas=metadatas[i:i+batch_size],
                    ids=ids[i:i+batch_size]
                )
            print("Migration complete!")
            
    except Exception as e:
        print(f"Migration error: {e}")

migrate()

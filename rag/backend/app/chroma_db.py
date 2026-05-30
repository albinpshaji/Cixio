import chromadb

# Initialize ChromaDB persistent client in the backend directory
chroma_client = chromadb.PersistentClient(path="./chroma_data")
collection = chroma_client.get_or_create_collection(
    name="documents",
    metadata={"hnsw:space": "cosine"} # Use cosine similarity for embeddings
)

def get_chroma_collection():
    return collection

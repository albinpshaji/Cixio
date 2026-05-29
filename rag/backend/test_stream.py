import httpx

url = "http://localhost:11434/api/generate"
payload = {
    "model": "qwen3.5:4b",
    "prompt": "what is RAG?",
    "stream": False,
    "options": {
        "num_predict": 50,
        "temperature": 0.2,
        "num_ctx": 8192
    }
}

try:
    response = httpx.post(url, json=payload, timeout=30.0)
    response.raise_for_status()
    print("Ollama accepted num_ctx!")
except Exception as e:
    print(f"Error: {e}")

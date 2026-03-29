import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

def ask_ollama(prompt):
    response = requests.post(OLLAMA_URL, json={
        "model": "phi3",
        "prompt": prompt,
        "stream": False
    })

    return response.json()["response"]
import httpx
from app.core.config import settings

def test():
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "anthropic/claude-3.5-sonnet", # Changed dash to dot
        "messages": [{"role": "user", "content": "hello"}],
    }
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}", "Content-Type": "application/json"}
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        print(resp.text)
    except Exception as e:
        print(f"Error: {e}")

test()

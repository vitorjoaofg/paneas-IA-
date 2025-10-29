#!/usr/bin/env python3
import httpx
import json

url = "http://llm-int4:8002/v1/chat/completions"
payload = {
    "model": "/models/qwen2_5/int4-awq-32b",
    "messages": [
        {"role": "user", "content": "Say only: TEST OK"}
    ],
    "max_tokens": 10,
    "temperature": 0.7
}

try:
    print(f"Testing: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    response = httpx.post(url, json=payload, timeout=30.0)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    if response.status_code == 200:
        data = response.json()
        print(f"Content: {data['choices'][0]['message']['content']}")
except Exception as e:
    print(f"Error: {e}")
#!/usr/bin/env python3
"""
Test simple completion with direct call to API
"""

import json
import httpx
import asyncio

async def test_simple():
    print("Testing simple completion...")

    payload = {
        "model": "paneas-q32b",
        "messages": [
            {"role": "user", "content": "Say only: OK"}
        ],
        "max_tokens": 10
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://localhost:8000/api/v1/chat/completions",
                json=payload,
                headers={"Authorization": "Bearer token_abc123"},
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Success!")
                print(f"Response: {data['choices'][0]['message']['content']}")
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
    except httpx.TimeoutException:
        print("❌ Timeout")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_simple())
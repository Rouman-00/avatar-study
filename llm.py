import asyncio

from fastapi import HTTPException
from huggingface_hub import InferenceClient

import config

_hf_client: InferenceClient | None = None


def get_hf_client() -> InferenceClient:
    global _hf_client
    if _hf_client is None:
        _hf_client = InferenceClient(model=config.LLM_MODEL_ID, token=config.HF_TOKEN)
    return _hf_client


async def generate_reply(message: str) -> str:
    if not config.HF_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="HF_TOKEN ist nicht gesetzt. Bitte in der .env-Datei hinterlegen.",
        )

    client = get_hf_client()
    completion = await asyncio.to_thread(
        client.chat_completion,
        messages=[{"role": "user", "content": message}],
        max_tokens=512,
    )
    return completion.choices[0].message.content

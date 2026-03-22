import asyncio
import json
from typing import AsyncGenerator, List, Optional

import aiohttp
from aiohttp_retry import RetryClient, ExponentialRetry
from loguru import logger

from config import settings, UNCENSORED_MODELS  # noqa: F401 (re-exported for convenience)

VENICE_BASE_URL = "https://api.venice.ai/api/v1"

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=120, connect=10)


def _build_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.VENICE_API_KEY}",
        "Content-Type": "application/json",
    }


def _build_payload(
    model_id: str,
    messages: List[dict],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    system_prompt: Optional[str] = None,
    stream: bool = False,
) -> dict:
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    return {
        "model": model_id,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
        "venice_parameters": {
            "include_venice_system_prompt": False,
        },
    }


async def chat_completion(
    model_id: str,
    messages: List[dict],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    system_prompt: Optional[str] = None,
) -> str:
    """Send a chat completion request and return the response text."""
    payload = _build_payload(model_id, messages, temperature, max_tokens, system_prompt)

    retry_options = ExponentialRetry(attempts=3, start_timeout=1.0, factor=2.0)

    try:
        async with RetryClient(
            raise_for_status=False,
            retry_options=retry_options,
            timeout=DEFAULT_TIMEOUT,
        ) as client:
            async with client.post(
                f"{VENICE_BASE_URL}/chat/completions",
                json=payload,
                headers=_build_headers(),
            ) as resp:
                if resp.status == 401:
                    logger.error("Venice API: Invalid API key")
                    raise ValueError("Неверный API ключ Venice.ai")
                if resp.status == 429:
                    logger.warning("Venice API: Rate limit hit")
                    raise RuntimeError("Превышен лимит запросов Venice.ai, попробуйте позже")
                if resp.status >= 500:
                    text = await resp.text()
                    logger.error(f"Venice API server error {resp.status}: {text}")
                    raise RuntimeError(f"Ошибка сервера Venice.ai ({resp.status})")
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Venice API unexpected status {resp.status}: {text}")
                    raise RuntimeError(f"Ошибка Venice.ai: {resp.status}")

                data = await resp.json()
                return data["choices"][0]["message"]["content"]

    except asyncio.TimeoutError:
        logger.error("Venice API: Request timed out")
        raise RuntimeError("Запрос к Venice.ai превысил время ожидания")
    except (aiohttp.ClientConnectionError, aiohttp.ClientError) as exc:
        logger.error(f"Venice API connection error: {exc}")
        raise RuntimeError(f"Ошибка подключения к Venice.ai: {exc}")


async def stream_completion(
    model_id: str,
    messages: List[dict],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    system_prompt: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Async generator that yields text chunks from a streaming response."""
    payload = _build_payload(
        model_id, messages, temperature, max_tokens, system_prompt, stream=True
    )

    try:
        async with aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT) as session:
            async with session.post(
                f"{VENICE_BASE_URL}/chat/completions",
                json=payload,
                headers=_build_headers(),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Venice stream error {resp.status}: {text}")
                    raise RuntimeError(f"Ошибка Venice.ai: {resp.status}")

                async for raw_line in resp.content:
                    line = raw_line.decode("utf-8").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    try:
                        chunk = json.loads(line)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError):
                        continue

    except asyncio.TimeoutError:
        logger.error("Venice stream: Request timed out")
        raise RuntimeError("Стриминг Venice.ai превысил время ожидания")
    except (aiohttp.ClientConnectionError, aiohttp.ClientError) as exc:
        logger.error(f"Venice stream connection error: {exc}")
        raise RuntimeError(f"Ошибка подключения к Venice.ai: {exc}")


async def get_available_models() -> List[dict]:
    """Fetch the list of available models from Venice.ai API."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(
                f"{VENICE_BASE_URL}/models",
                headers=_build_headers(),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Venice models endpoint returned {resp.status}")
                    return []
                data = await resp.json()
                return data.get("data", [])
    except Exception as exc:
        logger.error(f"Failed to fetch Venice models: {exc}")
        return []

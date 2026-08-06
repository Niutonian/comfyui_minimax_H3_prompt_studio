"""Small clients for supported text and vision generation providers."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class ProviderError(RuntimeError):
    """A safe, user-facing provider failure."""


def load_local_env() -> None:
    """Load simple KEY=VALUE entries without overriding process variables."""
    candidates = (Path(__file__).with_name(".env"), Path.cwd() / ".env")
    for path in candidates:
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"").strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1200]
        raise ProviderError(f"Provider returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Could not reach provider: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ProviderError(f"Provider request timed out after {timeout} seconds") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider returned an invalid JSON response") from exc


def _get_json(
    url: str,
    headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read(4 * 1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1200]
        raise ProviderError(f"Provider returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Could not reach provider: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ProviderError(f"Provider request timed out after {timeout} seconds") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider returned an invalid JSON response") from exc


def _required_key(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ProviderError(
            f"Missing {name}. Set it in the environment or in "
            f"{Path(__file__).with_name('.env')}"
        )
    return value


def _openai(
    config: dict[str, Any], system: str, prompt: str,
    images: list[dict[str, str]] | None = None,
    disable_thinking: bool = False,
) -> str:
    key = _required_key("OPENAI_API_KEY")
    base = config["base_url"].strip() or "https://api.openai.com/v1"
    user_content: str | list[dict[str, Any]] = prompt
    if images:
        user_content = [{"type": "input_text", "text": prompt}]
        for image in images:
            user_content.extend([
                {"type": "input_text", "text": image["label"]},
                {"type": "input_image", "image_url":
                 f"data:{image['media_type']};base64,{image['data']}"},
            ])
    data = _post_json(
        f"{base.rstrip('/')}/responses",
        {
            "model": config["model"],
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            "temperature": config["temperature"],
            "max_output_tokens": config["max_tokens"],
        },
        {"Authorization": f"Bearer {key}"},
        config["timeout"],
    )
    if isinstance(data.get("output_text"), str):
        return data["output_text"].strip()
    texts: list[str] = []
    for output in data.get("output", []):
        for content in output.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                texts.append(text)
    if not texts:
        raise ProviderError("OpenAI response contained no text output")
    return "\n".join(texts).strip()


def _anthropic(
    config: dict[str, Any], system: str, prompt: str,
    images: list[dict[str, str]] | None = None,
    disable_thinking: bool = False,
) -> str:
    key = _required_key("ANTHROPIC_API_KEY")
    base = config["base_url"].strip() or "https://api.anthropic.com"
    user_content: str | list[dict[str, Any]] = prompt
    if images:
        user_content = [{"type": "text", "text": prompt}]
        for image in images:
            user_content.extend([
                {"type": "text", "text": image["label"]},
                {"type": "image", "source": {
                    "type": "base64",
                    "media_type": image["media_type"],
                    "data": image["data"],
                }},
            ])
    data = _post_json(
        f"{base.rstrip('/')}/v1/messages",
        {
            "model": config["model"],
            "system": system,
            "messages": [{"role": "user", "content": user_content}],
            "temperature": config["temperature"],
            "max_tokens": config["max_tokens"],
        },
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
        config["timeout"],
    )
    texts = [part.get("text", "") for part in data.get("content", []) if part.get("type") == "text"]
    result = "\n".join(text for text in texts if text).strip()
    if not result:
        raise ProviderError("Anthropic response contained no text output")
    return result


def _gemini(
    config: dict[str, Any], system: str, prompt: str,
    images: list[dict[str, str]] | None = None,
    disable_thinking: bool = False,
) -> str:
    key = _required_key("GEMINI_API_KEY")
    base = config["base_url"].strip() or "https://generativelanguage.googleapis.com/v1beta"
    model = urllib.parse.quote(config["model"], safe="")
    parts: list[dict[str, Any]] = [{"text": prompt}]
    for image in images or []:
        parts.extend([
            {"text": image["label"]},
            {"inlineData": {
                "mimeType": image["media_type"],
                "data": image["data"],
            }},
        ])
    data = _post_json(
        f"{base.rstrip('/')}/models/{model}:generateContent",
        {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": config["temperature"],
                "maxOutputTokens": config["max_tokens"],
            },
        },
        {"x-goog-api-key": key},
        config["timeout"],
    )
    texts: list[str] = []
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if isinstance(part.get("text"), str):
                texts.append(part["text"])
    if not texts:
        detail = data.get("promptFeedback", {}).get("blockReason", "no text output")
        raise ProviderError(f"Gemini response contained no text output ({detail})")
    return "\n".join(texts).strip()


def _ollama(
    config: dict[str, Any], system: str, prompt: str,
    images: list[dict[str, str]] | None = None,
    disable_thinking: bool = False,
) -> str:
    base = config["base_url"].strip() or os.getenv(
        "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
    )
    base = base.rstrip("/")
    url = f"{base}/chat" if base.endswith("/api") else f"{base}/api/chat"
    user_message: dict[str, Any] = {"role": "user", "content": prompt}
    if images:
        labels = "\n".join(
            f"Image {index}: {image['label']}"
            for index, image in enumerate(images, 1)
        )
        user_message["content"] = f"{prompt}\n\nATTACHED IMAGE ORDER:\n{labels}"
        user_message["images"] = [image["data"] for image in images]
    payload: dict[str, Any] = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system},
            user_message,
        ],
        "stream": False,
        "options": {
            "temperature": config["temperature"],
            "num_predict": config["max_tokens"],
        },
    }
    if disable_thinking:
        payload["think"] = False
    data = _post_json(
        url,
        payload,
        {},
        config["timeout"],
    )
    result = data.get("message", {}).get("content", "").strip()
    if not result:
        reason = data.get("done_reason", "unknown")
        raise ProviderError(
            f"Ollama response contained no text output (done reason: {reason})"
        )
    return result


PROVIDERS = {
    "OpenAI": _openai,
    "Claude": _anthropic,
    "Gemini": _gemini,
    "Ollama": _ollama,
}


def discover_models(
    provider: str,
    base_url: str = "",
    timeout: int = 15,
) -> list[str]:
    """Return model identifiers currently visible to a provider account."""
    load_local_env()
    base_url = base_url.strip()

    if provider == "Ollama":
        base = base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        base = base.rstrip("/")
        url = f"{base}/tags" if base.endswith("/api") else f"{base}/api/tags"
        data = _get_json(url, {}, timeout)
        models = [item.get("model") or item.get("name") for item in data.get("models", [])]
    elif provider == "OpenAI":
        key = _required_key("OPENAI_API_KEY")
        base = base_url or "https://api.openai.com/v1"
        data = _get_json(
            f"{base.rstrip('/')}/models",
            {"Authorization": f"Bearer {key}"},
            timeout,
        )
        models = [item.get("id") for item in data.get("data", [])]
    elif provider == "Claude":
        key = _required_key("ANTHROPIC_API_KEY")
        base = base_url or "https://api.anthropic.com"
        data = _get_json(
            f"{base.rstrip('/')}/v1/models?limit=1000",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            timeout,
        )
        models = [item.get("id") for item in data.get("data", [])]
    elif provider == "Gemini":
        key = _required_key("GEMINI_API_KEY")
        base = base_url or "https://generativelanguage.googleapis.com/v1beta"
        data = _get_json(
            f"{base.rstrip('/')}/models?pageSize=1000",
            {"x-goog-api-key": key},
            timeout,
        )
        models = []
        for item in data.get("models", []):
            methods = item.get("supportedGenerationMethods", [])
            if methods and "generateContent" not in methods:
                continue
            name = item.get("name", "")
            models.append(name.removeprefix("models/"))
    else:
        raise ProviderError(f"Unsupported provider: {provider}")

    return sorted({str(model).strip() for model in models if model}, key=str.lower)


def generate_text(config: dict[str, Any], system: str, prompt: str) -> str:
    load_local_env()
    provider = config.get("provider", "")
    model = str(config.get("model", "")).strip()
    if provider not in PROVIDERS:
        raise ProviderError(f"Unsupported provider: {provider}")
    if not model:
        raise ProviderError("Model name cannot be empty")
    return PROVIDERS[provider](
        config,
        system,
        prompt,
        disable_thinking=bool(config.get("disable_ollama_thinking", False)),
    )


def generate_vision_text(
    config: dict[str, Any], system: str, prompt: str,
    images: list[dict[str, str]],
) -> str:
    """Generate text with optional labeled images using provider-native payloads."""
    load_local_env()
    provider = config.get("provider", "")
    model = str(config.get("model", "")).strip()
    if provider not in PROVIDERS:
        raise ProviderError(f"Unsupported provider: {provider}")
    if not model:
        raise ProviderError("Model name cannot be empty")
    return PROVIDERS[provider](
        config, system, prompt, images, disable_thinking=True
    )

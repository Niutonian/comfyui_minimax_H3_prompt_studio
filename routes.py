"""Optional ComfyUI HTTP routes used by the provider-model picker."""

from __future__ import annotations

import asyncio

from .providers import ProviderError, discover_models


_registered = False


def register_routes() -> None:
    global _registered
    if _registered:
        return
    try:
        from aiohttp import web
        from server import PromptServer
    except ImportError:
        # Allows unit tests and prompt utilities to run outside ComfyUI.
        return

    prompt_server = getattr(PromptServer, "instance", None)
    if prompt_server is None:
        # ComfyUI creates this before loading custom nodes. A standalone import of
        # the package (for tests or utilities) may happen earlier.
        return

    @prompt_server.routes.get("/minimax_h3_prompt_studio/models")
    async def list_provider_models(request):
        provider = request.query.get("provider", "Ollama")
        base_url = request.query.get("base_url", "")
        try:
            models = await asyncio.to_thread(discover_models, provider, base_url)
            return web.json_response({"models": models, "error": ""})
        except ProviderError as exc:
            return web.json_response(
                {"models": [], "error": str(exc)},
                status=400,
            )

    _registered = True

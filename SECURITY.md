# Security

## API credentials

MiniMax H3 Prompt Studio reads cloud credentials from environment variables or a local
`.env` file. It does not require credentials to be entered into ComfyUI widgets.

- Never commit `.env` or any file containing a real credential.
- Keep `.env.example` limited to empty values and safe local defaults.
- Review exported workflows before publishing them.
- If a key is exposed, revoke it with the provider immediately and issue a replacement.

Supported variables:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
GEMINI_API_KEY
OLLAMA_BASE_URL
```

Cloud-provider prompts are transmitted to the selected provider. Local Ollama prompts
remain local when Ollama itself is configured for local-only operation.

## Reporting a vulnerability

Once the repository is published, use GitHub's private security-advisory feature to
report vulnerabilities rather than opening a public issue containing exploit details
or credentials.

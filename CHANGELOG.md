# Changelog

## Unreleased

- Reject malformed all-in-one packages, invalid field types, and empty final prompts.
- Added a local structural validator with report, validity, and strict-mode outputs.
- Added manual model entry, endpoint refresh, and stale discovery request protection.
- Moved model discovery network calls off the ComfyUI server event loop.

- Fixed the Text Preview node so execution payloads appear in a resizable,
  read-only multiline viewer while continuing through the STRING output.

## 0.1.0 - 2026-08-06

- Initial nine-node MiniMax H3 audiovisual prompt suite.
- OpenAI, Claude, Gemini, and local Ollama provider support.
- Provider-aware model discovery and model selection.
- T2VA, I2VA, FL2VA, L2VA, and full-reference prompt modes.
- Official H3 alignment instructions, core fields, shot timing, dialogue tags,
  speaker IDs, soundscape separation, and reference retention labels.

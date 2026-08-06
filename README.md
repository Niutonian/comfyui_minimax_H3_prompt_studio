# MiniMax H3 Prompt Studio for ComfyUI

A ComfyUI prompt-writing suite for MiniMax H3. It turns short ideas, detailed briefs,
stories, and reference images into structured audiovisual prompts that follow MiniMax's
official H3 syntax.

This package writes prompt text. It does not download, load, or sample the MiniMax H3
video model; connect its `STRING` output to the text input used by your H3 workflow.

## H3 prompt modes

- **T2VA** — constructs the complete audiovisual timeline from text.
- **I2VA** — anchors Picture 1 at the exact first frame and develops forward.
- **FL2VA** — connects exact first and last frames through a continuous motion path.
- **L2VA** — infers an earlier state and converges on Picture 1 as the exact last frame.
- **Full-reference** — defines reusable subjects and reference relationships with the
  official six-section output format.

The implementation follows MiniMax's official
[base prompt-writing guide](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md)
and
[full-reference guide](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md).

## Nodes

- **LLM Provider** — selects OpenAI, Claude, Gemini, or a local Ollama writing model.
- **H3 Story Generator** — develops a feasible audiovisual story and continuity locks.
- **H3 Shot Planner** — creates numbered shots with valid, increasing cut times.
- **MiniMax H3 Prompt Writer** — converts arbitrary source material into the official
  three-field H3 prompt structure.
- **H3 Prompt Critic / Rewriter** — checks and repairs H3 formatting, timing, reference,
  dialogue, camera, and audio problems.
- **Story to H3 Prompt (All-in-One)** — creates a story, shot plan, and complete H3
  prompt in one LLM call.
- **Image Story to H3 Prompt (All-in-One)** — uses a vision-capable writing model for
  I2VA, FL2VA, L2VA, or full-reference prompts.
- **H3 Prompt Builder** — deterministically assembles an H3 base prompt without an LLM.
- **Text Preview** — displays and passes through any generated string.

All writing outputs use ComfyUI's standard `STRING` type.

## Installation

Copy the folder into ComfyUI's `custom_nodes` directory:

```text
ComfyUI/
└── custom_nodes/
    └── comfyui_minimax_H3_prompt_studio/
```

Restart ComfyUI. The nodes appear under **MiniMax H3 Prompt Studio**. No additional
Python packages are required beyond those already included with ComfyUI.

## Writing-model configuration

The suite uses an LLM to compose H3 prompts. API keys are supplied through environment
variables or an optional `.env` file inside this node folder:

```dotenv
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Only add keys for providers you use. `.env` is ignored by Git. Credentials are never
stored in ComfyUI workflow JSON.

For Ollama, leave `base_url` empty to use `OLLAMA_BASE_URL` or
`http://127.0.0.1:11434`. The provider node discovers locally installed models and lets
you refresh the list. Use a vision-capable writing model for the image-story node.
The provider exposes `disable_ollama_thinking`, enabled by default, so the final H3
structure receives the prediction budget instead of being consumed by hidden reasoning.
Vision requests always disable thinking.

Default endpoints:

```text
Ollama:  http://127.0.0.1:11434
OpenAI:  https://api.openai.com/v1
Claude:  https://api.anthropic.com
Gemini:  https://generativelanguage.googleapis.com/v1beta
```

## Output structure

Base-mode prompts contain these fields in order:

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

The builder inserts the exact required image-alignment line for I2VA, FL2VA, and L2VA.
T2VA begins directly with the three fields. Later shots use strictly increasing
`[Shot N] At MM:SS.mmm, ...` cut times; Shot 1 has no timestamp.

Full-reference mode produces:

```text
subject_definitions:
summary:
retention_analysis:
detailed_description:
overall_soundscape:
non_diegetic_music:
```

Dialogue and lyrics use `<d>[Language] ...</d>`, vocal sources retain stable `(S1)`,
`(S2)` identifiers, and visible text is quoted verbatim. Diegetic dialogue and music
remain in the detailed timeline; ambience and physical sounds are summarized separately
from audience-only non-diegetic music.

## Image workflow

The image-story node exposes four optional image sockets:

- `first_frame_image`
- `last_frame_image`
- `subject_reference_1`
- `subject_reference_2`

Required connections depend on the selected task mode:

| Mode | Required images |
| --- | --- |
| I2VA | First frame |
| FL2VA | First and last frames |
| L2VA | Last frame |
| Full-reference | At least one image; subject references are supported |

Subject-reference sockets are intentionally limited to full-reference mode. Each socket
uses the first image in its ComfyUI image batch and scales it to a maximum side length
of 1536 pixels before sending it to the selected writing provider.

The reference images sent to the writing LLM are not automatically connected to the
MiniMax H3 generation nodes. Connect the same source images to the appropriate H3 model
inputs in your video-generation workflow.

## Suggested workflows

Text-only:

```text
LLM Provider → Story to H3 Prompt (All-in-One) → Text Preview
```

Keyframe or full-reference:

```text
Load Image(s) ───────────────┐
LLM Provider ────────────────┼→ Image Story to H3 Prompt (All-in-One) → Text Preview
Written idea (optional) ─────┘
```

Manual deterministic assembly:

```text
H3 Prompt Builder → Text Preview
```

Three importable workflows are included:

- [`example/minimax_h3_t2va_workflow.json`](example/minimax_h3_t2va_workflow.json)
  generates a complete text-to-video story, shot plan, and H3 prompt.
- [`example/minimax_h3_fl2va_workflow.json`](example/minimax_h3_fl2va_workflow.json)
  demonstrates a continuous first-and-last-frame prompt.
- [`example/minimax_h3_full_reference_workflow.json`](example/minimax_h3_full_reference_workflow.json)
  demonstrates composition and character references using the official six-section
  full-reference format.

After importing an image workflow, select your own files in every connected **Load
Image** node. Placeholder filenames are included only to make each reference role clear.

## Tests

From the directory containing the package:

```powershell
python -m unittest discover -s comfyui_minimax_H3_prompt_studio/tests -v
node --check comfyui_minimax_H3_prompt_studio/web/model_picker.js
```

## Security and attribution

Cloud prompts and reference images leave your computer and are subject to the selected
provider's policies. Local Ollama requests remain local when Ollama is configured for
local-only operation.

This community utility is not an official MiniMax product. MiniMax H3 and its prompt
guides belong to MiniMax. This repository's source code is released under the
[MIT License](LICENSE).

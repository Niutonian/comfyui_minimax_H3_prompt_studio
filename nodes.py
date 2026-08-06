"""ComfyUI nodes for writing MiniMax H3 audiovisual prompts."""

from __future__ import annotations

import base64
import io

from .prompts import (
    BASE_TASK_MODES,
    DIRECTOR_SYSTEM,
    VISION_TASK_MODES,
    all_in_one_request,
    assemble_h3_prompt,
    critique_request,
    h3_prompt_request,
    parse_package,
    parse_vision_package,
    scene_request,
    story_request,
    vision_all_in_one_request,
)
from .providers import generate_text, generate_vision_text


CATEGORY = "MiniMax H3 Prompt Studio"
CONFIG_TYPE = "MINIMAX_H3_LLM_CONFIG"
MULTILINE = {"multiline": True, "dynamicPrompts": False}
VIDEO_TYPES = [
    "cinematic narrative", "single-shot scene", "commercial", "dialogue scene",
    "documentary", "found footage", "music video", "animation", "3D CG",
    "claymation", "motion graphics", "transformation", "social video", "trailer",
    "experimental",
]
SHOT_STRUCTURES = [
    "automatic", "single continuous shot", "time-coded continuous shot",
    "multi-shot sequence", "start-to-end transformation",
]
GENRES = [
    "cinematic", "automatic", "action", "adventure", "comedy", "drama",
    "fantasy", "horror", "mystery", "romance", "science fiction", "thriller",
    "documentary", "satire", "experimental", "custom",
]
TONES = [
    "engaging", "automatic", "dramatic", "suspenseful", "humorous", "dark",
    "uplifting", "emotional", "mysterious", "energetic", "calm", "surreal",
    "nostalgic", "epic", "custom",
]
REFERENCE_FIDELITY = [
    "fully_preserved", "partially_preserved", "attribute_transfer", "weak_reference"
]
CREATIVITY_LEVELS = ["grounded", "creative", "wild", "surreal"]


def resolve_custom_choice(selection: str, custom_value: str) -> str:
    if selection == "custom":
        return custom_value.strip() or "automatic"
    return selection


def encode_comfy_image(image, label: str, max_side: int = 1536) -> dict[str, str]:
    """Encode the first image in a ComfyUI IMAGE batch as a bounded JPEG."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Vision nodes require NumPy and Pillow, which are included with ComfyUI."
        ) from exc

    pixels = image.detach().cpu().numpy() if hasattr(image, "detach") else np.asarray(image)
    if pixels.ndim == 4:
        if pixels.shape[0] == 0:
            raise ValueError(f"{label} contains an empty image batch")
        pixels = pixels[0]
    if pixels.ndim != 3 or pixels.shape[-1] not in (1, 3, 4):
        raise ValueError(f"{label} is not a supported ComfyUI IMAGE tensor")
    if np.issubdtype(pixels.dtype, np.floating):
        pixels = (np.clip(pixels, 0.0, 1.0) * 255.0).round().astype(np.uint8)
    else:
        pixels = np.clip(pixels, 0, 255).astype(np.uint8)
    if pixels.shape[-1] == 1:
        pixels = np.repeat(pixels, 3, axis=-1)
    elif pixels.shape[-1] == 4:
        alpha = pixels[..., 3:4].astype(np.float32) / 255.0
        pixels = (
            pixels[..., :3].astype(np.float32) * alpha + 255.0 * (1.0 - alpha)
        ).round().astype(np.uint8)

    pil_image = Image.fromarray(pixels, mode="RGB")
    if max(pil_image.size) > max_side:
        scale = max_side / max(pil_image.size)
        size = tuple(max(1, round(value * scale)) for value in pil_image.size)
        resampling = getattr(Image, "Resampling", Image).LANCZOS
        pil_image = pil_image.resize(size, resampling)
    buffer = io.BytesIO()
    pil_image.save(buffer, format="JPEG", quality=90, optimize=True)
    return {
        "label": label,
        "media_type": "image/jpeg",
        "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
    }


class MiniMaxH3LLMProvider:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "provider": (["Ollama", "OpenAI", "Claude", "Gemini"],),
            "model": ("STRING", {"default": "qwen3.6:latest"}),
            "base_url": ("STRING", {"default": ""}),
            "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
            "max_tokens": ("INT", {"default": 6144, "min": 128, "max": 32768, "step": 128}),
            "timeout_seconds": ("INT", {"default": 240, "min": 10, "max": 1800, "step": 10}),
            "disable_ollama_thinking": ("BOOLEAN", {"default": True}),
        }}

    RETURN_TYPES = (CONFIG_TYPE, "STRING")
    RETURN_NAMES = ("provider_config", "configuration_summary")
    FUNCTION = "configure"
    CATEGORY = f"{CATEGORY}/Configuration"

    def configure(self, provider, model, base_url, temperature, max_tokens,
                  timeout_seconds, disable_ollama_thinking):
        config = {
            "provider": provider, "model": model.strip(), "base_url": base_url.strip(),
            "temperature": temperature, "max_tokens": max_tokens, "timeout": timeout_seconds,
            "disable_ollama_thinking": disable_ollama_thinking,
        }
        return config, f"{provider} / {model.strip() or '[model required]'}"


class MiniMaxH3StoryGenerator:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "provider_config": (CONFIG_TYPE,),
            "idea": ("STRING", MULTILINE),
            "genre": (GENRES,), "tone": (TONES,),
            "total_duration_seconds": ("INT", {"default": 10, "min": 1, "max": 600}),
            "shot_count": ("INT", {"default": 1, "min": 1, "max": 50}),
            "language": ("STRING", {"default": "English"}),
            "extra_instructions": ("STRING", MULTILINE),
            "variation_seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
            "custom_genre": ("STRING", {"default": "", "placeholder": "Used when genre is custom"}),
            "custom_tone": ("STRING", {"default": "", "placeholder": "Used when tone is custom"}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("story",)
    FUNCTION = "generate"
    CATEGORY = f"{CATEGORY}/Writing"

    def generate(self, provider_config, idea, genre, tone, total_duration_seconds,
                 shot_count, language, extra_instructions, variation_seed,
                 custom_genre, custom_tone):
        request = story_request(
            idea, resolve_custom_choice(genre, custom_genre),
            resolve_custom_choice(tone, custom_tone), total_duration_seconds,
            shot_count, language, extra_instructions, variation_seed,
        )
        return (generate_text(provider_config, DIRECTOR_SYSTEM, request),)


class MiniMaxH3ScenePlanner:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "provider_config": (CONFIG_TYPE,), "story": ("STRING", MULTILINE),
            "total_duration_seconds": ("INT", {"default": 10, "min": 1, "max": 600}),
            "shot_count": ("INT", {"default": 1, "min": 1, "max": 50}),
            "extra_direction": ("STRING", MULTILINE),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("shot_plan",)
    FUNCTION = "plan"
    CATEGORY = f"{CATEGORY}/Writing"

    def plan(self, provider_config, story, total_duration_seconds, shot_count, extra_direction):
        return (generate_text(
            provider_config, DIRECTOR_SYSTEM,
            scene_request(story, total_duration_seconds, shot_count, extra_direction),
        ),)


class MiniMaxH3PromptWriter:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "provider_config": (CONFIG_TYPE,), "source_text": ("STRING", MULTILINE),
            "task_mode": (BASE_TASK_MODES,), "video_type": (VIDEO_TYPES,),
            "shot_structure": (SHOT_STRUCTURES,),
            "duration_seconds": ("INT", {"default": 10, "min": 1, "max": 600}),
            "shot_count": ("INT", {"default": 1, "min": 1, "max": 50}),
            "visual_style": ("STRING", MULTILINE), "camera_direction": ("STRING", MULTILINE),
            "audio_and_dialogue": ("STRING", MULTILINE), "reference_notes": ("STRING", MULTILINE),
            "constraints": ("STRING", MULTILINE),
            "detail_level": (["concise", "balanced", "production specification"],),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("h3_prompt",)
    FUNCTION = "write"
    CATEGORY = f"{CATEGORY}/Prompting"

    def write(self, provider_config, source_text, task_mode, video_type, shot_structure,
              duration_seconds, shot_count, visual_style, camera_direction,
              audio_and_dialogue, reference_notes, constraints, detail_level):
        request = h3_prompt_request(
            source_text, task_mode, video_type, shot_structure, duration_seconds,
            shot_count, visual_style, camera_direction, audio_and_dialogue,
            reference_notes, constraints, detail_level,
        )
        return (generate_text(provider_config, DIRECTOR_SYSTEM, request).strip(),)


class MiniMaxH3PromptCritic:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "provider_config": (CONFIG_TYPE,), "prompt_text": ("STRING", MULTILINE),
            "duration_seconds": ("INT", {"default": 10, "min": 1, "max": 600}),
            "mode": (["rewrite", "critique only"],),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("review_or_rewrite",)
    FUNCTION = "review"
    CATEGORY = f"{CATEGORY}/Prompting"

    def review(self, provider_config, prompt_text, duration_seconds, mode):
        return (generate_text(
            provider_config, DIRECTOR_SYSTEM,
            critique_request(prompt_text, duration_seconds, mode == "rewrite"),
        ),)


class MiniMaxH3AllInOne:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "provider_config": (CONFIG_TYPE,), "idea": ("STRING", MULTILINE),
            "task_mode": (BASE_TASK_MODES,), "video_type": (VIDEO_TYPES,),
            "genre": (GENRES,), "tone": (TONES,), "visual_style": ("STRING", MULTILINE),
            "total_duration_seconds": ("INT", {"default": 10, "min": 1, "max": 600}),
            "shot_count": ("INT", {"default": 1, "min": 1, "max": 50}),
            "shot_structure": (SHOT_STRUCTURES,), "language": ("STRING", {"default": "English"}),
            "reference_notes": ("STRING", MULTILINE), "extra_instructions": ("STRING", MULTILINE),
            "variation_seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
            "custom_genre": ("STRING", {"default": "", "placeholder": "Used when genre is custom"}),
            "custom_tone": ("STRING", {"default": "", "placeholder": "Used when tone is custom"}),
        }}

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("story", "shot_plan", "h3_prompt", "raw_response")
    FUNCTION = "create"
    CATEGORY = f"{CATEGORY}/Quick Start"

    def create(self, provider_config, idea, task_mode, video_type, genre, tone,
               visual_style, total_duration_seconds, shot_count, shot_structure,
               language, reference_notes, extra_instructions, variation_seed,
               custom_genre, custom_tone):
        request = all_in_one_request(
            idea, task_mode, video_type, resolve_custom_choice(genre, custom_genre),
            resolve_custom_choice(tone, custom_tone), visual_style,
            total_duration_seconds, shot_count, shot_structure, language,
            reference_notes, extra_instructions, variation_seed,
        )
        raw = generate_text(provider_config, DIRECTOR_SYSTEM, request)
        story, plan, prompt = parse_package(raw)
        return story, plan, prompt, raw


class MiniMaxH3VisionAllInOne:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "provider_config": (CONFIG_TYPE,), "idea": ("STRING", {**MULTILINE, "default": ""}),
                "task_mode": (VISION_TASK_MODES,), "video_type": (VIDEO_TYPES,),
                "genre": (GENRES,), "tone": (TONES,), "visual_style": ("STRING", MULTILINE),
                "total_duration_seconds": ("INT", {"default": 10, "min": 1, "max": 600}),
                "shot_count": ("INT", {"default": 1, "min": 1, "max": 50}),
                "shot_structure": (SHOT_STRUCTURES,), "language": ("STRING", {"default": "English"}),
                "reference_fidelity": (REFERENCE_FIDELITY,), "creativity": (CREATIVITY_LEVELS,),
                "subject_1_role": ("STRING", {"default": "main character"}),
                "subject_2_role": ("STRING", {"default": "supporting character"}),
                "extra_instructions": ("STRING", MULTILINE),
                "variation_seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
                "custom_genre": ("STRING", {"default": "", "placeholder": "Used when genre is custom"}),
                "custom_tone": ("STRING", {"default": "", "placeholder": "Used when tone is custom"}),
            },
            "optional": {
                "first_frame_image": ("IMAGE",), "last_frame_image": ("IMAGE",),
                "subject_reference_1": ("IMAGE",), "subject_reference_2": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = (
        "reference_analysis", "subject_definitions", "retention_analysis", "story",
        "shot_plan", "h3_prompt", "raw_response",
    )
    FUNCTION = "create"
    CATEGORY = f"{CATEGORY}/Quick Start"

    @staticmethod
    def _image_specs(task_mode, first, last, subject_1, subject_2, role_1, role_2):
        if task_mode == "I2VA" and first is None:
            raise ValueError("I2VA requires first_frame_image.")
        if task_mode == "FL2VA" and (first is None or last is None):
            raise ValueError("FL2VA requires both first_frame_image and last_frame_image.")
        if task_mode == "L2VA" and last is None:
            raise ValueError("L2VA requires last_frame_image.")
        if task_mode != "full-reference" and (subject_1 is not None or subject_2 is not None):
            raise ValueError("Subject reference images require full-reference task mode.")
        specs = []
        if task_mode == "I2VA":
            specs.append((first, "Picture 1 — exact first frame at 0.00 seconds"))
        elif task_mode == "FL2VA":
            specs.extend([
                (first, "Picture 1 — exact first frame at 0.00 seconds"),
                (last, "Picture 2 — exact final frame"),
            ])
        elif task_mode == "L2VA":
            specs.append((last, "Picture 1 — exact final frame"))
        else:
            if first is not None:
                specs.append((first, "Picture 1 — opening or composition reference"))
            if last is not None:
                specs.append((last, "Picture 2 — ending or composition reference"))
            if subject_1 is not None:
                specs.append((subject_1, f"Subject reference 1 — {role_1.strip() or 'main character'}"))
            if subject_2 is not None:
                specs.append((subject_2, f"Subject reference 2 — {role_2.strip() or 'supporting character'}"))
            if not specs:
                raise ValueError("Full-reference mode requires at least one image.")
        return specs

    def create(self, provider_config, idea, task_mode, video_type, genre, tone,
               visual_style, total_duration_seconds, shot_count, shot_structure,
               language, reference_fidelity, creativity, subject_1_role,
               subject_2_role, extra_instructions, variation_seed, custom_genre,
               custom_tone, first_frame_image=None, last_frame_image=None,
               subject_reference_1=None, subject_reference_2=None):
        specs = self._image_specs(
            task_mode, first_frame_image, last_frame_image, subject_reference_1,
            subject_reference_2, subject_1_role, subject_2_role,
        )
        images = [encode_comfy_image(image, label) for image, label in specs]
        request = vision_all_in_one_request(
            idea, task_mode, video_type, resolve_custom_choice(genre, custom_genre),
            resolve_custom_choice(tone, custom_tone), visual_style,
            total_duration_seconds, shot_count, shot_structure, language,
            reference_fidelity, creativity, [item["label"] for item in images],
            extra_instructions, variation_seed,
        )
        raw = generate_vision_text(provider_config, DIRECTOR_SYSTEM, request, images)
        parsed = parse_vision_package(raw)
        return (*parsed, raw)


class MiniMaxH3PromptBuilder:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "task_mode": (BASE_TASK_MODES,),
            "integrated_multimodal_description": ("STRING", MULTILINE),
            "overall_soundscape": ("STRING", {**MULTILINE, "default": "N/A"}),
            "non_diegetic_music": ("STRING", {**MULTILINE, "default": "N/A"}),
            "duration_seconds": ("FLOAT", {"default": 10.0, "min": 0.01, "max": 600.0, "step": 0.01}),
            "final_shot_number": ("INT", {"default": 1, "min": 1, "max": 50}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("h3_prompt",)
    FUNCTION = "build"
    CATEGORY = f"{CATEGORY}/Utilities"

    def build(self, task_mode, integrated_multimodal_description, overall_soundscape,
              non_diegetic_music, duration_seconds, final_shot_number):
        return (assemble_h3_prompt(
            task_mode, integrated_multimodal_description, overall_soundscape,
            non_diegetic_music, duration_seconds, final_shot_number,
        ),)


class MiniMaxH3TextPreview:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"text": ("STRING", {"forceInput": True})}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "preview"
    CATEGORY = f"{CATEGORY}/Utilities"
    OUTPUT_NODE = True

    def preview(self, text):
        return {"ui": {"text": [text]}, "result": (text,)}


NODE_CLASS_MAPPINGS = {
    "MiniMaxH3LLMProvider": MiniMaxH3LLMProvider,
    "MiniMaxH3StoryGenerator": MiniMaxH3StoryGenerator,
    "MiniMaxH3ScenePlanner": MiniMaxH3ScenePlanner,
    "MiniMaxH3PromptWriter": MiniMaxH3PromptWriter,
    "MiniMaxH3PromptCritic": MiniMaxH3PromptCritic,
    "MiniMaxH3AllInOne": MiniMaxH3AllInOne,
    "MiniMaxH3VisionAllInOne": MiniMaxH3VisionAllInOne,
    "MiniMaxH3PromptBuilder": MiniMaxH3PromptBuilder,
    "MiniMaxH3TextPreview": MiniMaxH3TextPreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxH3LLMProvider": "LLM Provider",
    "MiniMaxH3StoryGenerator": "H3 Story Generator",
    "MiniMaxH3ScenePlanner": "H3 Shot Planner",
    "MiniMaxH3PromptWriter": "MiniMax H3 Prompt Writer",
    "MiniMaxH3PromptCritic": "H3 Prompt Critic / Rewriter",
    "MiniMaxH3AllInOne": "Story to H3 Prompt (All-in-One)",
    "MiniMaxH3VisionAllInOne": "Image Story to H3 Prompt (All-in-One)",
    "MiniMaxH3PromptBuilder": "H3 Prompt Builder",
    "MiniMaxH3TextPreview": "Text Preview",
}

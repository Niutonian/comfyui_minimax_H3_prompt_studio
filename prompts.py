"""Prompt builders implementing MiniMax H3's official video-prompt grammar."""

from __future__ import annotations

import json
import re
from typing import Any


DIRECTOR_SYSTEM = """You are an expert MiniMax H3 audiovisual prompt writer.
Follow MiniMax H3's official prompt grammar exactly. Describe concrete visible and
audible events in playback order. Preserve supplied dialogue, lyrics, and visible text
verbatim. Use stable speaker IDs, achievable timing, coherent camera movement, and
strict reference continuity. Never discuss your process or add markdown fences."""

BASE_TASK_MODES = ["T2VA", "I2VA", "FL2VA", "L2VA"]
VISION_TASK_MODES = ["I2VA", "FL2VA", "L2VA", "full-reference"]


def context_block(**values: Any) -> str:
    return "\n".join(
        f"{name.replace('_', ' ').title()}: {value}"
        for name, value in values.items()
        if value not in (None, "", "None")
    )


def format_duration(duration: float) -> str:
    return f"{float(duration):.2f}"


def alignment_instruction(task_mode: str, duration: float, final_shot: int) -> str:
    """Return the exact H3 keyframe-alignment instruction for a base task mode."""
    seconds = format_duration(duration)
    shot = max(1, int(final_shot))
    if task_mode == "T2VA":
        return ""
    if task_mode == "I2VA":
        return (
            "For the target video, at 0.00 seconds into the target video, "
            "<Picture 1> (from [Shot 1]) is fully referenced."
        )
    if task_mode == "FL2VA":
        return (
            "How the reference pictures align with the target video — Picture 1 "
            "(from Shot 1) aligns with the 0.00-second mark of the target video; "
            f"Picture 2 (from Shot {shot}) aligns with the {seconds}-second mark "
            "of the target video."
        )
    if task_mode == "L2VA":
        return (
            "How the reference pictures align with the target video — <Picture 1> "
            f"(from [Shot {shot}]) aligns with the {seconds}-second mark of the "
            "target video."
        )
    raise ValueError(f"Unsupported H3 base task mode: {task_mode}")


def assemble_h3_prompt(
    task_mode: str,
    integrated_multimodal_description: str,
    overall_soundscape: str,
    non_diegetic_music: str,
    duration: float,
    final_shot: int,
) -> str:
    """Assemble the official three-field H3 base prompt format."""
    description = integrated_multimodal_description.strip()
    if not description:
        raise ValueError("integrated_multimodal_description cannot be empty")
    instruction = alignment_instruction(task_mode, duration, final_shot)
    fields = (
        f"integrated_multimodal_description: {description}\n\n"
        f"overall_soundscape: {overall_soundscape.strip() or 'N/A'}\n\n"
        f"non_diegetic_music: {non_diegetic_music.strip() or 'N/A'}"
    )
    return f"{instruction}\n\n{fields}" if instruction else fields


def story_request(
    idea: str,
    genre: str,
    tone: str,
    duration: int,
    scene_count: int,
    language: str,
    extra_instructions: str,
    variation_seed: int,
) -> str:
    return f"""Develop this idea into an original story suitable for one MiniMax H3
video of {duration} seconds and approximately {scene_count} shot(s).

{context_block(idea=idea, genre=genre, tone=tone, output_language=language,
extra_instructions=extra_instructions, variation_seed=variation_seed)}

Return plain text with these headings: TITLE, LOGLINE, STORY, CHARACTERS,
WORLD AND VISUAL IDENTITY, DIALOGUE AND LYRICS, CONTINUITY LOCKS. Make all action
visible and feasible. Preserve any user-supplied dialogue or lyrics verbatim."""


def scene_request(story: str, duration: int, scene_count: int, extra: str) -> str:
    return f"""Turn this story into exactly {scene_count} MiniMax H3 shots spanning
{duration} seconds.

STORY:
{story}

ADDITIONAL DIRECTION:
{extra or 'None'}

Use [Shot 1] with no timestamp. Begin every later shot with [Shot N] At MM:SS.mmm,
using strictly increasing cut times within the duration. For each shot specify visible
composition, subject appearance and position, chronological action, camera movement,
dialogue or singing, synchronized diegetic sound, and its final state. Keep speaker IDs
(S1), (S2), and so on stable across every shot."""


def h3_prompt_request(
    source_text: str,
    task_mode: str,
    video_type: str,
    shot_structure: str,
    duration: int,
    shot_count: int,
    style: str,
    camera: str,
    audio_dialogue: str,
    references: str,
    constraints: str,
    detail_level: str,
) -> str:
    instruction = alignment_instruction(task_mode, duration, shot_count)
    return f"""Rewrite the source material as one production-ready MiniMax H3 {task_mode}
prompt.

{context_block(source_material=source_text, video_type=video_type,
shot_structure=shot_structure, duration_seconds=duration, shot_count=shot_count,
visual_style=style, camera_direction=camera, dialogue_lyrics_and_audio=audio_dialogue,
reference_notes=references, constraints=constraints, detail_level=detail_level)}

Required first-line instruction:
{instruction or 'None. T2VA begins directly with the three core fields.'}

Return only the final prompt. It must contain, in order:
integrated_multimodal_description, overall_soundscape, non_diegetic_music.
Use [Shot 1] without a timestamp; later shots use strictly increasing
[Shot N] At MM:SS.mmm cut times. Express camera motion naturally with type, amplitude,
and speed where meaningful. Put exact dialogue or lyrics inside
<d>[Language] ...</d>, keep stable speaker IDs, quote visible text, and do not repeat
dialogue in overall_soundscape. Use N/A for music only when none is requested."""


def critique_request(prompt: str, duration: int, rewrite: bool) -> str:
    action = (
        "Return only a corrected complete H3 prompt."
        if rewrite
        else "Return a concise report under FORMAT, TIMING, CONTINUITY, AUDIO, and FIXES."
    )
    return f"""Review this {duration}-second MiniMax H3 prompt against the official format.
Check alignment instructions, required field order, shot numbering and cut times,
camera-motion phrasing, stable speakers, <d>[Language] dialogue tags, verbatim visible
text, reference labels, soundscape separation, music specificity, and achievable pacing.

PROMPT:
{prompt}

{action}"""


def all_in_one_request(
    idea: str,
    task_mode: str,
    video_type: str,
    genre: str,
    tone: str,
    style: str,
    duration: int,
    scene_count: int,
    shot_structure: str,
    language: str,
    references: str,
    extra: str,
    variation_seed: int,
) -> str:
    schema = {
        "story": "Complete concise story with a clear ending",
        "scene_plan": "H3 shot plan using exact shot labels and cut times",
        "h3_prompt": "Complete final H3 prompt with required instruction and fields",
    }
    instruction = alignment_instruction(task_mode, duration, scene_count)
    return f"""Create a complete MiniMax H3 {task_mode} video package.

{context_block(idea=idea, video_type=video_type, genre=genre, tone=tone,
visual_style=style, duration_seconds=duration, shot_count=scene_count,
shot_structure=shot_structure, output_language=language, reference_notes=references,
extra_instructions=extra, variation_seed=variation_seed)}

The h3_prompt must begin with this instruction when it is not None:
{instruction or 'None — begin directly with integrated_multimodal_description.'}

Then include integrated_multimodal_description, overall_soundscape, and
non_diegetic_music in that order. Follow the official H3 rules for shots, cut times,
camera motion, speaker IDs, dialogue tags, visible text, diegetic sound, and music.

Return only valid JSON matching:
{json.dumps(schema, ensure_ascii=False, indent=2)}"""


def vision_all_in_one_request(
    idea: str,
    task_mode: str,
    video_type: str,
    genre: str,
    tone: str,
    style: str,
    duration: int,
    scene_count: int,
    shot_structure: str,
    language: str,
    reference_fidelity: str,
    creativity: str,
    image_labels: list[str],
    extra: str,
    variation_seed: int,
) -> str:
    schema = {
        "reference_analysis": "Visible evidence and the role of every attached image",
        "subject_definitions": "Stable H3 reference labels and visible identity details",
        "retention_analysis": "How each reference is preserved or transferred",
        "story": "Complete concise story with a clear ending",
        "scene_plan": "H3 shot plan with exact cut times",
        "h3_prompt": "Complete final H3 prompt",
    }
    attached = "\n".join(
        f"- Image {index}: {label}" for index, label in enumerate(image_labels, 1)
    ) or "No image is attached."
    base_instruction = (
        alignment_instruction(task_mode, duration, scene_count)
        if task_mode in BASE_TASK_MODES else "Use the six-section full-reference format."
    )
    return f"""Analyze the attached images and create a MiniMax H3 {task_mode} package.
Use only visible evidence for reference definitions, then invent motion and story details
that respect the user's requested fidelity.

{context_block(idea=idea or 'Invent a compelling audiovisual story from the images',
video_type=video_type, genre=genre, tone=tone, visual_style=style,
duration_seconds=duration, shot_count=scene_count, shot_structure=shot_structure,
output_language=language, reference_fidelity=reference_fidelity,
creativity=creativity, extra_instructions=extra, variation_seed=variation_seed)}

ATTACHED IMAGE ORDER:
{attached}

Required H3 format: {base_instruction}

For I2VA, Picture 1 is the exact first frame. For FL2VA, Picture 1 is the first frame
and Picture 2 is the exact last frame. For L2VA, Picture 1 is the exact last frame.
For full-reference mode, h3_prompt must contain subject_definitions, summary,
retention_analysis, detailed_description, overall_soundscape, and non_diegetic_music in
that order. Use <Subject N> for reusable visible content and fixed retention markers.

Return only valid JSON matching:
{json.dumps(schema, ensure_ascii=False, indent=2)}"""


def _json_object(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, re.I | re.S)
    if fenced:
        candidate = fenced.group(1)
    else:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    try:
        value = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def parse_package(text: str) -> tuple[str, str, str]:
    data = _require_package(text, ("story", "scene_plan", "h3_prompt"))
    return (
        str(data.get("story", "")).strip(),
        str(data.get("scene_plan", "")).strip(),
        str(data.get("h3_prompt", "")).strip(),
    )


def parse_vision_package(text: str) -> tuple[str, str, str, str, str, str]:
    data = _require_package(text, (
        "reference_analysis", "subject_definitions", "retention_analysis",
        "story", "scene_plan", "h3_prompt",
    ))
    return tuple(
        str(data.get(key, "")).strip()
        for key in (
            "reference_analysis",
            "subject_definitions",
            "retention_analysis",
            "story",
            "scene_plan",
            "h3_prompt",
        )
    )


def _require_package(text: str, fields: tuple[str, ...]) -> dict[str, str]:
    data = _json_object(text)
    if data is None:
        raise ValueError("Writing model returned invalid package JSON. Increase max_tokens or retry; no prompt was forwarded.")
    invalid = [key for key in fields if not isinstance(data.get(key), str)]
    if invalid or not data.get("h3_prompt", "").strip():
        detail = ", ".join(invalid) or "h3_prompt (empty)"
        raise ValueError(f"Writing model returned missing or invalid package fields: {detail}. Retry; no prompt was forwarded.")
    return data


def validate_h3_prompt(text: str, task_mode: str, duration: float) -> list[str]:
    """Check structural rules locally; creative quality still requires review."""
    issues = []
    fields = (
        ["subject_definitions", "summary", "retention_analysis", "detailed_description",
         "overall_soundscape", "non_diegetic_music"]
        if task_mode == "full-reference" else
        ["integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"]
    )
    headings = list(re.finditer(r"(?m)^\s*(" + "|".join(fields) + r")\s*:", text))
    if [match.group(1) for match in headings] != fields:
        issues.append("Required sections must appear exactly once in the expected order: " + ", ".join(fields))
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        if not text[heading.end():end].strip():
            issues.append(f"Section {heading.group(1)} is empty.")
    timeline_field = "detailed_description" if task_mode == "full-reference" else fields[0]
    timeline = ""
    for index, heading in enumerate(headings):
        if heading.group(1) == timeline_field:
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            timeline = text[heading.end():end]
            break
    shots = list(re.finditer(r"\[Shot\s+(\d+)\]", timeline))
    if not shots:
        issues.append("Timeline must contain [Shot 1].")
    elif [int(shot.group(1)) for shot in shots] != list(range(1, len(shots) + 1)):
        issues.append("Shot numbers must start at 1 and increase consecutively.")
    previous = 0.0
    for index, shot in enumerate(shots):
        end = shots[index + 1].start() if index + 1 < len(shots) else len(timeline)
        segment = timeline[shot.end():end].lstrip()
        timestamp = re.match(r"At (\d{2,}):([0-5]\d)\.(\d{3}),", segment)
        if index == 0:
            if re.match(r"At\s+\d", segment):
                issues.append("Shot 1 must not have a cut timestamp.")
            continue
        if not timestamp:
            issues.append(f"Shot {shot.group(1)} needs an At MM:SS.mmm, cut timestamp.")
            continue
        seconds = int(timestamp[1]) * 60 + int(timestamp[2]) + int(timestamp[3]) / 1000
        if seconds <= previous or seconds >= duration:
            issues.append(f"Shot {shot.group(1)} cut must increase and fall before the video ends.")
        previous = seconds
    if task_mode in ("I2VA", "FL2VA", "L2VA") and shots:
        expected = alignment_instruction(task_mode, duration, int(shots[-1].group(1)))
        if not text.strip().startswith(expected):
            issues.append("Missing or mismatched keyframe-alignment instruction.")
    tags = re.findall(r"</?d>", text)
    depth = 0
    for tag in tags:
        depth += 1 if tag == "<d>" else -1
        if depth not in (0, 1):
            break
    if depth != 0 or tags != [tag for _ in range(len(tags) // 2) for tag in ("<d>", "</d>")]:
        issues.append("Dialogue tags must be paired and must not be nested.")
    if any(not re.match(r"\s*\[[^\]\n]+\]", match.group(1))
           for match in re.finditer(r"<d>(.*?)</d>", text, re.S)):
        issues.append("Each dialogue tag needs a [Language] label.")
    return issues

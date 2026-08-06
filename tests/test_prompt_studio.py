import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PACKAGE_NAME = "comfyui_minimax_H3_prompt_studio"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT.parent))
if PACKAGE_ROOT.name != PACKAGE_NAME:
    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        PACKAGE_ROOT / "__init__.py",
        submodule_search_locations=[str(PACKAGE_ROOT)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = package
    assert spec.loader is not None
    spec.loader.exec_module(package)

from comfyui_minimax_H3_prompt_studio.nodes import (
    CONFIG_TYPE,
    NODE_CLASS_MAPPINGS,
    MiniMaxH3LLMProvider,
    MiniMaxH3TextPreview,
    MiniMaxH3VisionAllInOne,
    encode_comfy_image,
)
from comfyui_minimax_H3_prompt_studio.prompts import (
    alignment_instruction,
    assemble_h3_prompt,
    parse_package,
    parse_vision_package,
)
from comfyui_minimax_H3_prompt_studio.providers import (
    ProviderError,
    discover_models,
    generate_text,
    generate_vision_text,
)


class FakeResponse:
    def __init__(self, data):
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.data if size < 0 else self.data[:size]


def config(provider="Ollama"):
    return {
        "provider": provider,
        "model": "test-model",
        "base_url": "",
        "temperature": 0.7,
        "max_tokens": 512,
        "timeout": 30,
        "disable_ollama_thinking": True,
    }


class PromptTests(unittest.TestCase):
    def test_t2va_has_no_alignment_instruction(self):
        self.assertEqual(alignment_instruction("T2VA", 8, 1), "")

    def test_i2va_uses_exact_first_frame_instruction(self):
        self.assertEqual(
            alignment_instruction("I2VA", 8, 1),
            "For the target video, at 0.00 seconds into the target video, "
            "<Picture 1> (from [Shot 1]) is fully referenced.",
        )

    def test_fl2va_formats_duration_and_final_shot(self):
        result = alignment_instruction("FL2VA", 8, 3)
        self.assertIn("Picture 1 (from Shot 1)", result)
        self.assertIn("Picture 2 (from Shot 3)", result)
        self.assertIn("8.00-second mark", result)

    def test_l2va_uses_last_shot_anchor(self):
        result = alignment_instruction("L2VA", 6, 2)
        self.assertIn("<Picture 1> (from [Shot 2])", result)
        self.assertIn("6.00-second mark", result)

    def test_builder_outputs_three_core_fields_in_order(self):
        result = assemble_h3_prompt("T2VA", "[Shot 1] A fox runs.", "Wind.", "N/A", 5, 1)
        fields = [
            "integrated_multimodal_description:",
            "overall_soundscape:",
            "non_diegetic_music:",
        ]
        positions = [result.index(field) for field in fields]
        self.assertEqual(positions, sorted(positions))

    def test_package_parser(self):
        raw = '```json\n{"story":"S","scene_plan":"P","h3_prompt":"H"}\n```'
        self.assertEqual(parse_package(raw), ("S", "P", "H"))

    def test_vision_package_parser(self):
        raw = json.dumps({
            "reference_analysis": "A",
            "subject_definitions": "D",
            "retention_analysis": "R",
            "story": "S",
            "scene_plan": "P",
            "h3_prompt": "H",
        })
        self.assertEqual(parse_vision_package(raw), ("A", "D", "R", "S", "P", "H"))


class ProviderTests(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_discovers_sorted_ollama_models(self, urlopen):
        urlopen.return_value = FakeResponse(
            {"models": [{"model": "zeta:latest"}, {"name": "Alpha:7b"}]}
        )
        self.assertEqual(discover_models("Ollama"), ["Alpha:7b", "zeta:latest"])

    @patch("urllib.request.urlopen")
    def test_ollama_non_streaming_chat(self, urlopen):
        urlopen.return_value = FakeResponse(
            {"message": {"role": "assistant", "content": "Generated text"}}
        )
        self.assertEqual(generate_text(config(), "system", "user"), "Generated text")
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["think"])

    @patch("urllib.request.urlopen")
    def test_ollama_vision_disables_thinking(self, urlopen):
        urlopen.return_value = FakeResponse(
            {"message": {"role": "assistant", "content": "Vision result"}}
        )
        image = {"label": "Picture 1", "media_type": "image/jpeg", "data": "abc"}
        generate_vision_text(config(), "system", "user", [image])
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertFalse(payload["think"])
        self.assertEqual(payload["messages"][1]["images"], ["abc"])

    @patch("urllib.request.urlopen")
    def test_openai_vision_payload(self, urlopen):
        urlopen.return_value = FakeResponse({"output_text": "Vision result"})
        image = {"label": "Picture 1", "media_type": "image/jpeg", "data": "abc"}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}):
            generate_vision_text(config("OpenAI"), "system", "user", [image])
        content = json.loads(urlopen.call_args.args[0].data)["input"][1]["content"]
        self.assertEqual(content[-1]["type"], "input_image")

    @patch("urllib.request.urlopen")
    def test_anthropic_vision_payload(self, urlopen):
        urlopen.return_value = FakeResponse(
            {"content": [{"type": "text", "text": "Vision result"}]}
        )
        image = {"label": "Picture 1", "media_type": "image/jpeg", "data": "abc"}
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            generate_vision_text(config("Claude"), "system", "user", [image])
        content = json.loads(urlopen.call_args.args[0].data)["messages"][0]["content"]
        self.assertEqual(content[-1]["source"]["type"], "base64")

    @patch("urllib.request.urlopen")
    def test_gemini_vision_payload(self, urlopen):
        urlopen.return_value = FakeResponse({
            "candidates": [{"content": {"parts": [{"text": "Vision result"}]}}]
        })
        image = {"label": "Picture 1", "media_type": "image/jpeg", "data": "abc"}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}):
            generate_vision_text(config("Gemini"), "system", "user", [image])
        parts = json.loads(urlopen.call_args.args[0].data)["contents"][0]["parts"]
        self.assertEqual(parts[-1]["inlineData"]["data"], "abc")

    def test_missing_cloud_key_is_clear(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaisesRegex(ProviderError, "Missing OPENAI_API_KEY"):
                generate_text(config("OpenAI"), "system", "user")


class NodeTests(unittest.TestCase):
    def test_all_nodes_are_registered_and_namespaced(self):
        self.assertEqual(len(NODE_CLASS_MAPPINGS), 9)
        self.assertTrue(all(name.startswith("MiniMaxH3") for name in NODE_CLASS_MAPPINGS))

    def test_provider_uses_minimax_config_type(self):
        self.assertEqual(MiniMaxH3LLMProvider.RETURN_TYPES[0], CONFIG_TYPE)
        self.assertEqual(CONFIG_TYPE, "MINIMAX_H3_LLM_CONFIG")

    def test_text_preview_returns_ui_payload_and_string_passthrough(self):
        result = MiniMaxH3TextPreview().preview("A generated scene")
        self.assertEqual(result["ui"]["text"], ["A generated scene"])
        self.assertEqual(result["result"], ("A generated scene",))

    def test_vision_mode_requirements(self):
        validate = MiniMaxH3VisionAllInOne._image_specs
        with self.assertRaisesRegex(ValueError, "I2VA requires"):
            validate("I2VA", None, None, None, None, "hero", "friend")
        first, last = object(), object()
        specs = validate("FL2VA", first, last, None, None, "hero", "friend")
        self.assertEqual([label for _, label in specs], [
            "Picture 1 — exact first frame at 0.00 seconds",
            "Picture 2 — exact final frame",
        ])

    def test_subject_references_require_full_reference_mode(self):
        with self.assertRaisesRegex(ValueError, "full-reference"):
            MiniMaxH3VisionAllInOne._image_specs(
                "I2VA", object(), None, object(), None, "hero", "friend"
            )

    def test_comfy_image_encoding(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("NumPy is not available")
        image = np.zeros((1, 4, 6, 3), dtype=np.float32)
        encoded = encode_comfy_image(image, "Picture 1")
        self.assertEqual(encoded["media_type"], "image/jpeg")
        self.assertTrue(encoded["data"].startswith("/9j/"))


if __name__ == "__main__":
    unittest.main()

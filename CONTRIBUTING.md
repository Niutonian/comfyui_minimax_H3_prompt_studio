# Contributing

Contributions are welcome.

1. Create a branch from `main`.
2. Keep provider credentials out of source code, workflows, logs, and screenshots.
3. Add or update tests for Python behavior.
4. Run the test suite before opening a pull request:

```powershell
python -m unittest discover -s tests -v
node --check web/model_picker.js
```

Describe the ComfyUI version, provider, model, and reproduction steps for UI or
provider-integration changes. Do not include private prompt content without permission.

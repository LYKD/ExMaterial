# Contributing to ExMaterial

## Before opening a pull request

1. Keep user data out of commits. The `information/` directory is intentionally ignored.
2. Keep source code and filenames in English; user-facing documentation may be bilingual.
3. Preserve the separate raw-XRD and processed-XRD data paths.
4. Run the tests and the compile check before submitting:

   ```powershell
   python -m pytest -q
   python -m compileall -q exmaterial
   ```

## Pull requests

Describe the user-visible change, include tests for calculation or parsing changes, and avoid unrelated reformatting. By contributing, you agree to license your contribution under GPL-3.0-only.

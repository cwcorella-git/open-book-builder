# Repository Guidelines

## Project Structure

The app is Python with PySide6 in `src/open_book_builder/`: one module per tab (`bom_tab.py`, `assembly_tab.py`, `board_tab.py`, `case_tab.py`), `window.py` for the main window, and `build/` for the parsers that turn the source data into the dataset. Source data (BOM CSVs, `component_functions.json`, `assembly.json`, the KiCad and EAGLE boards, case STL files) is in `data/`, with planning data beside it (`offers.json`, `configs.json`, `checklist.json`, `revisions.json`). The dataset is built from it at every start. Tests are in `tests/`; `tests/fixtures/board-dataset.golden.json` is the expected dataset. The earlier React/Tauri tool is kept at git tag `web-tool-final`.

## Build and Development

- `uv venv .venv && uv pip install -e '.[dev]'` installs the app and test tools.
- `uv run open-book-builder` starts the app.
- `uv run pytest` runs the tests (Qt runs offscreen).
- `uv run python -m open_book_builder.build.dataset_build out.json` writes the dataset as JSON.

## Code and Data Conventions

Use standard Python style with four-space indentation and type hints. Follow `~/Desktop/voicebake ui style guide` for every screen: native widgets, no stylesheets or hard-coded colors, Title Case buttons, state as words with tooltips, an empty-state message, sentence-case messages ending with a period. Preserve the documented C2 CSV header alias and the cost-summary treatment; see `CLAUDE.md` for data pitfalls and the expected dataset counts.

## Testing and Verification

Run `uv run pytest` after any change. Data changes make `tests/test_build.py` fail until the golden file is updated on purpose. For visual changes, grab a tab with `QWidget.grab()` under `QT_QPA_PLATFORM=offscreen` and look at the image.

## Commits and Pull Requests

Recent commits use concise imperative subjects (for example, "Add Case tab to the desktop app"); keep subjects direct and around 70 characters or fewer. Commit directly to `main`. Mention the verification commands run.

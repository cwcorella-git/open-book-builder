# Repository Guidelines

## Project Structure

The React and TypeScript frontend is in `src/`: shared state and data helpers live in `src/lib/`, while tab views live in `src/components/`. The Tauri/Rust backend and canonical board/BOM data are in `src-tauri/src/` and `src-tauri/data/`. `scripts/bake-dataset.ts` exports backend data for the web build; `public/board-dataset.json` is generated and gitignored. Case models and related assets are under `public/case/`.

## Build and Development

- `npm install` installs JavaScript dependencies.
- `npm run tauri dev` starts the desktop app.
- `npm run dev` starts Vite; use `npm run dev:web` to bake data first.
- `npm run build` runs TypeScript checks and builds the frontend.
- `npm run build:web` bakes data, checks types, and builds the static site for `/open-book-builder/`.
- `npm run bake-dataset` regenerates the web dataset after canonical data changes.
- `cd src-tauri && cargo check` checks Rust code.

## Code and Data Conventions

Use the existing TypeScript/React patterns and two-space indentation. Keep components in PascalCase and hooks/helpers in the existing kebab-case filenames. Rust types and functions follow standard Rust snake_case conventions. `src/lib/types.ts` mirrors `src-tauri/src/types.rs`; update both when changing the dataset shape. Rust embeds canonical files from `src-tauri/data/`, so rebuild and rebake after editing them. Preserve the documented C2 CSV header alias and cost-summary treatment; see `CLAUDE.md` for data pitfalls and expected dataset counts.

## Testing and Verification

There is no dedicated `test` script. For frontend changes, run `npx tsc --noEmit` or `npm run build`; for backend changes, run `cd src-tauri && cargo check`. Data changes should be followed by `npm run bake-dataset` and a review of the generated dataset sanity values in `README.md`. `screenshots.mjs` provides Playwright screenshot automation for visual checks.

## Commits and Pull Requests

Recent commits use concise imperative subjects (for example, “Add Case viewer tab”); keep subjects direct and around 70 characters or fewer. Pull requests should explain the user-facing change, note relevant data or build effects, link related issues when applicable, and include screenshots for visual changes. Mention the verification commands run.

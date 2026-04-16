//! Open Book Builder — Rust backend.
//!
//! v0 scaffolding. The real dataset loading lives in `dataset.rs`; the
//! subcrates `kicad_pcb`, `kicad_sch`, `eagle`, `bom`, `cogs`, `export`,
//! `types`, `footprint_heights` are introduced incrementally per the plan
//! at `~/.claude/plans/melodic-tinkering-newt.md`.

mod bom;
mod dataset;
mod footprint_heights;
mod kicad_pcb;
mod types;

use types::BoardDataset;

/// Load the canonical `BoardDataset` for the UI. Called at app boot from
/// React via `invoke('load_board_dataset')`.
#[tauri::command]
fn load_board_dataset() -> Result<BoardDataset, String> {
    dataset::load().map_err(|e| e.to_string())
}

/// CLI entry point used by `scripts/bake-dataset.ts` to produce the static
/// web build's `public/board-dataset.json`. Invoked as:
/// `open-book-builder --export-json <out-path>`
pub fn export_json_to_path(out_path: &str) -> Result<(), String> {
    let dataset = dataset::load().map_err(|e| e.to_string())?;
    let json = serde_json::to_string_pretty(&dataset)
        .map_err(|e| format!("serialize error: {}", e))?;
    std::fs::write(out_path, json).map_err(|e| format!("write error: {}", e))?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![load_board_dataset])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

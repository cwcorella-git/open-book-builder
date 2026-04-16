// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // If invoked as `open-book-builder --export-json <path>`, run the bake-dataset
    // flow synchronously and exit — used by scripts/bake-dataset.ts for the static
    // web build. Otherwise start Tauri.
    let args: Vec<String> = std::env::args().collect();
    if args.len() >= 3 && args[1] == "--export-json" {
        let out_path = &args[2];
        match open_book_builder_lib::export_json_to_path(out_path) {
            Ok(()) => {
                eprintln!("Wrote baked dataset to {}", out_path);
                std::process::exit(0);
            }
            Err(e) => {
                eprintln!("Failed to bake dataset: {}", e);
                std::process::exit(1);
            }
        }
    }

    open_book_builder_lib::run()
}

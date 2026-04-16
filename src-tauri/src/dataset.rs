//! Assembles the canonical `BoardDataset`. Static JSONs (discrepancies,
//! assembly steps, component-function lookup) are `include_str!`'d at compile
//! time so they work identically in `tauri dev`, bundled release, and the
//! `--export-json` CLI mode used by the web build. Parsed KiCad/EAGLE/BOM
//! data is merged in by subsequent tasks.
//!
//! This module deliberately does not touch the filesystem: all runtime data
//! either lives in the binary (static JSONs) or will be loaded through its
//! own dedicated module (kicad_pcb, kicad_sch, eagle, bom) that accepts a
//! path and returns parsed structs.

use crate::bom;
use crate::kicad_pcb;
use crate::types::{
    AssemblyStep, BoardData, BoardDataset, BoardId, BoardOutline, Discrepancy,
};
use std::collections::BTreeMap;
use thiserror::Error;

const DISCREPANCIES_JSON: &str = include_str!("../data/discrepancies.json");
const ASSEMBLY_JSON: &str = include_str!("../data/assembly.json");

#[derive(Debug, Error)]
pub enum DatasetError {
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    #[error("json: {0}")]
    Json(#[from] serde_json::Error),
    #[error("csv: {0}")]
    Csv(#[from] csv::Error),
    #[error("kicad: {0}")]
    KiCad(#[from] kicad_pcb::KiCadError),
    // Used from task #3 onward once we're merging real data.
    #[allow(dead_code)]
    #[error("data: {0}")]
    Data(String),
}

pub fn load() -> Result<BoardDataset, DatasetError> {
    let discrepancies: Vec<Discrepancy> = serde_json::from_str(DISCREPANCIES_JSON)?;
    let assembly: Vec<AssemblyStep> = serde_json::from_str(ASSEMBLY_JSON)?;

    let bom_lines = bom::load_all()?;
    let cost_summary = bom::summarize_cost(&bom_lines);

    let mut boards = BTreeMap::new();
    boards.insert(BoardId::C1Main, kicad_pcb::load_c1_board(&bom_lines)?);
    // C2 driver stays empty until task #11 adds the EAGLE parser.
    boards.insert(BoardId::C2Driver, empty_board());

    Ok(BoardDataset {
        boards,
        bom: bom_lines,
        bom_comparison: Vec::new(),
        discrepancies,
        assembly,
        cost_summary,
    })
}

fn empty_board() -> BoardData {
    BoardData {
        components: Vec::new(),
        outline: BoardOutline {
            width_mm: 82.5,
            height_mm: 113.0,
            holes: Vec::new(),
            edge_segments: Vec::new(),
            silkscreen_svg: None,
            silkscreen_svg_bottom: None,
        },
        nets: Vec::new(),
    }
}

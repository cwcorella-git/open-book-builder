//! BOM parsers for the two CSVs we ship: C1 main board (Joey's
//! `1-click-bom.csv` format — distributor columns wide) and C2 driver module
//! (PCBWay PCBA format — narrower, explicit package column). Both converge to
//! `Vec<BomLine>` tagged with `board: BoardId`, with per-MPN metadata
//! (function, datasheet, cost, hero mesh id) merged from
//! `component_functions.json`.
//!
//! The CSVs are `include_str!`'d so this works identically in `tauri dev`,
//! bundled release, and `--export-json`.

use crate::dataset::DatasetError;
use crate::types::{BoardId, BomLine};
use serde::Deserialize;
use std::collections::HashMap;

const BOM_C1_CSV: &str = include_str!("../data/bom-c1-main.csv");
const BOM_C2_CSV: &str = include_str!("../data/bom-c2-driver.csv");
const COMPONENT_FUNCTIONS_JSON: &str = include_str!("../data/component_functions.json");

/// Shape of a single entry in `component_functions.json`. The JSON's
/// top-level `_comment` field is ignored via the skip below.
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ComponentFunction {
    function: String,
    #[serde(default)]
    datasheet_url: Option<String>,
    #[serde(default)]
    unit_cost_usd: Option<f64>,
    #[serde(default)]
    hero_mesh_id: Option<String>,
    #[serde(default)]
    #[allow(dead_code)]
    notes: Option<String>,
}

/// Load the per-MPN function lookup. The JSON is a flat object keyed by MPN,
/// plus a `_comment` sibling we drop.
fn load_function_lookup() -> Result<HashMap<String, ComponentFunction>, DatasetError> {
    let mut raw: HashMap<String, serde_json::Value> =
        serde_json::from_str(COMPONENT_FUNCTIONS_JSON)?;
    raw.remove("_comment");

    let mut out = HashMap::with_capacity(raw.len());
    for (mpn, value) in raw {
        let cf: ComponentFunction = serde_json::from_value(value)?;
        out.insert(mpn, cf);
    }
    Ok(out)
}

/// C1 `1-click-bom.csv` row. Distributor columns kept so we can populate
/// `digikey_pn` / `mouser_pn`.
#[derive(Debug, Deserialize)]
struct C1Row {
    #[serde(rename = "References")]
    references: String,
    #[serde(rename = "Qty")]
    qty: u32,
    #[serde(rename = "Description")]
    description: String,
    #[serde(rename = "Manufacturer")]
    manufacturer: String,
    #[serde(rename = "MPN")]
    mpn: String,
    #[serde(rename = "Digikey")]
    digikey: String,
    #[serde(rename = "Mouser")]
    mouser: String,
}

/// C2 PCBWay BOM row.
#[derive(Debug, Deserialize)]
struct C2Row {
    #[serde(rename = "*Designator")]
    designator: String,
    #[serde(rename = "*Qty")]
    qty: u32,
    #[serde(rename = "Manufacturer")]
    manufacturer: String,
    #[serde(rename = "*Mfg Part #")]
    mpn: String,
    #[serde(rename = "Description / Value")]
    description: String,
    // PCBWay templates include a trailing space on this header name.
    #[serde(rename = "*Package/Footprint ", alias = "*Package/Footprint")]
    footprint: String,
}

/// Split a reference field like `"B1, B2,"` or `"C1, C2, C3"` into its
/// individual designators. Handles trailing commas and extra whitespace.
fn split_refs(raw: &str) -> Vec<String> {
    raw.split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(String::from)
        .collect()
}

/// `OPTIONAL` anywhere in the description means the line is skippable.
fn is_optional(description: &str) -> bool {
    description.to_uppercase().contains("OPTIONAL")
}

fn normalize_optional(s: String) -> Option<String> {
    let trimmed = s.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
}

/// Merge per-MPN metadata into a partially populated `BomLine`. If the MPN
/// isn't in the lookup, we fall back to the CSV description as the
/// `function` field so the UI always renders something.
fn apply_lookup(line: &mut BomLine, lookup: &HashMap<String, ComponentFunction>) {
    if let Some(cf) = lookup.get(&line.mpn) {
        line.function = cf.function.clone();
        line.datasheet_url = cf.datasheet_url.clone();
        line.unit_cost_usd = cf.unit_cost_usd;
        line.hero_mesh_id = cf.hero_mesh_id.clone();
    } else {
        // Fall back to the CSV description so the column is never empty.
        line.function = line.description.clone();
    }
}

fn parse_c1(lookup: &HashMap<String, ComponentFunction>) -> Result<Vec<BomLine>, DatasetError> {
    let mut reader = csv::ReaderBuilder::new()
        .flexible(true)
        .from_reader(BOM_C1_CSV.as_bytes());

    let mut out = Vec::new();
    for result in reader.deserialize::<C1Row>() {
        let row = result?;
        let optional = is_optional(&row.description);
        let mut line = BomLine {
            refs: split_refs(&row.references),
            qty: row.qty,
            description: row.description,
            manufacturer: normalize_optional(row.manufacturer),
            mpn: row.mpn,
            digikey_pn: normalize_optional(row.digikey),
            mouser_pn: normalize_optional(row.mouser),
            optional,
            unit_cost_usd: None,
            live_price: None,
            footprint: None,
            function: String::new(),
            datasheet_url: None,
            hero_mesh_id: None,
            board: BoardId::C1Main,
        };
        apply_lookup(&mut line, lookup);
        out.push(line);
    }
    Ok(out)
}

fn parse_c2(lookup: &HashMap<String, ComponentFunction>) -> Result<Vec<BomLine>, DatasetError> {
    let mut reader = csv::ReaderBuilder::new()
        .flexible(true)
        .from_reader(BOM_C2_CSV.as_bytes());

    let mut out = Vec::new();
    for result in reader.deserialize::<C2Row>() {
        let row = result?;
        let optional = is_optional(&row.description);
        let mut line = BomLine {
            refs: split_refs(&row.designator),
            qty: row.qty,
            description: row.description,
            manufacturer: normalize_optional(row.manufacturer),
            mpn: row.mpn,
            digikey_pn: None,
            mouser_pn: None,
            optional,
            unit_cost_usd: None,
            live_price: None,
            footprint: normalize_optional(row.footprint),
            function: String::new(),
            datasheet_url: None,
            hero_mesh_id: None,
            board: BoardId::C2Driver,
        };
        apply_lookup(&mut line, lookup);
        out.push(line);
    }
    Ok(out)
}

/// Parse both BOMs and return the concatenated list. C1 rows come first so
/// the UI's default ordering groups by board.
pub fn load_all() -> Result<Vec<BomLine>, DatasetError> {
    let lookup = load_function_lookup()?;
    let mut lines = parse_c1(&lookup)?;
    lines.extend(parse_c2(&lookup)?);
    Ok(lines)
}

/// Sum per-unit cost across all **non-optional** C1 lines that have a
/// `unit_cost_usd` set. C2 internal lines are intentionally excluded — the
/// C2 driver module is priced as a single PCBA (OSO-BOOK-C2-01) and its
/// internals shouldn't be double-counted. Lines missing a price on C1 are
/// recorded in `missing_line_items` so the UI can flag the gap; the C2
/// module's own missing PCBA cost is the canonical example.
pub fn summarize_cost(bom: &[BomLine]) -> crate::types::CostSummary {
    let mut per_unit = 0.0_f64;
    let mut missing = Vec::new();

    for line in bom {
        if line.optional || line.board == BoardId::C2Driver {
            continue;
        }
        match line.unit_cost_usd {
            Some(price) => per_unit += price * f64::from(line.qty),
            None => missing.push(format!("c1-main:{}", line.mpn)),
        }
    }

    crate::types::CostSummary {
        per_unit_usd: per_unit,
        per_ten_units_usd: per_unit * 10.0,
        missing_line_items: missing,
    }
}

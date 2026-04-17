//! Loader for the hand-authored BOM comparison data (`bom-comparison.json`).
//! Each entry maps a `bomRef` (MPN) to per-source quantities and unit costs
//! from the three reference BOMs (COGS-LIST, PDF, April 2025 image) alongside
//! the canonical values. `conflict: true` flags rows where sources disagree.

use crate::types::BomComparison;
use thiserror::Error;

const COMPARISON_JSON: &str = include_str!("../data/bom-comparison.json");

#[derive(Debug, Error)]
pub enum BomComparisonError {
    #[error("json: {0}")]
    Json(#[from] serde_json::Error),
}

pub fn load() -> Result<Vec<BomComparison>, BomComparisonError> {
    let entries: Vec<BomComparison> = serde_json::from_str(COMPARISON_JSON)?;
    Ok(entries)
}

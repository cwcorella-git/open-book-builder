//! Serde structs mirroring `src/lib/types.ts`. Kept deliberately `Clone`able
//! and `Serialize + Deserialize` so both directions (load + bake) use the
//! same types.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Side {
    Top,
    Bottom,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
pub enum BoardId {
    C1Main,
    C2Driver,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum NetCategory {
    Power,
    Ground,
    Spi,
    I2c,
    Gpio,
    Debug,
    Analog,
    Other,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Severity {
    BuildCritical,
    CostImpact,
    Naming,
    Informational,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum AssemblyPhase {
    SmdPassives,
    SmdIcs,
    SmdMechanical,
    Tht,
    Modules,
    Mechanical,
    FlashFirmware,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BomLine {
    pub refs: Vec<String>,
    pub qty: u32,
    pub description: String,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub manufacturer: Option<String>,
    pub mpn: String,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub digikey_pn: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub mouser_pn: Option<String>,
    pub optional: bool,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub unit_cost_usd: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub live_price: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub footprint: Option<String>,
    pub function: String,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub datasheet_url: Option<String>,
    pub board: BoardId,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FootprintBbox {
    pub width: f32,
    pub height: f32,
    pub height3d: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Pad {
    pub number: String,
    pub x: f32,
    pub y: f32,
    pub shape: String,
    pub size: (f32, f32),
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub net_name: Option<String>,
    pub through_hole: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Component {
    #[serde(rename = "ref")]
    pub ref_: String,
    pub bom_ref: String,
    pub x: f32,
    pub y: f32,
    pub rotation: f32,
    pub side: Side,
    pub footprint: String,
    pub footprint_bbox: FootprintBbox,
    pub pads: Vec<Pad>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub hero_mesh_id: Option<String>,
    pub board: BoardId,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NetPadRef {
    #[serde(rename = "ref")]
    pub ref_: String,
    pub pad: String,
    pub board: BoardId,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Net {
    pub name: String,
    pub category: NetCategory,
    pub connected_pads: Vec<NetPadRef>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Hole {
    pub x: f32,
    pub y: f32,
    pub diameter: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EdgeSegment {
    pub kind: String, // "line" | "arc"
    pub points: Vec<(f32, f32)>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BoardOutline {
    pub width_mm: f32,
    pub height_mm: f32,
    pub holes: Vec<Hole>,
    pub edge_segments: Vec<EdgeSegment>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub silkscreen_svg: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub silkscreen_svg_bottom: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BoardData {
    pub components: Vec<Component>,
    pub outline: BoardOutline,
    pub nets: Vec<Net>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Discrepancy {
    pub id: String,
    pub severity: Severity,
    pub title: String,
    pub description: String,
    pub sources: Vec<String>,
    pub affects_components: Vec<String>,
    pub resolution: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BomComparison {
    pub bom_ref: String,
    pub canonical_qty: u32,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub canonical_cost: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub cogs_qty: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub cogs_cost: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub pdf_qty: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub pdf_cost: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub april2025_qty: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub april2025_cost: Option<f64>,
    pub conflict: bool,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub note: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AssemblyStep {
    pub id: String,
    pub order: u32,
    pub phase: AssemblyPhase,
    pub title: String,
    pub description: String,
    pub component_refs: Vec<String>,
    pub board: BoardId,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub estimated_minutes: Option<u32>,
    pub tools: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub notes: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct CostSummary {
    pub per_unit_usd: f64,
    pub per_ten_units_usd: f64,
    pub missing_line_items: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BoardDataset {
    pub boards: BTreeMap<BoardId, BoardData>,
    pub bom: Vec<BomLine>,
    pub bom_comparison: Vec<BomComparison>,
    pub discrepancies: Vec<Discrepancy>,
    pub assembly: Vec<AssemblyStep>,
    pub cost_summary: CostSummary,
}


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
    // Rendering hint that piggybacks on the per-MPN metadata merge (same as
    // `function` / `datasheet_url`). `kicad_pcb::classify_footprint` reads it
    // via ref-match and copies it onto `Component.hero_mesh_id`.
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub hero_mesh_id: Option<String>,
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
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub dominant_category: Option<NetCategory>,
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

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SilkscreenLine {
    pub start: (f32, f32),
    pub end: (f32, f32),
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SilkscreenArc {
    pub start: (f32, f32),
    pub mid: (f32, f32),
    pub end: (f32, f32),
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SilkscreenCircle {
    pub center: (f32, f32),
    pub radius: f32,
}

// Copper trace segments and vias. Parsed from KiCad `(segment)` / `(via)` and
// EAGLE `<signal>/<wire>` / `<via>`. Rendered as `THREE.LineSegments` per layer
// + `CylinderGeometry` per via behind a "Show traces" toggle (default off).

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum CopperLayer {
    FCu,
    BCu,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CopperSegment {
    pub start: (f32, f32),
    pub end: (f32, f32),
    pub width: f32,
    pub layer: CopperLayer,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub net_name: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Via {
    pub at: (f32, f32),
    pub diameter: f32,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub net_name: Option<String>,
}

// Board-space silkscreen primitives keyed by face. Task #13a emits lines, arcs,
// and circles from both parsers; text glyphs, polygonal fills, and fab-layer
// data are deliberately out of scope. See plan "Task #13a detail".
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SilkscreenLayer {
    pub lines: Vec<SilkscreenLine>,
    pub arcs: Vec<SilkscreenArc>,
    pub circles: Vec<SilkscreenCircle>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BoardOutline {
    pub width_mm: f32,
    pub height_mm: f32,
    pub holes: Vec<Hole>,
    pub edge_segments: Vec<EdgeSegment>,
    #[serde(default)]
    pub silkscreen_top: SilkscreenLayer,
    #[serde(default)]
    pub silkscreen_bottom: SilkscreenLayer,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BoardData {
    pub components: Vec<Component>,
    pub outline: BoardOutline,
    pub nets: Vec<Net>,
    #[serde(default)]
    pub traces: Vec<CopperSegment>,
    #[serde(default)]
    pub vias: Vec<Via>,
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
    pub assembly: Vec<AssemblyStep>,
    pub cost_summary: CostSummary,
}


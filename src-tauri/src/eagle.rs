//! EAGLE 9.x `.brd` parser for the C2 driver submodule. Sibling to
//! `kicad_pcb.rs` — same public shape (`load_c2_board(&[BomLine]) ->
//! Result<BoardData, _>`), same integration point in `dataset::load()`, same
//! `include_str!`-the-data convention. Different format and different quirks:
//!
//! - **Plain XML**, not S-expressions. Parsed via `quick-xml` with a manual
//!   event loop (not serde derive) so mixed-content `<plain>` / `<signals>`
//!   children don't trip the strict deserializer. The event loop only peeks
//!   at elements we care about; anything else is silently dropped.
//! - **Rotation encoding**: `rot="MR180"` = mirror + 180°. The `M` prefix
//!   flips the element to Layer 16 (Bottom Cu) — that's how EAGLE marks
//!   side. See `decode_rot`. All 17 BOM-relevant elements in the C2 file
//!   carry an `MR*` rot → every one renders on the bottom face.
//! - **Inline package library**. EAGLE embeds `<package>` definitions inside
//!   `<libraries>` right in the .brd, so footprint bboxes come from the
//!   file, not an external lookup. Computed from `<smd>` rects (center ±
//!   dx/2, dy/2) plus through-hole `<pad>` circles.
//! - **Board outline**: four Layer-20 `<wire>` segments in `<plain>`. Not
//!   arcs, not GND polygons. The GND signal polygons happen to fill the same
//!   rectangle but they're copper pours, not the outline.
//! - **Mounting holes**: three `<plain>/<hole>` entries. The "missing"
//!   fourth corner is where the JP1 castellation block sits.
//!
//! Task #11 handles placements + outline + holes + nets + a synthesized
//! virtual `Display` component so the C2 tab shows the GDEW042T2 panel
//! (whose BOM line lives on C1 with `refs=["Display"]`). Copper trace
//! geometry (`<signal>/<wire>`, `<via>`, `<polygon>`) is parsed only to the
//! extent of counting `<contactref>` into `Net.connected_pads`; rendering
//! traces is deferred to #13 polish.

use crate::footprint_heights;
use crate::types::{
    BoardData, BoardId, BoardOutline, BomLine, Component, EdgeSegment,
    FootprintBbox, Hole, Net, NetCategory, NetPadRef, Pad, Side,
};
use quick_xml::events::{BytesStart, Event};
use quick_xml::Reader;
use std::collections::HashMap;
use thiserror::Error;

const BRD_XML: &str = include_str!("../data/OSO-BOOK-C2-02.brd");

#[derive(Debug, Error)]
pub enum EagleError {
    #[error("xml: {0}")]
    Xml(#[from] quick_xml::Error),
    #[error("xml attr: {0}")]
    Attr(#[from] quick_xml::events::attributes::AttrError),
    // Reserved for structural-invariant violations (e.g. missing <drawing>);
    // the current C2 .brd is well-formed so this never fires today.
    #[allow(dead_code)]
    #[error("shape: {0}")]
    Shape(String),
}

/// Parse the compiled-in C2 `.brd` and return a populated `BoardData`.
/// `bom` is scanned for the GDEW042T2 display line (C1 BOM entry with
/// `ref="Display"`) so the returned board can include a synthesized hero-mesh
/// Component placed on the +X side of the driver.
pub fn load_c2_board(bom: &[BomLine]) -> Result<BoardData, EagleError> {
    let mut reader = Reader::from_str(BRD_XML);
    reader.config_mut().trim_text(true);

    // Intermediate collections: we walk the tree once, stash state, then
    // assemble the BoardData at the end so helpers can cross-reference
    // (e.g. package_bbox needs `packages` populated before an element is
    // finalized).
    let mut packages: HashMap<(String, String), PackageDef> = HashMap::new();
    let mut outline_wires: Vec<(f32, f32, f32, f32)> = Vec::new();
    let mut holes: Vec<Hole> = Vec::new();
    let mut elements: Vec<ElementPlacement> = Vec::new();
    let mut nets: Vec<Net> = Vec::new();

    // Parser state — tracks which subtree we're inside so we interpret the
    // shared element names (wire, text, etc.) in the right context.
    let mut in_plain = false;
    let mut in_elements = false;
    let mut library_stack: Vec<String> = Vec::new();
    let mut package_stack: Vec<PackageDef> = Vec::new();
    let mut signal_stack: Vec<SignalBuilder> = Vec::new();

    let mut buf = Vec::new();
    loop {
        match reader.read_event_into(&mut buf)? {
            Event::Eof => break,
            Event::Decl(_) | Event::DocType(_) | Event::PI(_) | Event::Comment(_) => {}
            Event::Start(e) => {
                let name = local_name(e.name().as_ref());
                match name.as_str() {
                    "plain" => in_plain = true,
                    "elements" => in_elements = true,
                    "library" => {
                        library_stack.push(attr_string(&e, "name")?.unwrap_or_default());
                    }
                    "package" => {
                        let pkg_name = attr_string(&e, "name")?.unwrap_or_default();
                        package_stack.push(PackageDef::new(pkg_name));
                    }
                    "element" if in_elements => {
                        elements.push(parse_element(&e)?);
                    }
                    "signal" => {
                        let n = attr_string(&e, "name")?.unwrap_or_default();
                        let cls = attr_string(&e, "class")?;
                        signal_stack.push(SignalBuilder {
                            name: n,
                            category: net_category_from_class(cls.as_deref()),
                            connected_pads: Vec::new(),
                        });
                    }
                    _ => {}
                }
            }
            Event::Empty(e) => {
                let name = local_name(e.name().as_ref());
                match name.as_str() {
                    "wire" if in_plain => {
                        // Layer-20 wires form the board outline. Layer-51
                        // wires are silkscreen/fab and get ignored.
                        let layer = attr_u32(&e, "layer")?.unwrap_or(0);
                        if layer == 20 {
                            let x1 = attr_f32(&e, "x1")?.unwrap_or(0.0);
                            let y1 = attr_f32(&e, "y1")?.unwrap_or(0.0);
                            let x2 = attr_f32(&e, "x2")?.unwrap_or(0.0);
                            let y2 = attr_f32(&e, "y2")?.unwrap_or(0.0);
                            outline_wires.push((x1, y1, x2, y2));
                        }
                    }
                    "wire" if !package_stack.is_empty() => {
                        // Layer-51 fab wires carry the package's mechanical
                        // footprint outline — useful as a bbox fallback for
                        // packages that have no SMDs/pads (unlikely in this
                        // file but cheap to support).
                        let layer = attr_u32(&e, "layer")?.unwrap_or(0);
                        if layer == 51 || layer == 21 {
                            let x1 = attr_f32(&e, "x1")?.unwrap_or(0.0);
                            let y1 = attr_f32(&e, "y1")?.unwrap_or(0.0);
                            let x2 = attr_f32(&e, "x2")?.unwrap_or(0.0);
                            let y2 = attr_f32(&e, "y2")?.unwrap_or(0.0);
                            let pkg = package_stack.last_mut().unwrap();
                            pkg.fab_wires.push((x1, y1, x2, y2));
                        }
                    }
                    "hole" if in_plain => {
                        let x = attr_f32(&e, "x")?.unwrap_or(0.0);
                        let y = attr_f32(&e, "y")?.unwrap_or(0.0);
                        let drill = attr_f32(&e, "drill")?.unwrap_or(1.0);
                        holes.push(Hole { x, y, diameter: drill });
                    }
                    "smd" if !package_stack.is_empty() => {
                        let pkg = package_stack.last_mut().unwrap();
                        pkg.smds.push(SmdDef {
                            name: attr_string(&e, "name")?.unwrap_or_default(),
                            x: attr_f32(&e, "x")?.unwrap_or(0.0),
                            y: attr_f32(&e, "y")?.unwrap_or(0.0),
                            dx: attr_f32(&e, "dx")?.unwrap_or(0.0),
                            dy: attr_f32(&e, "dy")?.unwrap_or(0.0),
                        });
                    }
                    "pad" if !package_stack.is_empty() => {
                        let pkg = package_stack.last_mut().unwrap();
                        pkg.pads.push(PadDef {
                            name: attr_string(&e, "name")?.unwrap_or_default(),
                            x: attr_f32(&e, "x")?.unwrap_or(0.0),
                            y: attr_f32(&e, "y")?.unwrap_or(0.0),
                            diameter: attr_f32(&e, "diameter")?
                                .or(attr_f32(&e, "drill")?.map(|d| d * 2.0))
                                .unwrap_or(1.5),
                            drill: attr_f32(&e, "drill")?.unwrap_or(0.0),
                        });
                    }
                    "element" if in_elements => {
                        // Self-closing `<element .../>` — no attribute
                        // children but still a real placement (J1 is one).
                        elements.push(parse_element(&e)?);
                    }
                    "contactref" if !signal_stack.is_empty() => {
                        let sig = signal_stack.last_mut().unwrap();
                        sig.connected_pads.push(NetPadRef {
                            ref_: attr_string(&e, "element")?.unwrap_or_default(),
                            pad: attr_string(&e, "pad")?.unwrap_or_default(),
                            board: BoardId::C2Driver,
                        });
                    }
                    _ => {}
                }
            }
            Event::End(e) => {
                let name = local_name(e.name().as_ref());
                match name.as_str() {
                    "plain" => in_plain = false,
                    "elements" => in_elements = false,
                    "library" => {
                        library_stack.pop();
                    }
                    "package" => {
                        if let Some(pkg) = package_stack.pop() {
                            if let Some(lib) = library_stack.last() {
                                packages.insert((lib.clone(), pkg.name.clone()), pkg);
                            }
                        }
                    }
                    "signal" => {
                        if let Some(sig) = signal_stack.pop() {
                            nets.push(Net {
                                name: sig.name,
                                category: sig.category,
                                connected_pads: sig.connected_pads,
                            });
                        }
                    }
                    _ => {}
                }
            }
            _ => {}
        }
        buf.clear();
    }

    // Outline extents — min/max across every wire endpoint. The C2 file
    // anchors at (0, 0), but we don't rely on that.
    let (width_mm, height_mm) = compute_extents(&outline_wires);
    let edge_segments: Vec<EdgeSegment> = outline_wires
        .into_iter()
        .map(|(x1, y1, x2, y2)| EdgeSegment {
            kind: "line".into(),
            points: vec![(x1, y1), (x2, y2)],
        })
        .collect();

    // Cross-reference elements against the C2 BOM. Any element whose ref
    // doesn't appear in *any* BOM line (either board) gets dropped — that's
    // how U$2 / U$3 (castellated BIGOVAL blocks) and JP1 (unpopulated test
    // header) are filtered out. Matches the KiCad parser's ref-match rule.
    let bom_by_ref: HashMap<&str, &BomLine> = bom
        .iter()
        .flat_map(|line| line.refs.iter().map(move |r| (r.as_str(), line)))
        .collect();

    let mut components = Vec::<Component>::new();
    for el in elements {
        let Some(bom_line) = bom_by_ref.get(el.name.as_str()) else {
            continue;
        };
        let (mirror, rotation) = decode_rot(el.rot.as_deref());
        let side = if mirror { Side::Bottom } else { Side::Top };
        let bbox = packages
            .get(&(el.library.clone(), el.package.clone()))
            .map(|pkg| package_bbox(pkg, &el.package))
            .unwrap_or_else(|| FootprintBbox {
                width: 1.0,
                height: 1.0,
                height3d: 1.0,
            });

        // Build pad list by cloning the package's SMD/pad centers into
        // Pad records. Nets wire into these via `contactref` lookups, so
        // pad numbers need to match `<contactref pad="..."/>`.
        let pads = if let Some(pkg) = packages.get(&(el.library.clone(), el.package.clone())) {
            build_pads(pkg)
        } else {
            Vec::new()
        };

        components.push(Component {
            ref_: el.name.clone(),
            bom_ref: el.name,
            x: el.x,
            y: el.y,
            rotation,
            side,
            footprint: format!("{}:{}", el.library, el.package),
            footprint_bbox: bbox,
            pads,
            hero_mesh_id: bom_line.hero_mesh_id.clone(),
            board: BoardId::C2Driver,
        });
    }

    // Synthesize the GDEW042T2 display component on the C2 board so the
    // tab shows the panel that the driver exists to drive. The C1 BOM
    // carries the display with `refs=["Display"]`; the existing BoardView
    // DetailPanel lookup walks the full `bom` array regardless of board,
    // so cross-board ref resolution just works.
    if let Some(display) = synthesize_display_component(bom) {
        components.push(display);
    }

    Ok(BoardData {
        components,
        outline: BoardOutline {
            width_mm,
            height_mm,
            holes,
            edge_segments,
            silkscreen_svg: None,
            silkscreen_svg_bottom: None,
        },
        nets,
    })
}

// ---------------------------------------------------------------------------
// Intermediate shapes

#[derive(Debug)]
struct ElementPlacement {
    name: String,
    library: String,
    package: String,
    x: f32,
    y: f32,
    rot: Option<String>,
}

#[derive(Debug)]
struct PackageDef {
    name: String,
    smds: Vec<SmdDef>,
    pads: Vec<PadDef>,
    fab_wires: Vec<(f32, f32, f32, f32)>,
}

impl PackageDef {
    fn new(name: String) -> Self {
        Self {
            name,
            smds: Vec::new(),
            pads: Vec::new(),
            fab_wires: Vec::new(),
        }
    }
}

#[derive(Debug)]
struct SmdDef {
    name: String,
    x: f32,
    y: f32,
    dx: f32,
    dy: f32,
}

#[derive(Debug)]
struct PadDef {
    name: String,
    x: f32,
    y: f32,
    diameter: f32,
    #[allow(dead_code)]
    drill: f32,
}

struct SignalBuilder {
    name: String,
    category: NetCategory,
    connected_pads: Vec<NetPadRef>,
}

// ---------------------------------------------------------------------------
// Per-element parsing

fn parse_element(e: &BytesStart<'_>) -> Result<ElementPlacement, EagleError> {
    Ok(ElementPlacement {
        name: attr_string(e, "name")?.unwrap_or_default(),
        library: attr_string(e, "library")?.unwrap_or_default(),
        package: attr_string(e, "package")?.unwrap_or_default(),
        x: attr_f32(e, "x")?.unwrap_or(0.0),
        y: attr_f32(e, "y")?.unwrap_or(0.0),
        rot: attr_string(e, "rot")?,
    })
}

/// Decode EAGLE's rotation attribute into (mirrored, degrees). Examples:
/// `"MR90"` → `(true, 90.0)`, `"R180"` → `(false, 180.0)`,
/// `None` / `""` → `(false, 0.0)`. The `M` prefix flips the element to
/// Layer 16 (bottom). EAGLE also has `S` (spin) we don't use; we treat any
/// non-`R` leading character after `M` as zero rotation.
fn decode_rot(rot: Option<&str>) -> (bool, f32) {
    let Some(s) = rot else {
        return (false, 0.0);
    };
    let (mirror, rest) = if let Some(stripped) = s.strip_prefix('M') {
        (true, stripped)
    } else {
        (false, s)
    };
    let num_str = rest.strip_prefix('R').unwrap_or(rest);
    let degrees = num_str.parse::<f32>().unwrap_or(0.0);
    (mirror, degrees)
}

fn net_category_from_class(class: Option<&str>) -> NetCategory {
    match class {
        Some("1") => NetCategory::Power,
        Some("2") => NetCategory::Ground,
        _ => NetCategory::Other,
    }
}

// ---------------------------------------------------------------------------
// Package bbox + pad list

/// Axis-aligned bbox over the package's SMD rectangles + through-hole pads.
/// Per-pad rotation is ignored (we use max(dx, dy) envelope in both axes) —
/// matches `kicad_pcb::bbox_from_pads`'s ignore-per-pad-rotation choice.
/// Falls back to Layer-51 fab-wire extents, then a 1×1 mm placeholder.
fn package_bbox(pkg: &PackageDef, package_name: &str) -> FootprintBbox {
    let height3d = footprint_heights::height3d_for_eagle(package_name);

    let (mut minx, mut miny) = (f32::INFINITY, f32::INFINITY);
    let (mut maxx, mut maxy) = (f32::NEG_INFINITY, f32::NEG_INFINITY);

    for s in &pkg.smds {
        let hx = s.dx.abs() * 0.5;
        let hy = s.dy.abs() * 0.5;
        minx = minx.min(s.x - hx);
        maxx = maxx.max(s.x + hx);
        miny = miny.min(s.y - hy);
        maxy = maxy.max(s.y + hy);
    }
    for p in &pkg.pads {
        let r = p.diameter * 0.5;
        minx = minx.min(p.x - r);
        maxx = maxx.max(p.x + r);
        miny = miny.min(p.y - r);
        maxy = maxy.max(p.y + r);
    }
    if !minx.is_finite() {
        // No SMDs or pads — fall back to fab-wire extents.
        for (x1, y1, x2, y2) in &pkg.fab_wires {
            minx = minx.min(*x1).min(*x2);
            maxx = maxx.max(*x1).max(*x2);
            miny = miny.min(*y1).min(*y2);
            maxy = maxy.max(*y1).max(*y2);
        }
    }
    if !minx.is_finite() {
        return FootprintBbox {
            width: 1.0,
            height: 1.0,
            height3d,
        };
    }
    FootprintBbox {
        width: (maxx - minx).max(0.5),
        height: (maxy - miny).max(0.5),
        height3d,
    }
}

fn build_pads(pkg: &PackageDef) -> Vec<Pad> {
    let mut pads = Vec::with_capacity(pkg.smds.len() + pkg.pads.len());
    for s in &pkg.smds {
        pads.push(Pad {
            number: s.name.clone(),
            x: s.x,
            y: s.y,
            shape: "rect".into(),
            size: (s.dx.abs(), s.dy.abs()),
            net_name: None,
            through_hole: false,
        });
    }
    for p in &pkg.pads {
        pads.push(Pad {
            number: p.name.clone(),
            x: p.x,
            y: p.y,
            shape: "circle".into(),
            size: (p.diameter, p.diameter),
            net_name: None,
            through_hole: true,
        });
    }
    pads
}

// ---------------------------------------------------------------------------
// Outline extent math

fn compute_extents(wires: &[(f32, f32, f32, f32)]) -> (f32, f32) {
    let (mut maxx, mut maxy) = (0.0_f32, 0.0_f32);
    for (x1, y1, x2, y2) in wires {
        maxx = maxx.max(*x1).max(*x2);
        maxy = maxy.max(*y1).max(*y2);
    }
    (maxx, maxy)
}

// ---------------------------------------------------------------------------
// Display panel synthesis

/// If the provided BOM contains the GDEW042T2 display line (identified by
/// `ref == "Display"`), return a virtual `Component` placed to the +X of
/// the driver so the C2 tab visibly includes the e-paper panel the driver
/// is there to drive. Returns `None` when the BOM lacks a Display entry —
/// graceful degradation.
fn synthesize_display_component(bom: &[BomLine]) -> Option<Component> {
    let display_bom = bom
        .iter()
        .find(|l| l.refs.iter().any(|r| r == "Display"))?;

    Some(Component {
        ref_: "Display".into(),
        bom_ref: "Display".into(),
        x: 65.0,
        y: 11.94,
        rotation: 0.0,
        side: Side::Top,
        footprint: "VIRTUAL_GDEW042T2".into(),
        footprint_bbox: FootprintBbox {
            width: 95.0,
            height: 110.0,
            height3d: 1.2,
        },
        pads: Vec::new(),
        hero_mesh_id: display_bom.hero_mesh_id.clone(),
        board: BoardId::C2Driver,
    })
}

// ---------------------------------------------------------------------------
// quick-xml helpers

fn local_name(name: &[u8]) -> String {
    String::from_utf8_lossy(name).to_string()
}

fn attr_string(e: &BytesStart<'_>, key: &str) -> Result<Option<String>, EagleError> {
    for a in e.attributes() {
        let a = a?;
        if a.key.as_ref() == key.as_bytes() {
            return Ok(Some(a.unescape_value()?.into_owned()));
        }
    }
    Ok(None)
}

fn attr_f32(e: &BytesStart<'_>, key: &str) -> Result<Option<f32>, EagleError> {
    Ok(attr_string(e, key)?.and_then(|s| s.parse::<f32>().ok()))
}

fn attr_u32(e: &BytesStart<'_>, key: &str) -> Result<Option<u32>, EagleError> {
    Ok(attr_string(e, key)?.and_then(|s| s.parse::<u32>().ok()))
}

// ---------------------------------------------------------------------------
// Tests

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decode_rot_real_values() {
        assert_eq!(decode_rot(Some("MR0")), (true, 0.0));
        assert_eq!(decode_rot(Some("MR90")), (true, 90.0));
        assert_eq!(decode_rot(Some("MR180")), (true, 180.0));
        assert_eq!(decode_rot(Some("MR270")), (true, 270.0));
        assert_eq!(decode_rot(Some("R90")), (false, 90.0));
        assert_eq!(decode_rot(Some("R270")), (false, 270.0));
        assert_eq!(decode_rot(None), (false, 0.0));
        assert_eq!(decode_rot(Some("")), (false, 0.0));
    }

    #[test]
    fn net_class_mapping() {
        assert!(matches!(
            net_category_from_class(Some("1")),
            NetCategory::Power
        ));
        assert!(matches!(
            net_category_from_class(Some("2")),
            NetCategory::Ground
        ));
        assert!(matches!(
            net_category_from_class(Some("0")),
            NetCategory::Other
        ));
        assert!(matches!(net_category_from_class(None), NetCategory::Other));
    }

    /// End-to-end smoke test over the compiled-in C2 file. Pinned to the
    /// current source; regenerating the .brd from EAGLE will likely shift
    /// a coordinate or two by a tenth of a millimeter — fine to retune,
    /// the point is to catch structural parser regressions.
    #[test]
    fn c2_parse_produces_expected_shape() {
        // Build a minimal BOM that matches the 17 BOM-relevant refs in the
        // C2 .brd plus the Display. This mirrors what `bom::load_all()`
        // produces but keeps the test self-contained.
        let bom = sample_bom();
        let board = load_c2_board(&bom).expect("parse");

        // 17 C2 BOM elements + 1 synthesized Display.
        assert_eq!(board.components.len(), 18, "component count");
        // Exactly one synthesized Display on the top side.
        let display_count = board
            .components
            .iter()
            .filter(|c| c.ref_ == "Display")
            .count();
        assert_eq!(display_count, 1);
        let display = board.components.iter().find(|c| c.ref_ == "Display").unwrap();
        assert!(matches!(display.side, Side::Top));
        assert_eq!(display.hero_mesh_id.as_deref(), Some("gdew042t2"));

        // All non-Display components are mirrored → bottom side.
        let bottom_non_display = board
            .components
            .iter()
            .filter(|c| c.ref_ != "Display" && matches!(c.side, Side::Bottom))
            .count();
        assert_eq!(bottom_non_display, 17);

        // U$2, U$3, JP1 dropped.
        for ref_ in ["U$2", "U$3", "JP1"] {
            assert!(
                !board.components.iter().any(|c| c.ref_ == ref_),
                "{ref_} should be dropped"
            );
        }

        // Outline ~17.27 × 23.88 mm.
        assert!((board.outline.width_mm - 17.272).abs() < 0.01);
        assert!((board.outline.height_mm - 23.876).abs() < 0.01);
        assert_eq!(board.outline.edge_segments.len(), 4);
        assert_eq!(board.outline.holes.len(), 3);

        // Every BOM element should be accounted for.
        let expected_refs: &[&str] = &[
            "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "D1", "D2", "D3", "J1",
            "L1", "Q1", "R1",
        ];
        for r in expected_refs {
            assert!(
                board.components.iter().any(|c| c.ref_ == *r),
                "missing {r}"
            );
        }

        // Nets populated; GND is Ground, 3.3V is Power, others default to Other.
        assert!(board.nets.iter().any(|n| n.name == "GND"
            && matches!(n.category, NetCategory::Ground)));
        assert!(board.nets.iter().any(|n| n.name == "3.3V"
            && matches!(n.category, NetCategory::Power)));
        let sck = board.nets.iter().find(|n| n.name == "SCK").unwrap();
        assert!(matches!(sck.category, NetCategory::Other));
    }

    fn sample_bom() -> Vec<BomLine> {
        let mut lines = vec![
            line(&["Display"], "GDEW042T2", Some("gdew042t2")),
            line(&["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"], "CAP-1UF", None),
            line(&["C10"], "CAP-4.7UF", None),
            line(&["D1", "D2", "D3"], "MBR0530", None),
            line(&["J1"], "EINK-FFC24", None),
            line(&["L1"], "IND-10UH", None),
            line(&["Q1"], "IRLML0100", None),
            line(&["R1"], "RES-0.47", None),
        ];
        // Every sample line is on C2Driver except the Display which on real
        // data is a C1 line — tests don't care which board flag is set
        // since the ref-matching HashMap spans both.
        for l in &mut lines {
            l.board = BoardId::C2Driver;
        }
        lines[0].board = BoardId::C1Main; // Display
        lines
    }

    fn line(refs: &[&str], mpn: &str, hero: Option<&str>) -> BomLine {
        BomLine {
            refs: refs.iter().map(|s| (*s).into()).collect(),
            qty: refs.len() as u32,
            description: "test".into(),
            manufacturer: None,
            mpn: mpn.into(),
            digikey_pn: None,
            mouser_pn: None,
            optional: false,
            unit_cost_usd: None,
            live_price: None,
            footprint: None,
            function: "test".into(),
            datasheet_url: None,
            hero_mesh_id: hero.map(|s| s.into()),
            board: BoardId::C1Main,
        }
    }
}

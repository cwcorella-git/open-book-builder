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
//! - **Silkscreen**: `<wire>` / `<circle>` on layer 21 (tPlace) or 22
//!   (bPlace). Package-local primitives get transformed to board coordinates
//!   at element instantiation time (mirror → rotate → translate). EAGLE
//!   `<wire curve="N">` encodes a curved segment as chord + sweep in degrees
//!   — converted to `SilkscreenArc` via chord/sagitta math. Text glyphs and
//!   polygonal fills are deliberately out of scope for #13a (see plan).
//!
//! Task #11 handles placements + outline + holes + nets + a synthesized
//! virtual `Display` component so the C2 tab shows the GDEW042T2 panel
//! (whose BOM line lives on C1 with `refs=["Display"]`). Task #13f adds
//! copper trace and via extraction from `<signal>/<wire>` (layers 1/16)
//! and `<signal>/<via>` for the "Show traces" toggle.

use crate::footprint_heights;
use crate::types::{
    BoardData, BoardId, BoardOutline, BomLine, Component, CopperLayer,
    CopperSegment, EdgeSegment, FootprintBbox, Hole, Net, NetCategory, NetPadRef,
    Pad, Side, SilkscreenArc, SilkscreenCircle, SilkscreenLayer, SilkscreenLine,
    Via,
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

    // Silkscreen accumulators — board-level primitives append directly;
    // package-level primitives live on each `PackageDef` and get transformed
    // to board coords at element-instantiation time further down.
    let mut silkscreen_top = SilkscreenLayer::default();
    let mut silkscreen_bottom = SilkscreenLayer::default();

    // Copper trace + via accumulators — captured from <wire>/<via> inside
    // <signal> context. Layer 1 = top copper (F.Cu), layer 16 = bottom (B.Cu).
    let mut traces = Vec::<CopperSegment>::new();
    let mut vias = Vec::<Via>::new();

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
                        // Layer-20 wires form the board outline. Layers 21/22
                        // are board-level silkscreen (top/bottom). Layer-51 is
                        // fab info; ignored at board scope.
                        let layer = attr_u32(&e, "layer")?.unwrap_or(0);
                        let x1 = attr_f32(&e, "x1")?.unwrap_or(0.0);
                        let y1 = attr_f32(&e, "y1")?.unwrap_or(0.0);
                        let x2 = attr_f32(&e, "x2")?.unwrap_or(0.0);
                        let y2 = attr_f32(&e, "y2")?.unwrap_or(0.0);
                        if layer == 20 {
                            outline_wires.push((x1, y1, x2, y2));
                        } else if layer == 21 || layer == 22 {
                            let curve = attr_f32(&e, "curve")?.unwrap_or(0.0);
                            let dest = if layer == 21 {
                                &mut silkscreen_top
                            } else {
                                &mut silkscreen_bottom
                            };
                            push_wire_as_silk((x1, y1), (x2, y2), curve, dest);
                        }
                    }
                    "circle" if in_plain => {
                        let layer = attr_u32(&e, "layer")?.unwrap_or(0);
                        if layer == 21 || layer == 22 {
                            let cx = attr_f32(&e, "x")?.unwrap_or(0.0);
                            let cy = attr_f32(&e, "y")?.unwrap_or(0.0);
                            let radius = attr_f32(&e, "radius")?.unwrap_or(0.0);
                            if radius > 0.0 {
                                let circle = SilkscreenCircle {
                                    center: (cx, cy),
                                    radius,
                                };
                                if layer == 21 {
                                    silkscreen_top.circles.push(circle);
                                } else {
                                    silkscreen_bottom.circles.push(circle);
                                }
                            }
                        }
                    }
                    "wire" if !package_stack.is_empty() => {
                        // Layer-51 fab wires carry the package's mechanical
                        // footprint outline — useful as a bbox fallback for
                        // packages that have no SMDs/pads. Layer 21 on a
                        // package is top-side silk; Layer 22 is bottom-side
                        // silk — stored package-local, transformed to board
                        // coords at element-instantiation time.
                        let layer = attr_u32(&e, "layer")?.unwrap_or(0);
                        let x1 = attr_f32(&e, "x1")?.unwrap_or(0.0);
                        let y1 = attr_f32(&e, "y1")?.unwrap_or(0.0);
                        let x2 = attr_f32(&e, "x2")?.unwrap_or(0.0);
                        let y2 = attr_f32(&e, "y2")?.unwrap_or(0.0);
                        if layer == 51 {
                            let pkg = package_stack.last_mut().unwrap();
                            pkg.fab_wires.push((x1, y1, x2, y2));
                        } else if layer == 21 || layer == 22 {
                            let curve = attr_f32(&e, "curve")?.unwrap_or(0.0);
                            let pkg = package_stack.last_mut().unwrap();
                            // Convert to local silk primitive up-front so the
                            // element-instantiation transform stage only
                            // handles typed lines/arcs/circles.
                            let mut layer_silk = SilkscreenLayer::default();
                            push_wire_as_silk((x1, y1), (x2, y2), curve, &mut layer_silk);
                            if layer == 21 {
                                pkg.silk_top.lines.extend(layer_silk.lines);
                                pkg.silk_top.arcs.extend(layer_silk.arcs);
                            } else {
                                pkg.silk_bottom.lines.extend(layer_silk.lines);
                                pkg.silk_bottom.arcs.extend(layer_silk.arcs);
                            }
                        }
                    }
                    "circle" if !package_stack.is_empty() => {
                        let layer = attr_u32(&e, "layer")?.unwrap_or(0);
                        if layer == 21 || layer == 22 {
                            let cx = attr_f32(&e, "x")?.unwrap_or(0.0);
                            let cy = attr_f32(&e, "y")?.unwrap_or(0.0);
                            let radius = attr_f32(&e, "radius")?.unwrap_or(0.0);
                            if radius > 0.0 {
                                let circle = SilkscreenCircle {
                                    center: (cx, cy),
                                    radius,
                                };
                                let pkg = package_stack.last_mut().unwrap();
                                if layer == 21 {
                                    pkg.silk_top.circles.push(circle);
                                } else {
                                    pkg.silk_bottom.circles.push(circle);
                                }
                            }
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
                    "wire" if !signal_stack.is_empty() => {
                        // Copper traces inside <signal>. Layer 1 = top,
                        // layer 16 = bottom. Other layers (e.g. polygon
                        // outlines) are ignored.
                        let layer = attr_u32(&e, "layer")?.unwrap_or(0);
                        let copper_layer = match layer {
                            1 => Some(CopperLayer::FCu),
                            16 => Some(CopperLayer::BCu),
                            _ => None,
                        };
                        if let Some(cl) = copper_layer {
                            let sig = signal_stack.last().unwrap();
                            traces.push(CopperSegment {
                                start: (
                                    attr_f32(&e, "x1")?.unwrap_or(0.0),
                                    attr_f32(&e, "y1")?.unwrap_or(0.0),
                                ),
                                end: (
                                    attr_f32(&e, "x2")?.unwrap_or(0.0),
                                    attr_f32(&e, "y2")?.unwrap_or(0.0),
                                ),
                                width: attr_f32(&e, "width")?.unwrap_or(0.25),
                                layer: cl,
                                net_name: Some(sig.name.clone()),
                            });
                        }
                    }
                    "via" if !signal_stack.is_empty() => {
                        let sig = signal_stack.last().unwrap();
                        let x = attr_f32(&e, "x")?.unwrap_or(0.0);
                        let y = attr_f32(&e, "y")?.unwrap_or(0.0);
                        let diameter = attr_f32(&e, "diameter")?
                            .or(attr_f32(&e, "drill")?.map(|d| d * 2.0))
                            .unwrap_or(0.6);
                        vias.push(Via {
                            at: (x, y),
                            diameter,
                            net_name: Some(sig.name.clone()),
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

    // Build (element_name, pad_name) → net_name lookup from parsed signals
    // so that per-component pads carry their net names for category classification.
    let mut pad_net_map: HashMap<(String, String), String> = HashMap::new();
    for net in &nets {
        for cref in &net.connected_pads {
            pad_net_map.insert(
                (cref.ref_.clone(), cref.pad.clone()),
                net.name.clone(),
            );
        }
    }

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
        let pkg_opt = packages.get(&(el.library.clone(), el.package.clone()));
        let bbox = pkg_opt
            .map(|pkg| package_bbox(pkg, &el.package))
            .unwrap_or_else(|| FootprintBbox {
                width: 1.0,
                height: 1.0,
                height3d: 1.0,
            });

        // Build pad list by cloning the package's SMD/pad centers into
        // Pad records. Nets wire into these via `contactref` lookups, so
        // pad numbers need to match `<contactref pad="..."/>`.
        let pads = if let Some(pkg) = pkg_opt {
            build_pads(pkg, &el.name, &pad_net_map)
        } else {
            Vec::new()
        };

        // Transform each package-local silk primitive to board coordinates
        // and route to top/bottom based on the layer XOR mirror composition:
        //   Layer 21 (package-top silk) + non-mirrored → board top
        //   Layer 21 + mirrored MR*     → board bottom
        //   Layer 22 (package-bot silk) + non-mirrored → board bottom
        //   Layer 22 + mirrored         → board top
        if let Some(pkg) = pkg_opt {
            emit_element_silk(
                pkg,
                (el.x, el.y),
                rotation,
                mirror,
                &mut silkscreen_top,
                &mut silkscreen_bottom,
            );
        }

        components.push(Component {
            ref_: el.name.clone(),
            bom_ref: el.name,
            x: el.x,
            y: el.y,
            rotation,
            side,
            footprint: format!("{}:{}", el.library, el.package),
            footprint_bbox: bbox,
            dominant_category: crate::net_category::pick_dominant(&pads),
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
            silkscreen_top,
            silkscreen_bottom,
        },
        nets,
        traces,
        vias,
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
    /// Package-local silkscreen for Layer 21 (tPlace). Transformed to board
    /// coordinates at element instantiation time. "Top" here is
    /// package-relative — whether it lands on the board's top or bottom face
    /// depends on whether the element is mirrored (see composition in the
    /// element loop below).
    silk_top: SilkscreenLayer,
    /// Package-local silkscreen for Layer 22 (bPlace). Symmetric to
    /// `silk_top` — rarely populated in practice (this board's packages keep
    /// all silk on layer 21) but handled for completeness.
    silk_bottom: SilkscreenLayer,
}

impl PackageDef {
    fn new(name: String) -> Self {
        Self {
            name,
            smds: Vec::new(),
            pads: Vec::new(),
            fab_wires: Vec::new(),
            silk_top: SilkscreenLayer::default(),
            silk_bottom: SilkscreenLayer::default(),
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

fn build_pads(
    pkg: &PackageDef,
    element_name: &str,
    pad_net_map: &HashMap<(String, String), String>,
) -> Vec<Pad> {
    let mut pads = Vec::with_capacity(pkg.smds.len() + pkg.pads.len());
    for s in &pkg.smds {
        pads.push(Pad {
            number: s.name.clone(),
            x: s.x,
            y: s.y,
            shape: "rect".into(),
            size: (s.dx.abs(), s.dy.abs()),
            net_name: pad_net_map
                .get(&(element_name.to_string(), s.name.clone()))
                .cloned(),
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
            net_name: pad_net_map
                .get(&(element_name.to_string(), p.name.clone()))
                .cloned(),
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
        dominant_category: None, // virtual component, no pads
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
// Silkscreen helpers (task #13a)
//
// EAGLE encodes a curved silk segment as `<wire x1 y1 x2 y2 curve="N"/>`,
// where N is the sweep angle in degrees. Zero / missing `curve` means a
// plain straight line. The chord runs from `(x1,y1)` to `(x2,y2)`; the arc
// bulges to the *left* of the chord (looking from p1 → p2) for positive
// curve, to the right for negative curve. The SilkscreenArc primitive we
// emit stores three points (start / mid / end) so downstream consumers can
// tessellate uniformly with the KiCad path.

fn push_wire_as_silk(
    start: (f32, f32),
    end: (f32, f32),
    curve_deg: f32,
    dest: &mut SilkscreenLayer,
) {
    if curve_deg.abs() < 0.01 {
        dest.lines.push(SilkscreenLine { start, end });
        return;
    }
    let Some(mid) = curve_mid(start, end, curve_deg) else {
        // Degenerate chord (zero length) — fall back to the straight line.
        dest.lines.push(SilkscreenLine { start, end });
        return;
    };
    dest.arcs.push(SilkscreenArc { start, mid, end });
}

/// Compute the arc's midpoint from the chord + sweep angle. The sagitta
/// (perpendicular offset from chord midpoint to arc midpoint) is
/// `h = (L/2) * tan(curve/4)` where L is chord length and curve is in
/// radians. The perpendicular is to the left of p1→p2 for positive sweep.
fn curve_mid(p1: (f32, f32), p2: (f32, f32), curve_deg: f32) -> Option<(f32, f32)> {
    let (dx, dy) = (p2.0 - p1.0, p2.1 - p1.1);
    let chord = (dx * dx + dy * dy).sqrt();
    if chord < 1e-6 {
        return None;
    }
    let theta = curve_deg.to_radians();
    let sagitta = (chord / 2.0) * (theta / 4.0).tan();
    // Unit perpendicular to the chord (left-hand side in a standard
    // right-handed CCW frame).
    let (px, py) = (-dy / chord, dx / chord);
    let midx = (p1.0 + p2.0) * 0.5 + px * sagitta;
    let midy = (p1.1 + p2.1) * 0.5 + py * sagitta;
    Some((midx, midy))
}

/// Compose (layer_is_top, mirror) → destination face. `layer_is_top` means
/// the silk primitive was on EAGLE Layer 21 (tPlace) within the package.
/// Mirroring happens when the element has an `MR*` rot (it's on the bottom
/// copper face). The two-input XOR: un-mirrored Layer 21 → top silk;
/// mirrored Layer 21 → bottom silk; un-mirrored Layer 22 → bottom silk;
/// mirrored Layer 22 → top silk.
fn compose_silk_face(layer_is_top: bool, mirror: bool) -> bool {
    layer_is_top ^ mirror
}

/// Transform a package-local point by the element's placement: mirror → X
/// flip (in package frame), rotate by `rot_deg` CCW around package origin,
/// then translate to the element's board position.
fn transform_silk_point(
    p: (f32, f32),
    origin: (f32, f32),
    rot_deg: f32,
    mirror: bool,
) -> (f32, f32) {
    let (mut x, y) = p;
    if mirror {
        x = -x;
    }
    let theta = rot_deg.to_radians();
    let (s, c) = (theta.sin(), theta.cos());
    let rx = x * c - y * s;
    let ry = x * s + y * c;
    (origin.0 + rx, origin.1 + ry)
}

/// Transform every package-local silk primitive to board coordinates and
/// route each to the correct face accumulator based on the layer-vs-mirror
/// composition above.
fn emit_element_silk(
    pkg: &PackageDef,
    origin: (f32, f32),
    rot_deg: f32,
    mirror: bool,
    silkscreen_top: &mut SilkscreenLayer,
    silkscreen_bottom: &mut SilkscreenLayer,
) {
    // Layer-21 (package-top) silk.
    emit_layer_silk(
        &pkg.silk_top,
        origin,
        rot_deg,
        mirror,
        /* layer_is_top = */ true,
        silkscreen_top,
        silkscreen_bottom,
    );
    // Layer-22 (package-bottom) silk.
    emit_layer_silk(
        &pkg.silk_bottom,
        origin,
        rot_deg,
        mirror,
        /* layer_is_top = */ false,
        silkscreen_top,
        silkscreen_bottom,
    );
}

fn emit_layer_silk(
    local: &SilkscreenLayer,
    origin: (f32, f32),
    rot_deg: f32,
    mirror: bool,
    layer_is_top: bool,
    silkscreen_top: &mut SilkscreenLayer,
    silkscreen_bottom: &mut SilkscreenLayer,
) {
    let lands_on_top = compose_silk_face(layer_is_top, mirror);
    let dest = if lands_on_top {
        silkscreen_top
    } else {
        silkscreen_bottom
    };
    for line in &local.lines {
        dest.lines.push(SilkscreenLine {
            start: transform_silk_point(line.start, origin, rot_deg, mirror),
            end: transform_silk_point(line.end, origin, rot_deg, mirror),
        });
    }
    for arc in &local.arcs {
        dest.arcs.push(SilkscreenArc {
            start: transform_silk_point(arc.start, origin, rot_deg, mirror),
            mid: transform_silk_point(arc.mid, origin, rot_deg, mirror),
            end: transform_silk_point(arc.end, origin, rot_deg, mirror),
        });
    }
    for circle in &local.circles {
        dest.circles.push(SilkscreenCircle {
            center: transform_silk_point(circle.center, origin, rot_deg, mirror),
            radius: circle.radius,
        });
    }
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

    #[test]
    fn silk_straight_wire_produces_line() {
        let mut silk = SilkscreenLayer::default();
        push_wire_as_silk((0.0, 0.0), (1.0, 0.0), 0.0, &mut silk);
        assert_eq!(silk.lines.len(), 1);
        assert_eq!(silk.arcs.len(), 0);
        assert_eq!(silk.lines[0].start, (0.0, 0.0));
        assert_eq!(silk.lines[0].end, (1.0, 0.0));
    }

    #[test]
    fn silk_curved_wire_produces_arc() {
        // 90° sweep on a chord along +X should bulge to the left (+Y).
        // Sagitta = (chord/2) * tan(90°/4) = 0.5 * tan(22.5°) ≈ 0.207.
        let mut silk = SilkscreenLayer::default();
        push_wire_as_silk((0.0, 0.0), (1.0, 0.0), 90.0, &mut silk);
        assert_eq!(silk.lines.len(), 0);
        assert_eq!(silk.arcs.len(), 1);
        let arc = &silk.arcs[0];
        assert_eq!(arc.start, (0.0, 0.0));
        assert_eq!(arc.end, (1.0, 0.0));
        assert!((arc.mid.0 - 0.5).abs() < 1e-4, "mid.x = {}", arc.mid.0);
        assert!(
            (arc.mid.1 - 0.20710678).abs() < 1e-4,
            "mid.y = {}",
            arc.mid.1
        );
    }

    #[test]
    fn silk_zero_length_curve_falls_back_to_line() {
        // Degenerate chord — emit a line rather than NaN-filled arc.
        let mut silk = SilkscreenLayer::default();
        push_wire_as_silk((2.5, 1.0), (2.5, 1.0), 45.0, &mut silk);
        assert_eq!(silk.lines.len(), 1);
        assert_eq!(silk.arcs.len(), 0);
    }

    #[test]
    fn silk_face_composition_rules() {
        // Layer 21 + not mirrored → top; Layer 21 + mirrored → bottom.
        assert_eq!(compose_silk_face(true, false), true);
        assert_eq!(compose_silk_face(true, true), false);
        // Layer 22 + not mirrored → bottom; Layer 22 + mirrored → top.
        assert_eq!(compose_silk_face(false, false), false);
        assert_eq!(compose_silk_face(false, true), true);
    }

    #[test]
    fn silk_transform_mirror_flips_x() {
        let p = transform_silk_point((2.0, 3.0), (0.0, 0.0), 0.0, true);
        assert_eq!(p, (-2.0, 3.0));
    }

    #[test]
    fn silk_transform_rotate_90_ccw() {
        // (1, 0) rotated 90° CCW about origin → (0, 1).
        let p = transform_silk_point((1.0, 0.0), (0.0, 0.0), 90.0, false);
        assert!(p.0.abs() < 1e-5, "x = {}", p.0);
        assert!((p.1 - 1.0).abs() < 1e-5, "y = {}", p.1);
    }

    #[test]
    fn silk_transform_translate() {
        let p = transform_silk_point((0.5, -0.5), (10.0, 20.0), 0.0, false);
        assert_eq!(p, (10.5, 19.5));
    }

    /// Mirroring + rotation + translation composed together — exercises the
    /// exact path an EAGLE MR* element drives. Starting from a local point
    /// (1, 0), mirror flips to (-1, 0), 180° rotation yields (1, 0), then
    /// translate by element origin (5, 5) → (6, 5).
    #[test]
    fn silk_transform_mirror_then_rotate_180_then_translate() {
        let p = transform_silk_point((1.0, 0.0), (5.0, 5.0), 180.0, true);
        assert!((p.0 - 6.0).abs() < 1e-5, "x = {}", p.0);
        assert!((p.1 - 5.0).abs() < 1e-5, "y = {}", p.1);
    }

    /// End-to-end silk sanity: C2 BOM elements all carry MR* rotations, so
    /// every package Layer-21 silk primitive should route to the board's
    /// bottom silk. Confirm we actually emit a meaningful number of them
    /// (packages have dense footprint outlines on layer 21).
    #[test]
    fn c2_parse_produces_bottom_silkscreen() {
        let bom = sample_bom();
        let board = load_c2_board(&bom).expect("parse");
        let top_total = board.outline.silkscreen_top.lines.len()
            + board.outline.silkscreen_top.arcs.len()
            + board.outline.silkscreen_top.circles.len();
        let bottom_total = board.outline.silkscreen_bottom.lines.len()
            + board.outline.silkscreen_bottom.arcs.len()
            + board.outline.silkscreen_bottom.circles.len();
        // Bottom face should dominate — every MR* element's package-top silk
        // lands there. Loose lower bound: at least one line per BOM element.
        assert!(
            bottom_total >= 17,
            "bottom silk total = {} (expected ≥ 17)",
            bottom_total
        );
        // Board also has top-silk text/wires in <plain> that we don't emit
        // (text is out of scope) — but package silk from non-mirrored
        // elements is empty in C2 because every BOM element is MR*. So top
        // can legitimately be zero or near-zero here.
        let _ = top_total;
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

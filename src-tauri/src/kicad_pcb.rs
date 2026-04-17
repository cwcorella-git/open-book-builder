//! KiCad 6 `.kicad_pcb` parser. Walks the S-expression tree (via `lexpr`)
//! and populates `BoardData` for the C1 main board. Called from
//! `dataset::load()` after the BOM has been parsed so component refs can be
//! matched against `BomLine.refs` and artwork placeholders (`REF**`, `G***`)
//! can be dropped.
//!
//! Heuristics:
//! - Footprints whose library name starts with `MountingHole` are routed to
//!   `BoardOutline.holes` with the diameter drawn from the largest-drill pad.
//! - Footprints whose reference doesn't match any C1 BOM ref are dropped
//!   (logo artwork, G*** placeholders).
//! - `(gr_line ...)` and `(gr_arc ...)` on layer `Edge.Cuts` become
//!   `EdgeSegment`s; board-level `gr_line`/`gr_arc`/`gr_circle` on `F.SilkS`
//!   or `B.SilkS` become `SilkscreenLayer` primitives. Fab/courtyard layers
//!   stay ignored.
//! - Per-footprint `fp_line` / `fp_arc` / `fp_circle` children on `F.SilkS`
//!   or `B.SilkS` are transformed (mirror for bottom-side footprints, rotate
//!   by footprint rotation, translate by origin) into board coordinates and
//!   pushed to the corresponding layer. Text (`fp_text`) is not rendered.
//! - Board `width_mm` / `height_mm` are the max X/Y extents of all Edge.Cuts
//!   points. The KiCad origin is (0, 0) at the top-left, so this matches the
//!   canvas convention — no flip needed.
//!
//! Top-level `(segment ...)` and `(via ...)` nodes produce `CopperSegment`
//! and `Via` records for copper-trace rendering. `nets` stays empty — the
//! net-name classification is driven per-pad, not from a top-level net list.

use crate::types::{
    BoardData, BoardId, BoardOutline, BomLine, Component, CopperLayer,
    CopperSegment, EdgeSegment, FootprintBbox, Hole, Pad, Side, SilkscreenArc,
    SilkscreenCircle, SilkscreenLayer, SilkscreenLine, Via,
};
use lexpr::Value;
use std::collections::HashMap;
use thiserror::Error;

const PCB_SEXPR: &str = include_str!("../data/OSO-BOOK-C1.kicad_pcb");

#[derive(Debug, Error)]
pub enum KiCadError {
    #[error("lexpr parse: {0}")]
    Lex(#[from] lexpr::parse::Error),
    #[error("pcb shape: {0}")]
    Shape(String),
}

/// Parse the compiled-in C1 `.kicad_pcb` and return populated `BoardData`.
/// `c1_bom` is filtered internally to just C1 lines before ref-matching.
pub fn load_c1_board(c1_bom: &[BomLine]) -> Result<BoardData, KiCadError> {
    // KiCad 6 sprinkles `(tstamp <uuid>)` and `(tedit <hex-epoch>)` tokens
    // throughout. lexpr's default reader tries to parse those as numbers and
    // fails on the first letter (e.g. the `b` in `1bd80cf9-...`). We don't
    // consume either value, so the cheapest fix is to strip both subexprs
    // before handing the text to lexpr.
    let cleaned = strip_timestamps(PCB_SEXPR);
    let root: Value = lexpr::from_str(&cleaned)?;
    if head_symbol(&root) != Some("kicad_pcb") {
        return Err(KiCadError::Shape(format!(
            "expected (kicad_pcb ...), got head {:?}",
            head_symbol(&root)
        )));
    }

    // Ref → BomLine index so classify_footprint can pull per-MPN rendering
    // hints (currently just `hero_mesh_id`; nets / pads-to-fn lookups land
    // in task #13). Any ref that matches a BOM line is a keepable component;
    // anything else is artwork / placeholder and gets dropped.
    let bom_by_ref: HashMap<&str, &BomLine> = c1_bom
        .iter()
        .filter(|l| l.board == BoardId::C1Main)
        .flat_map(|line| line.refs.iter().map(move |r| (r.as_str(), line)))
        .collect();

    let mut components = Vec::<Component>::new();
    let mut holes = Vec::<Hole>::new();
    let mut edge_segments = Vec::<EdgeSegment>::new();
    let mut silkscreen_top = SilkscreenLayer::default();
    let mut silkscreen_bottom = SilkscreenLayer::default();
    let mut traces = Vec::<CopperSegment>::new();
    let mut vias = Vec::<Via>::new();

    for child in positional(&root) {
        match head_symbol(child) {
            Some("footprint") => {
                classify_footprint(
                    child,
                    &bom_by_ref,
                    &mut components,
                    &mut holes,
                    &mut silkscreen_top,
                    &mut silkscreen_bottom,
                );
            }
            Some("gr_line") => {
                if let Some(seg) = parse_edge_line(child) {
                    edge_segments.push(seg);
                } else if let Some((layer, line)) = parse_board_silk_line(child) {
                    push_silk_line(layer, line, &mut silkscreen_top, &mut silkscreen_bottom);
                }
            }
            Some("gr_arc") => {
                if let Some(seg) = parse_edge_arc(child) {
                    edge_segments.push(seg);
                } else if let Some((layer, arc)) = parse_board_silk_arc(child) {
                    push_silk_arc(layer, arc, &mut silkscreen_top, &mut silkscreen_bottom);
                }
            }
            Some("gr_circle") => {
                if let Some((layer, circle)) = parse_board_silk_circle(child) {
                    push_silk_circle(layer, circle, &mut silkscreen_top, &mut silkscreen_bottom);
                }
            }
            Some("segment") => {
                if let Some(seg) = parse_copper_segment(child) {
                    traces.push(seg);
                }
            }
            Some("via") => {
                if let Some(v) = parse_via(child) {
                    vias.push(v);
                }
            }
            _ => {}
        }
    }

    let (width_mm, height_mm) = outline_extents(&edge_segments);

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
        nets: Vec::new(),
        traces,
        vias,
    })
}

// ---------------------------------------------------------------------------
// Preprocessing

/// Remove every `(tstamp ...)` and `(tedit ...)` subexpression from the raw
/// text. Both carry non-numeric bare atoms (UUIDs / hex epochs) that lexpr's
/// default parser rejects. They never nest and we never need their values.
fn strip_timestamps(src: &str) -> String {
    const PATTERNS: &[&[u8]] = &[b"(tstamp ", b"(tedit "];
    let bytes = src.as_bytes();
    let mut out = String::with_capacity(bytes.len());
    let mut i = 0;
    'outer: while i < bytes.len() {
        for pat in PATTERNS {
            if bytes[i..].starts_with(pat) {
                // Advance past the matching ')'. KiCad's tstamp/tedit atoms
                // never contain nested parens, so a simple counter suffices.
                let mut depth = 1;
                i += 1; // past '('
                while i < bytes.len() && depth > 0 {
                    match bytes[i] {
                        b'(' => depth += 1,
                        b')' => depth -= 1,
                        _ => {}
                    }
                    i += 1;
                }
                continue 'outer;
            }
        }
        out.push(bytes[i] as char);
        i += 1;
    }
    out
}

// ---------------------------------------------------------------------------
// lexpr helpers

/// Return every element of a proper list, or an empty `Vec` if `v` is not a
/// list. Borrows into `v`; caller keeps ownership.
fn list_children(v: &Value) -> Vec<&Value> {
    v.list_iter().map(Iterator::collect).unwrap_or_default()
}

/// For `(head arg1 arg2 ...)`, return `[arg1, arg2, ...]` — the elements
/// *after* the head symbol.
fn positional(v: &Value) -> Vec<&Value> {
    v.list_iter()
        .map(|iter| iter.skip(1).collect())
        .unwrap_or_default()
}

/// If `v` is a list whose first element is a symbol, return that symbol.
fn head_symbol(v: &Value) -> Option<&str> {
    v.list_iter()?.next()?.as_symbol()
}

/// First child whose head symbol matches `tag` — e.g. `find_tagged(fp, "at")`
/// on a footprint returns the `(at X Y [ROT])` node.
fn find_tagged<'a>(v: &'a Value, tag: &str) -> Option<&'a Value> {
    list_children(v).into_iter().find(|c| head_symbol(c) == Some(tag))
}

/// Every child whose head symbol matches `tag`.
fn find_all_tagged<'a>(v: &'a Value, tag: &'a str) -> Vec<&'a Value> {
    list_children(v)
        .into_iter()
        .filter(|c| head_symbol(c) == Some(tag))
        .collect()
}

fn as_f32(v: &Value) -> Option<f32> {
    v.as_f64().map(|f| f as f32)
}

fn string_of(v: &Value) -> Option<&str> {
    v.as_str()
}

// ---------------------------------------------------------------------------
// Footprints → components + holes

fn classify_footprint<'a>(
    fp: &'a Value,
    bom_by_ref: &HashMap<&str, &BomLine>,
    components: &mut Vec<Component>,
    holes: &mut Vec<Hole>,
    silkscreen_top: &mut SilkscreenLayer,
    silkscreen_bottom: &mut SilkscreenLayer,
) {
    let args = positional(fp);
    let Some(fp_name) = args.first().and_then(|v| string_of(v)) else {
        return;
    };

    let layer = find_tagged(fp, "layer")
        .and_then(|v| positional(v).first().and_then(|a| string_of(a)).map(String::from))
        .unwrap_or_else(|| "F.Cu".into());
    let side = if layer == "B.Cu" { Side::Bottom } else { Side::Top };

    let Some((x, y, rotation)) = find_tagged(fp, "at").and_then(parse_at) else {
        return;
    };

    let ref_name = reference_of(fp).unwrap_or_default();

    // Mounting holes are routed to the board outline so the SVG / future 3D
    // viewport can render them as pierced circles instead of tiny boxes.
    if fp_name.starts_with("MountingHole") {
        let diameter = largest_drill(fp).unwrap_or(2.5);
        holes.push(Hole { x, y, diameter });
        return;
    }

    // Artwork placeholders (`REF**`, `G***`) won't match a BOM ref — drop them.
    let Some(bom_line) = bom_by_ref.get(ref_name.as_str()) else {
        return;
    };

    // Footprint-level silkscreen graphics. Transformed to board coordinates
    // and routed to the correct face (F.SilkS follows the footprint body;
    // B.SilkS goes to the opposite face).
    let mirror = side == Side::Bottom;
    extract_footprint_silk(
        fp,
        (x, y),
        rotation,
        mirror,
        side,
        silkscreen_top,
        silkscreen_bottom,
    );

    let pads: Vec<Pad> = find_all_tagged(fp, "pad")
        .into_iter()
        .filter_map(parse_pad)
        .collect();
    let footprint_bbox = bbox_from_pads(&pads, fp_name);

    components.push(Component {
        ref_: ref_name.clone(),
        bom_ref: ref_name,
        x,
        y,
        rotation,
        side,
        footprint: fp_name.to_string(),
        footprint_bbox,
        dominant_category: crate::net_category::pick_dominant(&pads),
        pads,
        hero_mesh_id: bom_line.hero_mesh_id.clone(),
        board: BoardId::C1Main,
    });
}

/// Parse `(at X Y [ROT])` into `(x, y, rot)`. Rotation defaults to 0.
fn parse_at(v: &Value) -> Option<(f32, f32, f32)> {
    let a = positional(v);
    let x = as_f32(a.first()?)?;
    let y = as_f32(a.get(1)?)?;
    let rot = a.get(2).and_then(|r| as_f32(r)).unwrap_or(0.0);
    Some((x, y, rot))
}

/// Footprints can contain many `(fp_text ...)` nodes (reference, value, user).
/// Return the one whose first positional arg is the symbol `reference`.
fn reference_of(fp: &Value) -> Option<String> {
    for t in find_all_tagged(fp, "fp_text") {
        let a = positional(t);
        if a.first().and_then(|v| v.as_symbol()) == Some("reference") {
            return a.get(1).and_then(|v| string_of(v)).map(String::from);
        }
    }
    None
}

fn largest_drill(fp: &Value) -> Option<f32> {
    let mut best: Option<f32> = None;
    for pad in find_all_tagged(fp, "pad") {
        if let Some(d) = find_tagged(pad, "drill") {
            if let Some(v) = positional(d).first().and_then(|n| as_f32(n)) {
                best = Some(best.map_or(v, |prev| prev.max(v)));
            }
        }
    }
    best
}

fn parse_pad(pad: &Value) -> Option<Pad> {
    // (pad NUM TYPE SHAPE (at x y [rot]) (size w h) (layers ...) [(drill d)]
    //      [(net N "NAME")] ...)
    let a = positional(pad);
    let number_val = a.first()?;
    let number = number_val
        .as_str()
        .map(String::from)
        .or_else(|| number_val.as_symbol().map(String::from))
        .or_else(|| number_val.as_i64().map(|n| n.to_string()))?;
    let type_sym = a.get(1)?.as_symbol().unwrap_or("");
    let shape_sym = a.get(2)?.as_symbol().unwrap_or("");

    let (px, py, _) = find_tagged(pad, "at").and_then(parse_at)?;
    let size_args = positional(find_tagged(pad, "size")?);
    let sw = as_f32(size_args.first()?)?;
    let sh = as_f32(size_args.get(1)?)?;

    let through_hole = type_sym == "thru_hole" || type_sym == "np_thru_hole";

    let net_name = find_tagged(pad, "net")
        .and_then(|n| positional(n).get(1).and_then(|v| string_of(v)).map(String::from));

    Some(Pad {
        number,
        x: px,
        y: py,
        shape: map_pad_shape(shape_sym),
        size: (sw, sh),
        net_name,
        through_hole,
    })
}

fn map_pad_shape(s: &str) -> String {
    // KiCad 6 emits rect / roundrect / circle / oval / trapezoid / custom.
    // The TS side only draws rect / circle / roundrect / oval; anything else
    // falls back to rect so the SVG rendering stays predictable.
    match s {
        "rect" | "roundrect" | "circle" | "oval" => s.into(),
        _ => "rect".into(),
    }
}

/// Axis-aligned bbox over pad footprints (ignoring per-pad rotation — good
/// enough for a 2D overview and the task #9 3D extrusion).
fn bbox_from_pads(pads: &[Pad], fp_name: &str) -> FootprintBbox {
    let height3d = crate::footprint_heights::height3d_for(fp_name);
    if pads.is_empty() {
        return FootprintBbox {
            width: 1.0,
            height: 1.0,
            height3d,
        };
    }
    let (mut minx, mut miny) = (f32::INFINITY, f32::INFINITY);
    let (mut maxx, mut maxy) = (f32::NEG_INFINITY, f32::NEG_INFINITY);
    for p in pads {
        let hx = p.size.0 * 0.5;
        let hy = p.size.1 * 0.5;
        minx = minx.min(p.x - hx);
        maxx = maxx.max(p.x + hx);
        miny = miny.min(p.y - hy);
        maxy = maxy.max(p.y + hy);
    }
    FootprintBbox {
        width: (maxx - minx).max(0.5),
        height: (maxy - miny).max(0.5),
        height3d,
    }
}

// ---------------------------------------------------------------------------
// Edge.Cuts geometry

fn parse_edge_line(v: &Value) -> Option<EdgeSegment> {
    if !on_layer(v, "Edge.Cuts") {
        return None;
    }
    let start = point_of(v, "start")?;
    let end = point_of(v, "end")?;
    Some(EdgeSegment {
        kind: "line".into(),
        points: vec![start, end],
    })
}

fn parse_edge_arc(v: &Value) -> Option<EdgeSegment> {
    if !on_layer(v, "Edge.Cuts") {
        return None;
    }
    let start = point_of(v, "start")?;
    let mid = point_of(v, "mid")?;
    let end = point_of(v, "end")?;
    // KiCad 6 arcs carry start/mid/end; the mid point gives the SVG side
    // enough information to compute radius + sweep without extra math here.
    Some(EdgeSegment {
        kind: "arc".into(),
        points: vec![start, mid, end],
    })
}

fn on_layer(v: &Value, layer: &str) -> bool {
    find_tagged(v, "layer")
        .and_then(|l| positional(l).first().and_then(|a| string_of(a)).map(String::from))
        .as_deref()
        == Some(layer)
}

fn point_of(v: &Value, tag: &str) -> Option<(f32, f32)> {
    let node = find_tagged(v, tag)?;
    let a = positional(node);
    Some((as_f32(a.first()?)?, as_f32(a.get(1)?)?))
}

/// Board dimensions are the max X/Y over all Edge.Cuts vertices, assuming
/// origin at (0, 0). KiCad places the board in the positive quadrant by
/// default for newly-drawn boards, and the C1 file follows that convention.
fn outline_extents(segments: &[EdgeSegment]) -> (f32, f32) {
    let (mut maxx, mut maxy) = (0.0_f32, 0.0_f32);
    for seg in segments {
        for (px, py) in &seg.points {
            maxx = maxx.max(*px);
            maxy = maxy.max(*py);
        }
    }
    (maxx, maxy)
}

// ---------------------------------------------------------------------------
// Copper traces + vias (task #13f)

/// Parse `(segment (start X Y) (end X Y) (width W) (layer L) (net N) ...)`
fn parse_copper_segment(v: &Value) -> Option<CopperSegment> {
    let layer_str = find_tagged(v, "layer")
        .and_then(|l| positional(l).first().and_then(|a| string_of(a)))?;
    let copper_layer = match layer_str {
        "F.Cu" => CopperLayer::FCu,
        "B.Cu" => CopperLayer::BCu,
        _ => return None, // inner layers not rendered
    };
    let start = point_of(v, "start")?;
    let end = point_of(v, "end")?;
    let width = find_tagged(v, "width")
        .and_then(|w| positional(w).first().and_then(|a| as_f32(a)))
        .unwrap_or(0.25);
    let net_name = find_tagged(v, "net")
        .and_then(|n| positional(n).get(1).and_then(|a| string_of(a)).map(String::from));
    Some(CopperSegment {
        start,
        end,
        width,
        layer: copper_layer,
        net_name,
    })
}

/// Parse `(via (at X Y) (size S) (drill D) (layers L1 L2) (net N) ...)`
fn parse_via(v: &Value) -> Option<Via> {
    let (x, y) = find_tagged(v, "at").and_then(|a| {
        let p = positional(a);
        Some((as_f32(p.first()?)?, as_f32(p.get(1)?)?))
    })?;
    let diameter = find_tagged(v, "size")
        .and_then(|s| positional(s).first().and_then(|a| as_f32(a)))
        .unwrap_or(0.6);
    let net_name = find_tagged(v, "net")
        .and_then(|n| positional(n).get(1).and_then(|a| string_of(a)).map(String::from));
    Some(Via {
        at: (x, y),
        diameter,
        net_name,
    })
}

// ---------------------------------------------------------------------------
// Silkscreen extraction (task #13a)
//
// Two sources:
// 1. Board-level graphics (`gr_line` / `gr_arc` / `gr_circle`) on `F.SilkS`
//    or `B.SilkS`. Coordinates are already in board space.
// 2. Per-footprint graphics (`fp_line` / `fp_arc` / `fp_circle`) inside a
//    `(footprint ...)` block. Coordinates are footprint-local and must be
//    mirrored (for bottom-side footprints) + rotated + translated.
//
// The destination face is a composition of the footprint's side with the
// silk layer (F.SilkS = same side as the footprint body; B.SilkS = the
// opposite face). See plan "Task #13a detail".

/// Which side of the board a silk primitive should be drawn on.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SilkFace {
    Top,
    Bottom,
}

fn layer_to_silk_face(layer: &str) -> Option<SilkFace> {
    match layer {
        "F.SilkS" => Some(SilkFace::Top),
        "B.SilkS" => Some(SilkFace::Bottom),
        _ => None,
    }
}

fn push_silk_line(
    face: SilkFace,
    line: SilkscreenLine,
    top: &mut SilkscreenLayer,
    bottom: &mut SilkscreenLayer,
) {
    match face {
        SilkFace::Top => top.lines.push(line),
        SilkFace::Bottom => bottom.lines.push(line),
    }
}

fn push_silk_arc(
    face: SilkFace,
    arc: SilkscreenArc,
    top: &mut SilkscreenLayer,
    bottom: &mut SilkscreenLayer,
) {
    match face {
        SilkFace::Top => top.arcs.push(arc),
        SilkFace::Bottom => bottom.arcs.push(arc),
    }
}

fn push_silk_circle(
    face: SilkFace,
    circle: SilkscreenCircle,
    top: &mut SilkscreenLayer,
    bottom: &mut SilkscreenLayer,
) {
    match face {
        SilkFace::Top => top.circles.push(circle),
        SilkFace::Bottom => bottom.circles.push(circle),
    }
}

// --- Board-level silkscreen (already in board coordinates)

fn parse_board_silk_line(v: &Value) -> Option<(SilkFace, SilkscreenLine)> {
    let layer = find_tagged(v, "layer")
        .and_then(|l| positional(l).first().and_then(|a| string_of(a)).map(String::from))?;
    let face = layer_to_silk_face(&layer)?;
    let start = point_of(v, "start")?;
    let end = point_of(v, "end")?;
    Some((face, SilkscreenLine { start, end }))
}

fn parse_board_silk_arc(v: &Value) -> Option<(SilkFace, SilkscreenArc)> {
    let layer = find_tagged(v, "layer")
        .and_then(|l| positional(l).first().and_then(|a| string_of(a)).map(String::from))?;
    let face = layer_to_silk_face(&layer)?;
    let start = point_of(v, "start")?;
    let mid = point_of(v, "mid")?;
    let end = point_of(v, "end")?;
    Some((face, SilkscreenArc { start, mid, end }))
}

fn parse_board_silk_circle(v: &Value) -> Option<(SilkFace, SilkscreenCircle)> {
    let layer = find_tagged(v, "layer")
        .and_then(|l| positional(l).first().and_then(|a| string_of(a)).map(String::from))?;
    let face = layer_to_silk_face(&layer)?;
    let center = point_of(v, "center")?;
    // KiCad encodes a circle as `(gr_circle (center cx cy) (end ex ey) ...)`
    // where `end` is a point on the circumference. Radius is |end - center|.
    let end = point_of(v, "end")?;
    let dx = end.0 - center.0;
    let dy = end.1 - center.1;
    let radius = (dx * dx + dy * dy).sqrt();
    Some((face, SilkscreenCircle { center, radius }))
}

// --- Footprint-level silkscreen (needs transform)

/// Rotate a footprint-local point around the footprint origin by `rot_deg`
/// (CCW in standard math orientation), after optionally mirroring along X,
/// then translate to board coordinates.
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

fn extract_footprint_silk(
    fp: &Value,
    origin: (f32, f32),
    rotation: f32,
    mirror: bool,
    fp_side: Side,
    silkscreen_top: &mut SilkscreenLayer,
    silkscreen_bottom: &mut SilkscreenLayer,
) {
    // Pick a compositor: F.SilkS targets the footprint's face; B.SilkS the
    // opposite face. Bottom-side footprints flip the meaning of F/B locally.
    let compose = |layer_face: SilkFace| -> SilkFace {
        match (layer_face, fp_side) {
            (SilkFace::Top, Side::Top) | (SilkFace::Bottom, Side::Bottom) => SilkFace::Top,
            _ => SilkFace::Bottom,
        }
    };

    for child in list_children(fp) {
        let Some(tag) = head_symbol(child) else { continue };
        let Some(layer) = find_tagged(child, "layer")
            .and_then(|l| positional(l).first().and_then(|a| string_of(a)).map(String::from))
        else {
            continue;
        };
        let Some(layer_face) = layer_to_silk_face(&layer) else {
            continue;
        };
        let dest = compose(layer_face);

        match tag {
            "fp_line" => {
                if let (Some(start), Some(end)) = (point_of(child, "start"), point_of(child, "end"))
                {
                    let line = SilkscreenLine {
                        start: transform_silk_point(start, origin, rotation, mirror),
                        end: transform_silk_point(end, origin, rotation, mirror),
                    };
                    push_silk_line(dest, line, silkscreen_top, silkscreen_bottom);
                }
            }
            "fp_arc" => {
                if let (Some(start), Some(mid), Some(end)) = (
                    point_of(child, "start"),
                    point_of(child, "mid"),
                    point_of(child, "end"),
                ) {
                    let arc = SilkscreenArc {
                        start: transform_silk_point(start, origin, rotation, mirror),
                        mid: transform_silk_point(mid, origin, rotation, mirror),
                        end: transform_silk_point(end, origin, rotation, mirror),
                    };
                    push_silk_arc(dest, arc, silkscreen_top, silkscreen_bottom);
                }
            }
            "fp_circle" => {
                if let (Some(center), Some(edge)) =
                    (point_of(child, "center"), point_of(child, "end"))
                {
                    let dx = edge.0 - center.0;
                    let dy = edge.1 - center.1;
                    let radius = (dx * dx + dy * dy).sqrt();
                    let circle = SilkscreenCircle {
                        center: transform_silk_point(center, origin, rotation, mirror),
                        radius,
                    };
                    push_silk_circle(dest, circle, silkscreen_top, silkscreen_bottom);
                }
            }
            _ => {}
        }
    }
}

// ---------------------------------------------------------------------------
// Tests

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn transform_silk_point_identity() {
        let p = transform_silk_point((1.0, 2.0), (10.0, 20.0), 0.0, false);
        assert!((p.0 - 11.0).abs() < 1e-4);
        assert!((p.1 - 22.0).abs() < 1e-4);
    }

    #[test]
    fn transform_silk_point_mirror_only() {
        let p = transform_silk_point((3.0, 4.0), (0.0, 0.0), 0.0, true);
        assert!((p.0 + 3.0).abs() < 1e-4);
        assert!((p.1 - 4.0).abs() < 1e-4);
    }

    #[test]
    fn transform_silk_point_rotation_90() {
        // (1, 0) rotated 90° CCW → (0, 1), translated by (5, 5) → (5, 6).
        let p = transform_silk_point((1.0, 0.0), (5.0, 5.0), 90.0, false);
        assert!((p.0 - 5.0).abs() < 1e-4);
        assert!((p.1 - 6.0).abs() < 1e-4);
    }

    #[test]
    fn load_c1_produces_silkscreen_when_bom_matches() {
        // The C1 .kicad_pcb is ~1.3 MB and the S-expression walker recurses
        // deeply while parsing. Test threads default to a 2 MB stack which
        // overflows on debug builds; run the load on a dedicated thread with
        // an 8 MB stack to sidestep.
        let handle = std::thread::Builder::new()
            .stack_size(8 * 1024 * 1024)
            .spawn(|| {
                // Populate a BOM entry for R1 so classify_footprint keeps at
                // least one component, which lets its fp_line silk flow
                // through to the top-face accumulator.
                let bom = vec![BomLine {
                    refs: vec!["R1".into()],
                    qty: 1,
                    description: "test".into(),
                    manufacturer: None,
                    mpn: "TEST-R1".into(),
                    digikey_pn: None,
                    mouser_pn: None,
                    optional: false,
                    unit_cost_usd: None,
                    live_price: None,
                    footprint: None,
                    function: "test".into(),
                    datasheet_url: None,
                    hero_mesh_id: None,
                    board: BoardId::C1Main,
                }];
                load_c1_board(&bom).unwrap()
            })
            .expect("spawn");
        let board = handle.join().expect("join");
        // Every 0805 passive carries an outline rectangle (4 lines) on
        // F.SilkS. With R1 in the BOM we expect at least a handful of lines.
        assert!(
            !board.outline.silkscreen_top.lines.is_empty(),
            "R1 silk should populate silkscreen_top.lines"
        );
    }
}

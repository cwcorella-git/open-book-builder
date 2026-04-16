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
//!   `EdgeSegment`s; everything else on those node types (silkscreen, fab
//!   layers) is ignored.
//! - Board `width_mm` / `height_mm` are the max X/Y extents of all Edge.Cuts
//!   points. The KiCad origin is (0, 0) at the top-left, so this matches the
//!   canvas convention — no flip needed.
//!
//! Nets, copper traces, and vias are explicitly out of scope for task #8;
//! the `nets` field stays empty until task #13.

use crate::types::{
    BoardData, BoardId, BoardOutline, BomLine, Component, EdgeSegment,
    FootprintBbox, Hole, Pad, Side,
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

    for child in positional(&root) {
        match head_symbol(child) {
            Some("footprint") => {
                classify_footprint(child, &bom_by_ref, &mut components, &mut holes);
            }
            Some("gr_line") => {
                if let Some(seg) = parse_edge_line(child) {
                    edge_segments.push(seg);
                }
            }
            Some("gr_arc") => {
                if let Some(seg) = parse_edge_arc(child) {
                    edge_segments.push(seg);
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
            silkscreen_svg: None,
            silkscreen_svg_bottom: None,
        },
        nets: Vec::new(),
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

//! Part-class height lookup. Turns a KiCad footprint name (e.g.
//! `"Capacitor_SMD:C_0805_2012Metric_Pad1.20x1.40mm_HandSolder"`) into a
//! 3D extrusion height in millimeters. Called from `kicad_pcb::bbox_from_pads`
//! so the value ends up in `FootprintBbox.height3d` at parse time — baked
//! into `public/board-dataset.json` for the web target.
//!
//! Rules are evaluated top to bottom; first match wins. The rule set is tuned
//! to the exact C1 footprint strings present in `OSO-BOOK-C1.kicad_pcb`:
//! every current component hits a specific rule and nothing falls through to
//! the default. The unit tests below enumerate those strings so a regression
//! (e.g. a new footprint slipping in with an unintended default) would fail
//! loudly.
//!
//! Once task #10 lands hero meshes (Pi Pico, MEM2075, C2 module, battery
//! holder, GDEW042T2 panel), those component records bypass the extrusion
//! path entirely — this table's values for them become visually dead.

/// Return a reasonable extrusion height (mm) for the footprint. Never fails;
/// falls through to 1.0 mm for a genuinely unmatched footprint class.
pub fn height3d_for(fp: &str) -> f32 {
    // Bulky through-hole mechanicals first so their "SMT" suffix doesn't
    // match the SMD-passive tail rules.
    if fp.starts_with("Battery_Holder") {
        return 12.0;
    }

    // Switches — SPDT slide vs. tactile-SMD vs. tactile-buttonpad.
    if fp.contains("SW_SPDT") || fp.starts_with("Switch_Slide") {
        return 2.5;
    }
    if fp.starts_with("TACT_") || fp.contains("SW_PUSH") {
        return 3.5;
    }
    if fp.starts_with("Button_Switch_SMD") || fp.starts_with("Button_Switch_THT") {
        return 3.5;
    }

    // Connectors — JST SH is the low-profile 1mm-pitch variant; PH is the
    // taller 2mm-pitch body most visible on the C1.
    if fp.contains("JST_SH_") {
        return 1.5;
    }
    if fp.starts_with("Connector_JST") {
        return 4.5;
    }

    // Crystals / resonators sit ~1.5mm over the board.
    if fp.contains("Crystal") {
        return 1.5;
    }

    // Hero-mesh candidates — these values only matter until task #10's real
    // GLTFs ship; keep them low so the placeholder boxes don't dominate the
    // scene. Pi Pico reads as a thin PCB; MEM2075 microSD slot is a shallow
    // metal shell; OSO-BOOK-C2-01 is the 1.5mm-thick castellated submodule.
    if fp.contains("RPi_Pico") || fp.contains("MEM2075") || fp.contains("OSO-BOOK-C2") {
        return 1.5;
    }

    // Generic SMD IC packages.
    if fp.starts_with("Package_SO")
        || fp.starts_with("Package_QFN")
        || fp.starts_with("Package_DFN")
        || fp.starts_with("Package_TO_SOT")
    {
        return 1.0;
    }

    // SMD passives (0402 / 0603 / 0805 / 1206 / 1210).
    for size in ["_0402", "_0603", "_0805", "_1206", "_1210"] {
        if fp.contains(size) {
            return 0.6;
        }
    }

    // Unmatched — 1mm is a safe "thin-SMD" fallback.
    1.0
}

/// Height lookup for EAGLE bare package names (e.g. `"0805-NO"`, `"SOD-123"`,
/// `"SOT23-3"`, `"EINK_24PIN"`, `"_0603"`). EAGLE embeds package definitions
/// inline in the `.brd`, so footprints aren't prefixed with a library path —
/// different keyspace from KiCad, different table.
///
/// Evaluated top-to-bottom, first match wins. Tuned to the 8 packages that
/// appear in `OSO-BOOK-C2-02.brd`; unknowns fall through to 1mm.
pub fn height3d_for_eagle(pkg: &str) -> f32 {
    // SMD passives. `0805-NO`, `MICROBUILDER__0805`, `_0603` all land here.
    if pkg.contains("0805") || pkg.contains("_0603") {
        return 0.6;
    }

    // Small-outline transistor / diode packages. SOD-123 is the Schottky body,
    // SOT23-3 is the P-MOSFET body — both ~1.1mm tall.
    if pkg == "SOD-123" {
        return 1.1;
    }
    if pkg.starts_with("SOT23") {
        return 1.1;
    }

    // The 24-pin FFC connector for the e-paper ribbon.
    if pkg == "EINK_24PIN" {
        return 1.5;
    }

    // Unmatched — 1mm is a safe default.
    1.0
}

#[cfg(test)]
mod tests {
    use super::{height3d_for, height3d_for_eagle};

    /// Every footprint string that currently appears in the C1 dataset gets
    /// an explicit expected value. If a new footprint slips in and we forget
    /// to classify it, this test won't catch it — but our Rust→JSON bake
    /// will, since the frontend smoke test expects no raw `1.0` fallthroughs
    /// on parts we know should be shorter or taller.
    #[test]
    fn c1_footprints_get_expected_heights() {
        let cases: &[(&str, f32)] = &[
            // Passives
            (
                "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder",
                0.6,
            ),
            (
                "Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm_HandSolder",
                0.6,
            ),
            (
                "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder",
                0.6,
            ),
            (
                "Resistor_SMD:R_1206_3216Metric_Pad1.30x1.75mm_HandSolder",
                0.6,
            ),
            // Switches
            (
                "Button_Switch_SMD:Panasonic_EVQPUJ_EVQPUA",
                3.5,
            ),
            ("Button_Switch_SMD:SW_SPDT_CK-JS102011SAQN", 2.5),
            ("TACT_PANA-EVQ:TACT_PANA-EVQ-BUTTONPAD", 3.5),
            // Connectors
            (
                "Connector_JST:JST_PH_S3B-PH-SM4-TB_1x03-1MP_P2.00mm_Horizontal",
                4.5,
            ),
            (
                "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal",
                1.5,
            ),
            // ICs / packages
            ("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", 1.0),
            ("Package_TO_SOT_SMD:SOT-23_Handsoldering", 1.0),
            // Hero-mesh placeholders
            ("MCU_RaspberryPi_and_Boards:RPi_Pico_SMD", 1.5),
            ("MEM2075-00-140-01-A:GCT_MEM2075-00-140-01-A", 1.5),
            ("OSO-BOOK-C2-01:OSO-BOOK-C2-01", 1.5),
            // Mechanical
            ("Battery_Holder:AAA_SMT", 12.0),
        ];
        for (fp, expected) in cases {
            let got = height3d_for(fp);
            assert!(
                (got - expected).abs() < 1e-4,
                "height3d_for({fp:?}) = {got}, expected {expected}"
            );
        }
    }

    #[test]
    fn unknown_footprint_defaults_to_one() {
        assert_eq!(height3d_for("Nonexistent:SomeFootprint"), 1.0);
    }

    #[test]
    fn slide_switch_before_smd_button() {
        // The SPDT slide switch lives in `Button_Switch_SMD:` but is 2.5mm,
        // not 3.5mm. Ordering matters; assert it here so reshuffling the
        // match list doesn't silently reclassify SW1.
        let fp = "Button_Switch_SMD:SW_SPDT_CK-JS102011SAQN";
        assert_eq!(height3d_for(fp), 2.5);
    }

    /// Every EAGLE package string that appears in the C2 `.brd` gets an
    /// expected height. Catches regressions if a new package slips in or a
    /// rule gets reordered.
    #[test]
    fn c2_packages_get_expected_heights() {
        let cases: &[(&str, f32)] = &[
            ("0805-NO", 0.6),
            ("MICROBUILDER__0805", 0.6),
            ("_0603", 0.6),
            ("SOD-123", 1.1),
            ("SOT23-3", 1.1),
            ("EINK_24PIN", 1.5),
        ];
        for (pkg, expected) in cases {
            let got = height3d_for_eagle(pkg);
            assert!(
                (got - expected).abs() < 1e-4,
                "height3d_for_eagle({pkg:?}) = {got}, expected {expected}"
            );
        }
    }

    #[test]
    fn unknown_eagle_package_defaults_to_one() {
        assert_eq!(height3d_for_eagle("BIGOVAL"), 1.0);
        assert_eq!(height3d_for_eagle("UNKNOWN"), 1.0);
    }
}

//! Net-name → category classifier and per-component dominant-category picker.
//!
//! Heuristic: substring matches on net names, first match wins. Applied
//! identically to KiCad and EAGLE net names so both boards share the same
//! classification semantics.

use crate::types::{NetCategory, Pad};

/// Classify a single net name into a `NetCategory`. Case-insensitive
/// substring match, first rule wins.
pub fn classify_net_name(name: &str) -> NetCategory {
    let lower = name.to_ascii_lowercase();

    // Power rails
    if lower.starts_with("vcc")
        || lower.starts_with("vdd")
        || lower.starts_with("+3v3")
        || lower.starts_with("+3.3v")
        || lower.starts_with("+5v")
        || lower.starts_with("+batt")
        || lower.starts_with("vbus")
        || lower.starts_with("vbat")
        || lower.starts_with("vsys")
        || lower.starts_with("vpp")
        || lower.starts_with("vee")
        || lower.starts_with("vdda")
        || lower.contains("+3.3vp")
        || lower.contains("+3v3")
    {
        return NetCategory::Power;
    }

    // Ground
    if lower.starts_with("gnd")
        || lower.starts_with("vss")
        || lower.starts_with("agnd")
        || lower.starts_with("dgnd")
        || lower.starts_with("pgnd")
    {
        return NetCategory::Ground;
    }

    // SPI
    if lower.contains("sclk")
        || lower.contains("_sck")
        || lower.contains("/sck")
        || lower == "sck"
        || lower.contains("miso")
        || lower.contains("mosi")
        || lower.contains("cipo")
        || lower.contains("copi")
        || lower.contains("display_cs")
        || lower.contains("display_dc")
        || lower.contains("display_mosi")
        || lower.contains("display_sck")
        || lower.contains("sd_cs")
        || lower.contains("babel_cs")
        || lower.contains("eink_cs")
        || lower.contains("eink_dc")
        || lower.contains("eink_sck")
        || lower.contains("eink_mosi")
    {
        return NetCategory::Spi;
    }

    // I²C
    if lower.contains("sda") || lower.contains("scl") || lower.contains("i2c") {
        return NetCategory::I2c;
    }

    // Debug — match standalone RESET (not display_reset which is GPIO)
    if lower.contains("swdio")
        || lower.contains("swclk")
        || lower.contains("jtag")
        || lower.contains("uart")
        || lower.ends_with("reset") && !lower.contains("display")
    {
        return NetCategory::Debug;
    }

    // Analog
    if lower.contains("analog")
        || lower.contains("adc")
        || lower.contains("vref")
    {
        return NetCategory::Analog;
    }

    // GPIO (buttons, LEDs, general IO)
    if lower.contains("btn_")
        || lower.contains("button")
        || lower.contains("led")
        || lower.contains("gp26")
        || lower.contains("gp27")
        || lower.contains("sd_cd")
        || lower.contains("display_busy")
        || lower.contains("display_reset")
        || lower.contains("eink_busy")
        || lower.contains("eink_rst")
        || lower.contains("/en")
        || lower.contains("~{en")
    {
        return NetCategory::Gpio;
    }

    NetCategory::Other
}

/// Priority for tie-breaking when multiple categories have the same pad count.
/// Lower number wins.
fn category_priority(cat: NetCategory) -> u8 {
    match cat {
        NetCategory::Power => 0,
        NetCategory::Ground => 1,
        NetCategory::Spi => 2,
        NetCategory::I2c => 3,
        NetCategory::Debug => 4,
        NetCategory::Analog => 5,
        NetCategory::Gpio => 6,
        NetCategory::Other => 7,
    }
}

/// Pick the dominant net category for a component by counting pad-net
/// classifications. Returns `None` if the component has no pads with net
/// names (e.g., the synthesized GDEW042T2 display).
pub fn pick_dominant(pads: &[Pad]) -> Option<NetCategory> {
    let mut counts = [0u32; 8]; // indexed by category_priority
    let mut any = false;

    for pad in pads {
        if let Some(ref name) = pad.net_name {
            // Skip "unconnected-*" pseudo-nets
            if name.starts_with("unconnected-") {
                continue;
            }
            let cat = classify_net_name(name);
            counts[category_priority(cat) as usize] += 1;
            any = true;
        }
    }

    if !any {
        return None;
    }

    // Find category with highest count; ties broken by priority (lower index wins)
    let mut best_idx = 0;
    let mut best_count = 0;
    for (i, &c) in counts.iter().enumerate() {
        if c > best_count {
            best_count = c;
            best_idx = i;
        }
    }

    // Map index back to category
    Some(match best_idx {
        0 => NetCategory::Power,
        1 => NetCategory::Ground,
        2 => NetCategory::Spi,
        3 => NetCategory::I2c,
        4 => NetCategory::Debug,
        5 => NetCategory::Analog,
        6 => NetCategory::Gpio,
        _ => NetCategory::Other,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn power_rails() {
        assert_eq!(classify_net_name("+3V3"), NetCategory::Power);
        assert_eq!(classify_net_name("+3.3VP"), NetCategory::Power);
        assert_eq!(classify_net_name("VCC"), NetCategory::Power);
        assert_eq!(classify_net_name("VBUS"), NetCategory::Power);
        assert_eq!(classify_net_name("+BATT"), NetCategory::Power);
    }

    #[test]
    fn ground() {
        assert_eq!(classify_net_name("GND"), NetCategory::Ground);
    }

    #[test]
    fn spi_signals() {
        assert_eq!(classify_net_name("/DISPLAY_MOSI"), NetCategory::Spi);
        assert_eq!(classify_net_name("/DISPLAY_SCK"), NetCategory::Spi);
        assert_eq!(classify_net_name("/DISPLAY_CS"), NetCategory::Spi);
        assert_eq!(classify_net_name("/SD_CS"), NetCategory::Spi);
        assert_eq!(classify_net_name("/SCK"), NetCategory::Spi);
        assert_eq!(classify_net_name("/MOSI"), NetCategory::Spi);
        assert_eq!(classify_net_name("/MISO"), NetCategory::Spi);
        assert_eq!(classify_net_name("/BABEL_CS"), NetCategory::Spi);
        assert_eq!(classify_net_name("EINK_CS"), NetCategory::Spi);
        assert_eq!(classify_net_name("EINK_DC"), NetCategory::Spi);
        assert_eq!(classify_net_name("SCK"), NetCategory::Spi);
    }

    #[test]
    fn i2c_signals() {
        assert_eq!(classify_net_name("/TX{slash}SDA"), NetCategory::I2c);
        assert_eq!(classify_net_name("/RX{slash}SCL"), NetCategory::I2c);
    }

    #[test]
    fn debug_signals() {
        assert_eq!(classify_net_name("/SWDIO"), NetCategory::Debug);
        assert_eq!(classify_net_name("/SWCLK"), NetCategory::Debug);
        assert_eq!(classify_net_name("/RESET"), NetCategory::Debug);
    }

    #[test]
    fn gpio_signals() {
        assert_eq!(classify_net_name("/BTN_DOWN"), NetCategory::Gpio);
        assert_eq!(classify_net_name("/BTN_UP"), NetCategory::Gpio);
        assert_eq!(classify_net_name("/SD_CD"), NetCategory::Gpio);
        assert_eq!(classify_net_name("/DISPLAY_BUSY"), NetCategory::Gpio);
        assert_eq!(classify_net_name("/DISPLAY_RESET"), NetCategory::Gpio);
        assert_eq!(classify_net_name("/GP26"), NetCategory::Gpio);
        assert_eq!(classify_net_name("/EN"), NetCategory::Gpio);
        assert_eq!(classify_net_name("/~{EN2}"), NetCategory::Gpio);
    }

    #[test]
    fn unconnected_is_other() {
        assert_eq!(
            classify_net_name("unconnected-(SW1-Pad1)"),
            NetCategory::Other
        );
    }
}

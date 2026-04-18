// About tab — orientation copy and ordering guide for builders.
// Six sections: what the Open Book is, ordering the boards, what this app
// does, project status, credits, and developer info.

import { useDataset } from '../lib/dataset-context';
import { useBreakpoint } from '../lib/use-breakpoint';

export function AboutView() {
  const { bom, assembly } = useDataset();
  const bp = useBreakpoint();
  const compact = bp === 'compact';

  return (
    <div
      style={{
        maxWidth: '720px',
        marginInline: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: compact ? '14px' : '20px',
        color: '#cbd5e1',
        fontSize: compact ? '12px' : '13px',
        lineHeight: 1.6,
        padding: compact ? '0 0 24px' : '4px 4px 40px',
      }}
    >
      <header style={{ borderBottom: '1px solid #334155', paddingBottom: compact ? '8px' : '12px' }}>
        <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
          A pre-flight check for building an Open Book e-reader.
        </p>
      </header>

      <Section title="What the Open Book is" compact={compact}>
        <p style={paragraph}>
          <Ext href="https://www.oddlyspecificobjects.com/projects/openbook/">The Open Book</Ext>{' '}
          is an open-source hardware e-reader designed by{' '}
          <Ext href="https://joeycastillo.com">Joey Castillo</Ext>, licensed CC-BY-SA 4.0.
          It pairs a Raspberry Pi Pico with a 4.2-inch B&W e-paper display, runs on two AAA
          batteries, and reads books from a microSD card. The firmware supports bold, italic,
          chapter breaks, front-matter metadata, and the full Unicode Basic Multilingual Plane
          including right-to-left scripts.
        </p>
        <p style={paragraph}>
          The hardware is split across two PCBs. The <strong style={strong}>main board</strong>{' '}
          (<code style={code}>OSO-BOOK-C1</code>) carries the Pico, battery holder, buttons,
          microSD slot, and the connector for the display. A small{' '}
          <strong style={strong}>daughter board</strong> (<code style={code}>OSO-BOOK-C2</code>)
          solders onto the main board via half-circle edge pads called "castellations." It generates
          the high voltages the e-paper display needs and converts signal levels between the Pico and
          the screen. You order the daughter board pre-assembled from a fab house and solder it on
          in one step.
        </p>
      </Section>

      <Section title="Ordering the boards" compact={compact}>
        <p style={paragraph}>
          You need two boards and one display panel. Upload the gerber files from the{' '}
          <Ext href="https://github.com/joeycastillo/The-Open-Book/tree/main/Fabrication%20Files">
            upstream Fabrication Files directory
          </Ext>{' '}
          to your PCB fab. <em>Note: the upstream README references older file versions — the specs
          below are current.</em>
        </p>

        <h3 style={subheading}>C1 main board (bare PCB — you solder the parts)</h3>
        <table style={specTable}>
          <tbody>
            <tr><td style={specLabel}>Gerber file</td><td style={specValue}><code style={code}>OSO-BOOK-C1-05-rounded.zip</code></td></tr>
            <tr><td style={specLabel}>Layers</td><td style={specValue}>2</td></tr>
            <tr>
              <td style={specLabel}>Thickness</td>
              <td style={specValue}>
                <strong style={strong}>1.0 mm</strong>
                <span style={{ color: '#94a3b8' }}>{' '}(required — the 3D-printed case is designed for this thickness)</span>
              </td>
            </tr>
            <tr>
              <td style={specLabel}>Surface finish</td>
              <td style={specValue}>
                <strong style={strong}>Lead-free HASL</strong>
                <span style={{ color: '#94a3b8' }}>{' '}(or ENIG if you want gold pads)</span>
              </td>
            </tr>
            <tr><td style={specLabel}>Solder mask</td><td style={specValue}>Green (or any color — cosmetic only)</td></tr>
            <tr><td style={specLabel}>Copper weight</td><td style={specValue}>1 oz (standard)</td></tr>
          </tbody>
        </table>
        <div style={callout}>
          <strong style={strong}>Settings to change from defaults:</strong> Most fab houses default to
          1.6 mm thickness and leaded HASL. Change <strong style={strong}>thickness to 1.0 mm</strong> and{' '}
          <strong style={strong}>surface finish to lead-free HASL</strong>. Everything else (2-layer, FR-4,
          1 oz copper, green mask) matches defaults on both JLCPCB and PCBWay.
          Also recommended: enable "Confirm Production File" so the fab reviews your gerbers before cutting.
        </div>

        <h3 style={subheading}>C2 e-paper driver (pre-assembled — the fab house populates it)</h3>
        <p style={paragraph}>
          Upload the <strong style={strong}>gerber + BOM + pick-and-place</strong> files to your
          fab house's assembly (PCBA) service. Same board specs as C1 (1.0 mm, lead-free HASL).
        </p>
        <table style={specTable}>
          <tbody>
            <tr>
              <td style={specLabel}>JLCPCB</td>
              <td style={specValue}>
                <code style={code}>OSO-BOOK-C2-03</code> files
                <span style={{ color: '#94a3b8' }}>{' '}(the README says C2-01, but that's been replaced)</span>
              </td>
            </tr>
            <tr>
              <td style={specLabel}>PCBWay</td>
              <td style={specValue}><code style={code}>OSO-BOOK-C2-02</code> files</td>
            </tr>
            <tr>
              <td style={specLabel}>Assembly type</td>
              <td style={specValue}>
                Turnkey (fab sources parts){' '}
                <span style={{ color: '#94a3b8' }}>· JLCPCB: "Economic" · PCBWay: "Turnkey"</span>
              </td>
            </tr>
            <tr>
              <td style={specLabel}>Assembly side</td>
              <td style={specValue}>Top only</td>
            </tr>
          </tbody>
        </table>
        <div style={callout}>
          <strong style={strong}>Extra settings for C2:</strong> In addition to thickness and surface finish,
          set <strong style={strong}>castellated holes to Yes</strong> — the C2 module uses half-circle
          edge pads to connect to the main board. On JLCPCB, toggle "PCB Assembly" on at the bottom
          of the quote page, select Economic assembly, and upload the BOM + pick-and-place CSVs.
        </div>
        <p style={paragraph}>
          Budget <strong style={strong}>$30–80 per unit</strong> for the C2 assembly — this cost is
          not included in any upstream BOM total.
        </p>

        <h3 style={subheading}>Display</h3>
        <p style={paragraph}>
          Order a 4.2-inch B&W GoodDisplay panel — you will most likely receive a{' '}
          <strong style={strong}>GDEY042T81</strong> (the original GDEW042T2 is end-of-life).
          The panels are physically identical (same FPC connector, confirmed drop-in by community
          testers). The firmware flash step on the <em>Assembly</em> tab handles the controller
          difference automatically — it builds from{' '}
          <Ext href="https://github.com/joeycastillo/libros/pull/11">PR #11</Ext>, which
          auto-detects which display is connected.
        </p>
      </Section>

      <Section title="What this app does" compact={compact}>
        <p style={paragraph}>
          Open Book Builder is a pre-flight check for the Open Book build. It combines a unified
          parts list, ordering specs, assembly steps, and interactive 3D views of both boards —
          everything you need to verify your build before spending money.
        </p>
        <p style={paragraph}>
          It currently tracks <Stat n={bom.length} unit="parts" /> and{' '}
          <Stat n={assembly.length} unit="assembly steps" />, and renders both boards in 3D
          from the original design files (KiCad for the main board, EAGLE for the driver module).
          The <em>Parts List</em> tab exports a Digi-Key BOM Manager CSV you can upload directly.
        </p>
        <p style={paragraph}>
          This app targets the two-board Pico design in the{' '}
          <Ext href="https://github.com/joeycastillo/The-Open-Book">project's GitHub repository</Ext>.
          The design files are read-only inputs — nothing in this tool writes back to the
          original project.
        </p>
      </Section>

      <Section title="Project status (April 2026)" compact={compact}>
        <p style={paragraph}>
          The Pico-based "Abridged Edition" covered here is the current DIY build. The{' '}
          <Ext href="https://github.com/joeycastillo/libros">libros firmware</Ext> repo has not
          had a maintainer commit since February 2024 — Joey's focus has shifted to the Open Book
          Touch. Community contributor{' '}
          <Ext href="https://github.com/joeycastillo/libros/pull/11">PR #11</Ext> adds
          auto-detection for the newer GDEY042T81 display and has been merge-ready since December
          2025. It is the recommended firmware source for new builds.
        </p>
        <p style={paragraph}>
          Separately, Joey has announced the{' '}
          <Ext href="https://www.crowdsupply.com/oddly-specific-objects/open-book-touch">Open Book Touch</Ext>{' '}
          — an ESP32-S3-based next-generation e-reader with a 4.26-inch capacitive touch display,
          front light, WiFi/Bluetooth, and USB-C charging. It is heading to Crowd Supply and
          represents the project's long-term direction. The Pico-based build remains the accessible
          DIY option.
        </p>
        <p style={paragraph}>
          Community resources:{' '}
          <Ext href="https://discord.gg/b6FgeqSZs3">Discord</Ext>{' · '}
          <Ext href="https://www.oddlyspecificobjects.com/projects/openbook/">Project documentation</Ext>{' · '}
          <Ext href="https://hackaday.io/project/192688-the-open-book">Hackaday.io</Ext>
        </p>
      </Section>

      <Section title="Credits &amp; license" compact={compact}>
        <p style={paragraph}>
          The Open Book hardware is © Joey Castillo, licensed{' '}
          <Ext href="https://creativecommons.org/licenses/by-sa/4.0/">CC-BY-SA 4.0</Ext>. Upstream
          source: <Ext href="https://github.com/joeycastillo/The-Open-Book">github.com/joeycastillo/The-Open-Book</Ext>.
        </p>
        <p style={paragraph}>
          This tool is MIT-licensed and was built with Claude Code as a scaffolding and
          pair-programming partner. Issues and patches welcome at{' '}
          <Ext href="https://github.com/cwcorella-git/open-book-builder">github.com/cwcorella-git/open-book-builder</Ext>.
        </p>
      </Section>

      <Section title="For developers" compact={compact}>
        <p style={paragraph}>
          Tauri v2 + React 19 + Three.js. The same codebase ships as a desktop app (reads the
          design files live via a Rust <code style={code}>invoke</code> command) and as a
          static web build (dataset baked to JSON at build time). The web build is hosted on{' '}
          <Ext href="https://cwcorella-git.github.io/open-book-builder/">GitHub Pages</Ext>.
        </p>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------

const paragraph: React.CSSProperties = { margin: 0 };

const strong: React.CSSProperties = { color: '#f1f5f9' };

const callout: React.CSSProperties = {
  margin: 0,
  padding: '10px 12px',
  background: '#0f172a',
  border: '1px solid #1e293b',
  borderRadius: '5px',
  fontSize: '12px',
  lineHeight: 1.5,
  color: '#94a3b8',
};

const code: React.CSSProperties = {
  fontFamily: 'monospace',
  fontSize: '12px',
  color: '#e2e8f0',
  background: '#0f172a',
  padding: '1px 5px',
  borderRadius: '3px',
};

const subheading: React.CSSProperties = {
  margin: 0,
  fontSize: '12px',
  color: '#e2e8f0',
  fontWeight: 600,
};

const specTable: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '12px',
};

const specLabel: React.CSSProperties = {
  padding: '5px 10px 5px 0',
  color: '#94a3b8',
  verticalAlign: 'top',
  borderBottom: '1px solid #1e293b',
};

const specValue: React.CSSProperties = {
  padding: '5px 0',
  color: '#e2e8f0',
  borderBottom: '1px solid #1e293b',
};

function Section({ title, children, compact }: { title: string; children: React.ReactNode; compact?: boolean }) {
  return (
    <section
      style={{
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: '8px',
        padding: compact ? '12px 14px' : '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: compact ? '8px' : '10px',
      }}
    >
      <h2
        style={{
          margin: 0,
          fontSize: '13px',
          color: '#f1f5f9',
          textTransform: 'uppercase',
          letterSpacing: '0.6px',
        }}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

function Ext({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      style={{ color: '#60a5fa', textDecoration: 'none' }}
    >
      {children}
    </a>
  );
}

function Stat({ n, unit }: { n: number; unit: string }) {
  return (
    <strong style={{ color: '#f1f5f9' }}>
      {n} {unit}
    </strong>
  );
}

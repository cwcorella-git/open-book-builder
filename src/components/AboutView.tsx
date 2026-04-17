// About tab — static orientation copy for new readers landing on the web
// build. No data dependencies; no interaction. Four sections: what the
// Open Book is, what this app is, how this build relates to upstream's
// older ESP32-S3 doc, and credits.

import { useDataset } from '../lib/dataset-context';

export function AboutView() {
  const { bom, discrepancies, assembly } = useDataset();

  return (
    <div
      style={{
        maxWidth: '720px',
        marginInline: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        color: '#cbd5e1',
        fontSize: '13px',
        lineHeight: 1.6,
        padding: '4px 4px 40px',
      }}
    >
      <header style={{ borderBottom: '1px solid #334155', paddingBottom: '12px' }}>
        <h1 style={{ margin: 0, fontSize: '18px', color: '#f1f5f9', letterSpacing: '0.3px' }}>
          Open Book Builder
        </h1>
        <p style={{ margin: '6px 0 0', fontSize: '12px', color: '#94a3b8' }}>
          A pre-flight check for building an Open Book e-reader.
        </p>
      </header>

      <Section title="What the Open Book is">
        <p style={paragraph}>
          <Ext href="https://www.oddlyspecificobjects.com/projects/openbook/">The Open Book</Ext>{' '}
          is an open-source hardware e-reader designed by{' '}
          <Ext href="https://joeycastillo.com">Joey Castillo</Ext>, licensed CC-BY-SA 4.0.
          It pairs a Raspberry Pi Pico with a GoodDisplay GDEW042T2 4.2-inch e-paper panel, runs on
          two AAA batteries, and reads books from a microSD card.
        </p>
        <p style={paragraph}>
          The hardware is split across two PCBs. The main board (<code style={code}>OSO-BOOK-C1</code>){' '}
          carries the Pico, battery holder, buttons, microSD slot, and the connector for the
          display. A small daughter board (<code style={code}>OSO-BOOK-C2-02</code>) solders onto the
          main board via half-circle edge pads called "castellations." It generates the high voltages the
          e-paper display needs and converts signal levels between the Pico and the screen. Isolating
          that circuitry on a separately-orderable module keeps the main board simple and hand-solderable.
        </p>
      </Section>

      <Section title="What this app is">
        <p style={paragraph}>
          Open Book Builder is a personal tool for sanity-checking a build of the Open Book before
          ordering PCBs and parts. Three parts lists circulating in the project's GitHub repository
          disagreed on quantities and costs; a PCBWay order had two build-critical errors; a community
          cost-of-goods list mixed annotations from an older board into the current design. This tool
          unifies those sources into one place.
        </p>
        <p style={paragraph}>
          It currently knows about <Stat n={bom.length} unit="parts" />,{' '}
          <Stat n={discrepancies.length} unit="discrepancies" />, and{' '}
          <Stat n={assembly.length} unit="assembly steps" />, and renders both boards in 3D from
          the original circuit board design files (KiCad for the main board, EAGLE for the driver
          module). The{' '}
          <em>Discrepancies</em> tab surfaces unresolved build-critical issues as a red banner
          until you've reviewed them; the <em>BOM</em> tab emits a Digi-Key BOM Manager CSV you can
          upload directly.
        </p>
      </Section>

      <Section title="Relationship to the original project">
        <p style={paragraph}>
          This app targets the current two-board Pico design in the project's GitHub (
          <code style={code}>OSO-BOOK-C1</code> + <code style={code}>OSO-BOOK-C2-02</code>). If
          you've read the <code style={code}>why-the-open-book</code> document in the project
          tree, note that it describes an earlier ESP32-S3 prototype ("B1") — it's the project's
          origin story, not a spec for what gets built today. The discrepancies surfaced in this
          tool are partly about reconciling that drift: the doc mentions SRAM and audio hardware
          that simply aren't on the current boards.
        </p>
        <p style={paragraph}>
          The original design files (circuit board layouts and parts lists) are read-only inputs;
          nothing in this tool writes back to the original project.
        </p>
      </Section>

      <Section title="Credits &amp; license">
        <p style={paragraph}>
          The Open Book hardware is © Joey Castillo, licensed{' '}
          <Ext href="https://creativecommons.org/licenses/by-sa/4.0/">CC-BY-SA 4.0</Ext>. Upstream
          source: <Ext href="https://github.com/joeycastillo/The-Open-Book">github.com/joeycastillo/The-Open-Book</Ext>.
        </p>
        <p style={paragraph}>
          This tool is MIT-licensed and was built by Christopher Corella with Claude Code as a
          scaffolding and pair-programming partner. Issues and patches welcome at{' '}
          <Ext href="https://github.com/cwcorella-git/open-book-builder">github.com/cwcorella-git/open-book-builder</Ext>.
        </p>
      </Section>

      <Section title="For developers">
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

const code: React.CSSProperties = {
  fontFamily: 'monospace',
  fontSize: '12px',
  color: '#e2e8f0',
  background: '#0f172a',
  padding: '1px 5px',
  borderRadius: '3px',
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section
      style={{
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: '8px',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
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

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { useBreakpoint } from '../lib/use-breakpoint';

const BASE = import.meta.env.BASE_URL;

const linkStyle: React.CSSProperties = { color: '#93c5fd', textDecoration: 'none' };

const code: React.CSSProperties = {
  fontFamily: 'monospace',
  fontSize: '11px',
  color: '#e2e8f0',
  background: '#0f172a',
  padding: '1px 5px',
  borderRadius: '3px',
};

type DesignId = 'sprint-5' | 'minimal';

interface Part {
  url: string;
  /** Offset in case-local mm. Used for exploded-view separation. */
  offset?: [number, number, number];
}

interface CaseDesign {
  id: DesignId;
  label: string;
  blurb: React.ReactNode;
  parts: Part[];
  /** Files to expose as download links. */
  downloads: { label: string; url: string }[];
}

const DESIGNS: CaseDesign[] = [
  {
    id: 'sprint-5',
    label: 'Sprint 5 (two-part)',
    blurb: (
      <>
        Two-part case from Joey Castillo's{' '}
        <a
          href="https://hackaday.io/project/192688-the-open-book/files"
          target="_blank"
          rel="noreferrer"
          style={linkStyle}
        >
          Hackaday Prize 2023 submission
        </a>{' '}
        (Oct 2023) — the 5th iteration of his parametric enclosure design.
        Originally targeting the B1 ESP32-S3 prototype, but B1 and the Pico C1
        share board outline so the same Hackaday-rendered STLs (88.6 × 118.6 mm)
        fit a C1 build. Assembly uses four M2.5 × 6 mm screws — countersunk
        through the frontplate, threading directly into the plastic backplate.
        Total stack-up under 10 mm. The{' '}
        <code style={code}>.scad</code> source is parametric: toggle{' '}
        <code style={code}>abridged</code> for AAA-holder Z-clearance (Pico) vs
        LiPo (B1), and adjust wall thickness, screen bevel, or JST-PH cutouts
        before re-rendering.
      </>
    ),
    parts: [
      // Sprint 5 STLs were exported with frontplate at negative X and
      // backplate at positive X in case-local coordinates. Push them further
      // apart so they read as an exploded view.
      { url: `${BASE}case/sprint-5-frontplate.stl`, offset: [-25, 0, 0] },
      { url: `${BASE}case/sprint-5-backplate.stl`, offset: [25, 0, 0] },
    ],
    downloads: [
      { label: 'Frontplate STL', url: `${BASE}case/sprint-5-frontplate.stl` },
      { label: 'Backplate STL', url: `${BASE}case/sprint-5-backplate.stl` },
      { label: 'OpenSCAD source', url: `${BASE}case/sprint-5.scad` },
    ],
  },
  {
    id: 'minimal',
    label: 'Minimal Case (back cover only)',
    blurb: (
      <>
        Joey Castillo's upstream design from{' '}
        <a
          href="https://github.com/joeycastillo/The-Open-Book/tree/main/3D%20Printed%20Case"
          target="_blank"
          rel="noreferrer"
          style={linkStyle}
        >
          joeycastillo/The-Open-Book
        </a>
        . This is a single back-cover only — there is no front bezel. The PCB
        itself serves as the front face of the device, with the e-paper display
        and buttons exposed. M2.5 screws, no supports needed. Sized for a
        1.0 mm-thick PCB.
      </>
    ),
    parts: [{ url: `${BASE}case/open-book-abridged-minimal-case.stl` }],
    downloads: [
      { label: 'Minimal Case STL', url: `${BASE}case/open-book-abridged-minimal-case.stl` },
    ],
  },
];

export function CaseView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [design, setDesign] = useState<DesignId>('sprint-5');
  const [status, setStatus] = useState<'loading' | 'ready' | { error: string }>('loading');
  const bp = useBreakpoint();
  const compact = bp === 'compact';

  const active = DESIGNS.find((d) => d.id === design)!;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    setStatus('loading');

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#0b1220');

    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 5000);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.AmbientLight(0xffffff, 0.45));
    const key = new THREE.DirectionalLight(0xffffff, 0.85);
    key.position.set(1, 1.5, 1);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xa3b5d4, 0.35);
    fill.position.set(-1, -0.5, -0.7);
    scene.add(fill);

    const root = new THREE.Group();
    // STL convention is Z-up; rotate so the case lies flat in our Y-up scene.
    root.rotation.x = -Math.PI / 2;
    scene.add(root);

    const ownedGeometries: THREE.BufferGeometry[] = [];
    const material = new THREE.MeshStandardMaterial({
      color: '#9ccc65',
      metalness: 0.05,
      roughness: 0.55,
      flatShading: true,
    });

    const resize = () => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      if (w === 0 || h === 0) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(container);

    let raf = 0;
    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(animate);
    };

    let cancelled = false;
    const loader = new STLLoader();

    Promise.all(
      active.parts.map(
        (part) =>
          new Promise<{ geom: THREE.BufferGeometry; offset: [number, number, number] }>((resolve, reject) => {
            loader.load(
              part.url,
              (geom) => resolve({ geom, offset: part.offset ?? [0, 0, 0] }),
              undefined,
              (err) => reject(err),
            );
          }),
      ),
    )
      .then((results) => {
        if (cancelled) {
          results.forEach((r) => r.geom.dispose());
          return;
        }

        // Compute combined center across all parts so the camera frames the
        // whole assembly, not just one half.
        const overallBox = new THREE.Box3();
        const meshes: THREE.Mesh[] = [];
        for (const { geom, offset } of results) {
          geom.computeVertexNormals();
          const mesh = new THREE.Mesh(geom, material);
          mesh.position.set(offset[0], offset[1], offset[2]);
          ownedGeometries.push(geom);
          root.add(mesh);
          meshes.push(mesh);
          mesh.updateMatrixWorld(true);
          overallBox.expandByObject(mesh);
        }

        const center = overallBox.getCenter(new THREE.Vector3());
        const size = overallBox.getSize(new THREE.Vector3());
        // Recenter the assembly around the origin (post-rotation world).
        for (const mesh of meshes) {
          mesh.position.sub(new THREE.Vector3(
            center.x - root.position.x,
            center.y - root.position.y,
            center.z - root.position.z,
          ));
        }

        const radius = size.length() / 2;
        const fov = (camera.fov * Math.PI) / 180;
        const dist = radius / Math.sin(fov / 2);
        camera.position.set(dist * 0.6, dist * 0.55, dist * 0.7);
        camera.near = dist / 100;
        camera.far = dist * 100;
        camera.updateProjectionMatrix();
        controls.target.set(0, 0, 0);
        controls.update();

        setStatus('ready');
        animate();
      })
      .catch((err) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : String(err);
        setStatus({ error: message });
      });

    return () => {
      cancelled = true;
      if (raf) cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      ownedGeometries.forEach((g) => g.dispose());
      material.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [active]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '10px' }}>
      <div style={{
        padding: compact ? '8px 10px' : '10px 14px',
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: '6px',
        color: '#cbd5e1',
        fontSize: compact ? '11px' : '12px',
        lineHeight: 1.55,
      }}>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
          {DESIGNS.map((d) => (
            <button
              key={d.id}
              onClick={() => setDesign(d.id)}
              style={{
                padding: '4px 10px',
                fontSize: '11px',
                background: d.id === design ? '#334155' : 'transparent',
                color: '#e2e8f0',
                border: '1px solid ' + (d.id === design ? '#475569' : '#334155'),
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              {d.label}
            </button>
          ))}
        </div>
        <div style={{ marginBottom: '6px' }}>{active.blurb}</div>
        <div style={{ fontSize: '11px', color: '#94a3b8' }}>
          {active.downloads.map((dl, i) => (
            <span key={dl.url}>
              {i > 0 && ' · '}
              <a href={dl.url} download style={linkStyle}>{dl.label}</a>
            </span>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, position: 'relative', minHeight: '300px' }}>
        <div
          ref={containerRef}
          style={{
            position: 'absolute',
            inset: 0,
            border: '1px solid #1e293b',
            borderRadius: '6px',
            overflow: 'hidden',
          }}
        />
        {status === 'loading' && <Overlay text="Loading case mesh…" />}
        {typeof status === 'object' && (
          <Overlay text={`Failed to load STL: ${status.error}`} />
        )}
      </div>
    </div>
  );
}

function Overlay({ text }: { text: string }) {
  return (
    <div style={{
      position: 'absolute',
      inset: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#94a3b8',
      fontSize: '12px',
      pointerEvents: 'none',
    }}>
      {text}
    </div>
  );
}

// Procedural hero meshes for visually-dominant components on the C1 board:
// Pi Pico (U1), C2 castellated submodule (U2), Keystone 1022 battery holder
// (BT1), MEM2075 microSD slot (U3). Each builder returns a THREE.Group + the
// owned GPU resources so `scene-renderer.ts` can add them to the scene and
// dispose them cleanly.
//
// Local-frame convention every builder follows:
//   - Origin at the PCB-touching face (the face that sits flush against the
//     board copper), growing toward +Y.
//   - Mesh laid out with its "outward face" (USB port, label text, battery
//     cells, microSD slot) facing +Y.
//   - `scene-renderer.ts::applyBoardSide` wraps the group for bottom-mounted
//     components and flips it via rotation.x = π so the outward face ends up
//     pointing into -Y (below the board).
//
// The goal is "recognizable at a glance" not CAD-accurate — users should
// spot the Pico / battery holder / SD slot / C2 module without reading the
// detail panel. Dimensions come from the footprint bbox baked into the
// dataset by kicad_pcb.rs, so the meshes scale correctly if someone tweaks
// the part-class heights in footprint_heights.rs.

import * as THREE from 'three';
import type { Component } from './types';

export interface HeroMeshResult {
  /** Root group, userData is set by the caller (ref / side / primaryMesh). */
  object: THREE.Group;
  /** The "main body" mesh — scene-renderer tints this for selection. */
  primaryMesh: THREE.Mesh;
  ownedGeometries: THREE.BufferGeometry[];
  ownedMaterials: THREE.Material[];
  ownedTextures: THREE.Texture[];
}

/**
 * Returns a procedural mesh for the given hero id, or `null` if the id is
 * unknown — caller falls back to the extruded-bbox box path.
 */
export function buildHeroMesh(
  id: string,
  component: Component,
): HeroMeshResult | null {
  switch (id) {
    case 'pi-pico':
      return buildPiPico(component);
    case 'c2-module':
      return buildC2Module(component);
    case 'keystone-1022':
      return buildKeystone1022(component);
    case 'mem2075':
      return buildMem2075(component);
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Raspberry Pi Pico — U1
//
// Black PCB 21.3 × 1.0 × 49.9 mm (W × thickness × length in local frame).
// Silver castellations along both long edges. Dark USB-C housing at one
// short edge + a centered "Raspberry Pi / Pico" label on the top face.

function buildPiPico(c: Component): HeroMeshResult {
  const geometries: THREE.BufferGeometry[] = [];
  const materials: THREE.Material[] = [];
  const textures: THREE.Texture[] = [];

  const w = c.footprintBbox.width;
  const l = c.footprintBbox.height; // KiCad-Y length is the Pico's long axis
  const pcbThickness = 1.0;

  const group = new THREE.Group();

  // Main PCB body.
  const pcbMat = new THREE.MeshStandardMaterial({
    color: 0x1f2937,
    roughness: 0.7,
    metalness: 0.05,
  });
  materials.push(pcbMat);
  const pcbGeom = new THREE.BoxGeometry(w, pcbThickness, l);
  pcbGeom.translate(0, pcbThickness / 2, 0);
  geometries.push(pcbGeom);
  const pcb = new THREE.Mesh(pcbGeom, pcbMat);
  group.add(pcb);

  // Castellation nubs — 20 per long edge. The real Pico has 20 pads per side,
  // so the count reads right even if the user stops to count them.
  const castMat = new THREE.MeshStandardMaterial({
    color: 0x9ca3af,
    roughness: 0.35,
    metalness: 0.8,
  });
  materials.push(castMat);
  const castCount = 20;
  const castGeom = new THREE.BoxGeometry(2.0, 0.6, 1.2);
  geometries.push(castGeom);
  // Leave ~2 mm of padding at each short edge (USB housing + opposite end).
  const castSpan = l - 4;
  for (let i = 0; i < castCount; i++) {
    const t = (i + 0.5) / castCount; // center-of-nub along [0, 1]
    const z = -castSpan / 2 + t * castSpan;
    for (const xSign of [-1, 1]) {
      const nub = new THREE.Mesh(castGeom, castMat);
      nub.position.set(xSign * (w / 2 - 0.2), pcbThickness / 2, z);
      group.add(nub);
    }
  }

  // USB-C housing — sits on top of the PCB at one short end.
  const usbMat = new THREE.MeshStandardMaterial({
    color: 0x4b5563,
    roughness: 0.4,
    metalness: 0.7,
  });
  materials.push(usbMat);
  const usbGeom = new THREE.BoxGeometry(8, 3, 6);
  usbGeom.translate(0, 1.5, 0);
  geometries.push(usbGeom);
  const usb = new THREE.Mesh(usbGeom, usbMat);
  // USB lives at the -Z end in local frame (near the shorter KiCad-Y coord).
  usb.position.set(0, pcbThickness, -l / 2 + 3);
  group.add(usb);

  // Top-face label. Float 0.02 mm above the PCB top to avoid z-fighting.
  const labelTex = makeTextTexture(['Raspberry Pi', 'Pico'], 256, 512);
  textures.push(labelTex);
  const labelMat = new THREE.MeshBasicMaterial({
    map: labelTex,
    transparent: true,
  });
  materials.push(labelMat);
  const labelGeom = new THREE.PlaneGeometry(w * 0.8, l * 0.35);
  geometries.push(labelGeom);
  const label = new THREE.Mesh(labelGeom, labelMat);
  label.rotation.x = -Math.PI / 2; // normal +Z → +Y (face-up)
  label.position.y = pcbThickness + 0.02;
  group.add(label);

  return { object: group, primaryMesh: pcb, ownedGeometries: geometries, ownedMaterials: materials, ownedTextures: textures };
}

// ---------------------------------------------------------------------------
// OSO-BOOK-C2 submodule — U2
//
// Green PCB 17.3 × 1.0 × 26.0 mm with castellations on both long edges and
// a handful of surface-mount rectangles on top to suggest ICs.

function buildC2Module(c: Component): HeroMeshResult {
  const geometries: THREE.BufferGeometry[] = [];
  const materials: THREE.Material[] = [];
  const textures: THREE.Texture[] = [];

  const w = c.footprintBbox.width;
  const l = c.footprintBbox.height;
  const pcbThickness = 1.0;

  const group = new THREE.Group();

  // Green PCB body.
  const pcbMat = new THREE.MeshStandardMaterial({
    color: 0x14532d,
    roughness: 0.6,
    metalness: 0.05,
  });
  materials.push(pcbMat);
  const pcbGeom = new THREE.BoxGeometry(w, pcbThickness, l);
  pcbGeom.translate(0, pcbThickness / 2, 0);
  geometries.push(pcbGeom);
  const pcb = new THREE.Mesh(pcbGeom, pcbMat);
  group.add(pcb);

  // Castellations — 12 per long edge.
  const castMat = new THREE.MeshStandardMaterial({
    color: 0x9ca3af,
    roughness: 0.35,
    metalness: 0.8,
  });
  materials.push(castMat);
  const castCount = 12;
  const castGeom = new THREE.BoxGeometry(1.6, 0.5, 1.0);
  geometries.push(castGeom);
  const castSpan = l - 3;
  for (let i = 0; i < castCount; i++) {
    const t = (i + 0.5) / castCount;
    const z = -castSpan / 2 + t * castSpan;
    for (const xSign of [-1, 1]) {
      const nub = new THREE.Mesh(castGeom, castMat);
      nub.position.set(xSign * (w / 2 - 0.15), pcbThickness / 2, z);
      group.add(nub);
    }
  }

  // IC/passive rectangles — a few small dark blocks to break up the green.
  const icMat = new THREE.MeshStandardMaterial({
    color: 0x0f172a,
    roughness: 0.5,
  });
  materials.push(icMat);
  const ics: [number, number, number, number][] = [
    // [cx, cz (local), w, d]  — positions relative to PCB top face
    [0, 6, 6, 5],
    [-3, -4, 3, 2],
    [3, -4, 3, 2],
    [0, -9, 4, 1.5],
  ];
  for (const [cx, cz, iw, id] of ics) {
    const icGeom = new THREE.BoxGeometry(iw, 0.5, id);
    icGeom.translate(0, 0.25, 0);
    geometries.push(icGeom);
    const ic = new THREE.Mesh(icGeom, icMat);
    ic.position.set(cx, pcbThickness, cz);
    group.add(ic);
  }

  // Label.
  const labelTex = makeTextTexture(['OSO-BOOK', 'C2'], 256, 256);
  textures.push(labelTex);
  const labelMat = new THREE.MeshBasicMaterial({
    map: labelTex,
    transparent: true,
  });
  materials.push(labelMat);
  const labelGeom = new THREE.PlaneGeometry(w * 0.75, w * 0.75);
  geometries.push(labelGeom);
  const label = new THREE.Mesh(labelGeom, labelMat);
  label.rotation.x = -Math.PI / 2;
  label.position.set(0, pcbThickness + 0.02, l / 2 - w * 0.5);
  group.add(label);

  return { object: group, primaryMesh: pcb, ownedGeometries: geometries, ownedMaterials: materials, ownedTextures: textures };
}

// ---------------------------------------------------------------------------
// Keystone 1022 AAA battery holder — BT1
//
// Black plastic base + two silver AAA cylinders lying along the X axis,
// offset in Z. Gold contact bumps at the inside ends of each slot.

function buildKeystone1022(c: Component): HeroMeshResult {
  const geometries: THREE.BufferGeometry[] = [];
  const materials: THREE.Material[] = [];
  const textures: THREE.Texture[] = [];

  const w = c.footprintBbox.width;
  const d = c.footprintBbox.height; // depth along KiCad Y
  const baseThickness = 2.0;
  const cellRadius = 5.25; // AAA ≈ 10.5 mm diameter
  const cellLength = Math.min(w - 12, 48); // leave room for end contacts

  const group = new THREE.Group();

  // Plastic base.
  const baseMat = new THREE.MeshStandardMaterial({
    color: 0x111827,
    roughness: 0.8,
  });
  materials.push(baseMat);
  const baseGeom = new THREE.BoxGeometry(w, baseThickness, d);
  baseGeom.translate(0, baseThickness / 2, 0);
  geometries.push(baseGeom);
  const base = new THREE.Mesh(baseGeom, baseMat);
  group.add(base);

  // Two AAA cells. CylinderGeometry's default axis is Y; rotate π/2 around Z
  // so the axis runs along X.
  const cellMat = new THREE.MeshStandardMaterial({
    color: 0xd1d5db,
    roughness: 0.25,
    metalness: 0.9,
  });
  materials.push(cellMat);
  // One shared geometry is fine — we don't dispose per-mesh.
  const cellGeom = new THREE.CylinderGeometry(cellRadius, cellRadius, cellLength, 24);
  cellGeom.rotateZ(Math.PI / 2);
  geometries.push(cellGeom);
  const cellCenterY = baseThickness + cellRadius;
  const cellOffsetZ = d / 2 - cellRadius - 0.5;
  for (const zSign of [-1, 1]) {
    const cell = new THREE.Mesh(cellGeom, cellMat);
    cell.position.set(0, cellCenterY, zSign * cellOffsetZ);
    group.add(cell);
  }

  // Gold contact bumps at the inside end of each slot (one per cell).
  const contactMat = new THREE.MeshStandardMaterial({
    color: 0xd4af37,
    roughness: 0.3,
    metalness: 0.8,
  });
  materials.push(contactMat);
  const contactGeom = new THREE.BoxGeometry(1.2, 1.2, 0.8);
  contactGeom.translate(0, 0.6, 0);
  geometries.push(contactGeom);
  for (const zSign of [-1, 1]) {
    const contact = new THREE.Mesh(contactGeom, contactMat);
    contact.position.set(cellLength / 2 + 0.6, baseThickness, zSign * cellOffsetZ);
    group.add(contact);
  }

  return { object: group, primaryMesh: base, ownedGeometries: geometries, ownedMaterials: materials, ownedTextures: textures };
}

// ---------------------------------------------------------------------------
// MEM2075 microSD card socket — U3
//
// Polished-steel housing with a visible slot opening on one face.

function buildMem2075(c: Component): HeroMeshResult {
  const geometries: THREE.BufferGeometry[] = [];
  const materials: THREE.Material[] = [];
  const textures: THREE.Texture[] = [];

  const w = c.footprintBbox.width;
  const d = c.footprintBbox.height;
  const housingHeight = Math.max(c.footprintBbox.height3d, 1.5);

  const group = new THREE.Group();

  // Outer steel housing.
  const housingMat = new THREE.MeshStandardMaterial({
    color: 0xcbd5e1,
    roughness: 0.3,
    metalness: 0.85,
  });
  materials.push(housingMat);
  const housingGeom = new THREE.BoxGeometry(w, housingHeight, d);
  housingGeom.translate(0, housingHeight / 2, 0);
  geometries.push(housingGeom);
  const housing = new THREE.Mesh(housingGeom, housingMat);
  group.add(housing);

  // Slot opening on the -X face — a thin dark inset just under the top.
  const slotMat = new THREE.MeshStandardMaterial({
    color: 0x0f172a,
    roughness: 0.9,
  });
  materials.push(slotMat);
  const slotThickness = 0.4; // x extent
  const slotHeight = Math.min(1.0, housingHeight * 0.6);
  const slotDepth = d * 0.75;
  const slotGeom = new THREE.BoxGeometry(slotThickness, slotHeight, slotDepth);
  geometries.push(slotGeom);
  const slot = new THREE.Mesh(slotGeom, slotMat);
  // Inset just barely into the -X face so the dark slot reads cleanly.
  slot.position.set(-w / 2 + slotThickness / 2 - 0.01, housingHeight - slotHeight / 2 - 0.2, 0);
  group.add(slot);

  return { object: group, primaryMesh: housing, ownedGeometries: geometries, ownedMaterials: materials, ownedTextures: textures };
}

// ---------------------------------------------------------------------------
// Shared helpers

/**
 * Render short text onto a 2D canvas and wrap it as a Three.js CanvasTexture.
 * Transparent background so the underlying PCB color shows through the
 * letter spacing. Caller is responsible for disposing the returned texture.
 */
function makeTextTexture(
  lines: string[],
  width: number,
  height: number,
): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    // Shouldn't happen in any browser we target, but keep it honest.
    return new THREE.CanvasTexture(canvas);
  }

  ctx.clearRect(0, 0, width, height);

  // Pick a font size that fits the tallest line in the given band height.
  const bandHeight = height / lines.length;
  const fontSize = Math.floor(bandHeight * 0.55);
  ctx.fillStyle = '#f8fafc';
  ctx.font = `bold ${fontSize}px sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  lines.forEach((line, i) => {
    ctx.fillText(line, width / 2, bandHeight * (i + 0.5));
  });

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  // Prevent texture blurring at oblique angles — labels stay readable.
  texture.anisotropy = 4;
  return texture;
}

---
name: fmri-overlay
description: Overlay a BOLD activation timeseries (from TRIBE v2 or any 20,484-vertex fsaverage5 cortex prediction) onto a Three.js / R3F mesh as a per-vertex color attribute, with smooth interpolation across timepoints. Use when the user has a BOLD trace and just wants to *see it on a brain*, without re-running brain-viz's full compose-and-narrate flow. Lighter, faster, demo-friendly.
version: 0.1.0
author: Mercury
license: MIT
metadata:
  mercury:
    tags: [3D, fMRI, BOLD, vertex-colors, R3F, three.js, overlay, neuroscience]
    category: creative
    related_skills: [brain-viz, three-js-component, three-js-debug, glsl-shader, cortex-bridge]
  hackathon:
    target: nous-research-creative-2026
    track: creative
prerequisites:
  packages: [three, "@react-three/fiber", "@react-three/drei"]
  files:
    - "An fsaverage5 cortex mesh — typically D:/cortex/data/fsaverage5_pial.glb"
    - "BOLD trace as JSON — array shape [n_timepoints, 20484]"
---

# fMRI Overlay — BOLD Trace → Animated Cortex

This skill turns a BOLD activation timeseries (the output of `cortex-bridge.brain_scan`) into a buttery-smooth animated cortex you can scrub through. Strictly client-side once the trace is loaded — no server round-trips per frame.

## When to Use

- You already have a BOLD trace and just want it animated on a mesh.
- You want to A/B two scans side-by-side (use two instances of this skill).
- You're recording the hackathon demo and brain-viz's full compose flow is overkill — this gets you to *the visual* in five seconds.
- You want to embed a cortex viewer inside an existing Three.js scene without inheriting Cortex's whole webapp.

**Do NOT use** for vertex counts that don't match fsaverage5 (20,484). For higher-resolution cortices (HCP MMP, Schaefer-1000), make a sister skill — the GLSL is similar but the mesh assumption changes.

## Inputs / Outputs

```ts
type BoldTrace = number[][];                 // shape [n_t, 20484]
type Overlay = {
  mesh:        THREE.BufferGeometry,         // fsaverage5 pial / inflated
  trace:       BoldTrace,
  fps:         number,                       // default 2 (TRIBE v2 native)
  colormap:    "rdbu" | "viridis" | "hot",   // default "rdbu" — diverging
  range:       [number, number] | "auto",    // z-score range, default auto
  smoothing:   "linear" | "cubic" | "none",  // temporal interpolation
};
type OverlayHandle = {
  play():       void,
  pause():      void,
  scrub(t: number): void,                    // t in seconds
  setColormap(c: Overlay["colormap"]): void,
  destroy():    void,
};
```

## How It Works (the 90-second mental model)

1. The fsaverage5 pial mesh has **20,484 vertices** (10,242 per hemisphere). Each vertex gets one BOLD scalar per timepoint.
2. We pre-compute a **3-D `Float32Array` texture** of shape `[n_t × 1 × 20484]` and bind it as a `DataTexture3D`. GPU does the timepoint sampling.
3. A **custom `ShaderMaterial`** samples the texture using `gl_VertexID / 20484` as the U coord and `(time * fps) / n_t` as the W coord, then maps the scalar through a colormap LUT (a small 1D `DataTexture` with 256 RGBA samples).
4. Smooth interpolation between TR samples is free — just don't snap the W coord to integers.

The whole render loop runs at native screen refresh; the BOLD trace can be 100 timepoints (50 s at 2 Hz) or 600 (5 min) without changing GPU cost meaningfully.

## Step-by-Step

### Step 1 — Load the mesh once

```js
import { useGLTF } from "@react-three/drei";
const { scene } = useGLTF("/data/fsaverage5_pial.glb");
const geom = scene.children[0].geometry;          // BufferGeometry, 20484 verts
```

If the mesh isn't on the asset server, drop it in `mercury-web/public/data/` or have Cortex's webapp serve it from `/api/mesh/fsaverage5_pial`.

### Step 2 — Pack the trace into a 3-D texture

```js
import * as THREE from "three";

const nT = trace.length;                          // e.g. 100
const flat = new Float32Array(nT * 20484);
for (let t = 0; t < nT; t++) {
  flat.set(trace[t], t * 20484);
}
const tex = new THREE.Data3DTexture(flat, 20484, 1, nT);
tex.format       = THREE.RedFormat;
tex.type         = THREE.FloatType;
tex.minFilter    = THREE.LinearFilter;
tex.magFilter    = THREE.LinearFilter;
tex.needsUpdate  = true;
```

### Step 3 — Mount the shader material

The full GLSL is in [`shader.glsl`](./shader.glsl) (sister skill `glsl-shader` will write the variant you need). The vertex shader writes the BOLD scalar to a varying; the fragment shader maps it through the colormap LUT.

```js
const material = new THREE.ShaderMaterial({
  uniforms: {
    boldTex:  { value: tex },
    lut:      { value: viridisLUT },              // pre-built 256×4 RGBA
    time:     { value: 0 },
    nT:       { value: nT },
    range:    { value: new THREE.Vector2(-3, 3) }, // z-score
  },
  vertexShader,
  fragmentShader,
});
const cortex = new THREE.Mesh(geom, material);
```

### Step 4 — Drive `time`

```js
useFrame((_, dt) => {
  if (!paused) material.uniforms.time.value += dt;
});
```

That's it. Scrubbing is `material.uniforms.time.value = seconds`.

## Colormap LUTs

Three built-in colormaps live in `mercury-web/src/lib/colormaps.ts`:

| Name | When |
|---|---|
| `rdbu` | Diverging — for z-scored or Δ activation. **Default.** |
| `viridis` | Sequential — for positive-only metrics. Color-blind safe. |
| `hot` | Sequential — for "where's the activation" demos. Pop-y. |

Each is a 256-entry `Uint8Array(1024)` (RGBA). New colormaps follow the same shape — bind as a `THREE.DataTexture(lut, 256, 1, RGBAFormat, UnsignedByteType)`.

## Output Contract

The skill returns an `OverlayHandle` (see top). The caller is responsible for mounting it into their scene; the skill doesn't open a window or take over the canvas.

## Performance Targets (RTX 5090 desktop, mercury-web)

| Mesh | n_t | Frame time |
|---|---:|---:|
| fsaverage5 pial (20,484 verts) | 100 | < 1.0 ms |
| fsaverage5 pial | 600 | < 1.2 ms |
| fsaverage6 pial (40,962) | 100 | < 1.5 ms |

Bottleneck is texture upload, not rendering. If the trace is being streamed (e.g. live decode from a TRIBE inference stream), allocate the texture once at max-n_t and partially update with `tex.image.data.set(...)`.

## Examples

### A — Drop into an existing R3F scene

```jsx
import { Cortex } from "@/components/Cortex";
<Canvas camera={{ position: [0, 0, 250] }}>
  <ambientLight intensity={0.4} />
  <Cortex traceUrl="/api/scan/abc123/bold" colormap="rdbu" />
  <OrbitControls />
</Canvas>
```

### B — Stand-alone demo page

A ready-to-use page is at `mercury-web/src/pages/CortexOverlay.tsx`. Pass a scan ID via the URL: `?scan=abc123`.

## Hackathon Submission Notes (Nous Creative 2026)

This skill is the *visual* of the brain-viz demo. While brain-viz handles compose + narrate (full pipeline), fmri-overlay is the lighter "just-show-me-the-pretty-cortex" call you'd make in the second half of the demo video to A/B two stimuli (e.g. cat video vs. metronome) without re-narrating each time.

Suggested 30-second segment in the recording:
1. Have two pre-scanned BOLD traces in `mercury-web/public/scans/`
2. Mount two side-by-side `<Cortex>` instances
3. Hit play on both — the user sees instant comparison: "Look how much more V1 lights up for the cat than for the metronome."

Trademark line still required: "Gemma is a trademark of Google LLC."

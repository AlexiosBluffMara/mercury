# Per-vertex (20,484) brain viewer upgrade — plan

The current viewer (`D:/cortex/webapp/public/main.js`) places **50 ROI markers**
over a flattened-sphere mesh. TRIBE v2 actually outputs `(T, 20484)` — one
BOLD z-score **per cortical vertex** on fsaverage5. We're rendering ~0.24%
of what the model produces.

Note on terminology: TRIBE v2 is a **surface-based** model (not volumetric),
so "voxel-by-voxel" on the cortical surface really means "vertex-by-vertex"
on fsaverage5 (10,242 verts × 2 hemispheres = 20,484 verts). True volumetric
voxels would require a different model and raymarching — out of scope for
the May 3 submission.

## Target

- **Color every vertex** of `brain_fsaverage5.glb` from BOLD z at the
  current timestep, not just 50 markers.
- **Smooth interpolation** between timesteps via a fragment shader so the
  scrubber animates fluidly.
- **Network-mask toggle** at vertex level (gray-out vertices outside the
  active Yeo-7 networks).
- **Click-to-inspect any vertex** with raycaster — shows the vertex's
  BOLD curve, parcel ID, network, anatomical label.

## Architecture

```
                                         ┌──────────────────────┐
   /api/scan/{id}/bold-vertex (new)  ──▶ │ packed Float32Array  │
                                         │ shape (T, 20484)     │  ~8 MB / scan
                                         └──────────┬───────────┘
                                                    ▼
                              ┌──────────────────────────────────────┐
                              │  upload as DataTexture (RGBA32F)     │
                              │  width = 20484 / 4  (5121 cols)      │
                              │  height = T                          │
                              └──────────┬───────────────────────────┘
                                         ▼
                              vertex shader reads tex(vertex_id, t)
                                         ▼
                              fragment shader Lerps between t and t+1
                                         ▼
                                   per-fragment color
```

## Files to change

| File | Change |
|---|---|
| `D:/cortex/webapp/public/main.js` | Replace 50-marker code with per-vertex shader pipeline (~250 LOC) |
| `D:/cortex/webapp/public/main.js` | Replace flattened-sphere mesh with `brain_fsaverage5.glb` actual load |
| `D:/cortex/webapp/server.py` | Add `GET /api/scan/{id}/bold-vertex` returning (T, 20484) Float32 |
| `D:/cortex/cortex/visualize.py` | Add `export_bold_vertex_packed(result, path)` — packs preds.npy → .bin |
| `D:/cortex/webapp/public/index.html` | Add inline `<script>` defining the GLSL strings (vertex + fragment) |
| `D:/cortex/webapp/public/atlas.json` | Add `vertex_to_parcel` field — 20,484-int array mapping vert→Schaefer parcel for click-inspect |

## Vertex shader

```glsl
attribute float vertexId;     // 0..20483
uniform sampler2D bold;       // Float texture (T x 5121 RGBA32F)
uniform float t_current;      // float frame index in [0, T-1]
uniform int  network_mask;    // bitmask of enabled Yeo networks
uniform sampler2D vertex_to_network;  // 20484 x 1 R8UI

varying float v_bold;
varying float v_active;

vec4 readBold(int v, int t) {
  // 4 verts packed per RGBA texel
  int col = v >> 2;
  int comp = v & 3;
  vec4 px = texelFetch(bold, ivec2(col, t), 0);
  return vec4(px[comp]);
}

void main() {
  int v = int(vertexId + 0.5);
  int t0 = int(floor(t_current));
  int t1 = t0 + 1;
  float a = fract(t_current);
  float b0 = readBold(v, t0).r;
  float b1 = readBold(v, t1).r;
  v_bold = mix(b0, b1, a);

  int net = int(texelFetch(vertex_to_network, ivec2(v, 0), 0).r);
  v_active = (network_mask & (1 << net)) != 0 ? 1.0 : 0.0;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
```

## Fragment shader (color ramp)

```glsl
varying float v_bold;     // z-score, ~[-4, 4]
varying float v_active;

vec3 ramp(float z) {
  // diverging viridis/inferno hybrid centered at 0
  float t = clamp((z + 4.0) / 8.0, 0.0, 1.0);
  return mix(vec3(0.05, 0.10, 0.30),
             mix(vec3(0.85, 0.85, 0.85),
                 vec3(0.95, 0.30, 0.10), t * 2.0 - 1.0),
             abs(t * 2.0 - 1.0));
}

void main() {
  vec3 c = ramp(v_bold);
  if (v_active < 0.5) c = mix(c, vec3(0.4), 0.85);  // gray out masked-off networks
  gl_FragColor = vec4(c, 1.0);
}
```

## Deliverables

1. New endpoint returning a single packed binary the client can `fetch()` once and
   upload as a Float texture (~8 MB for a 50s scan).
2. Single-pass render — no draw call per vertex.
3. The scrubber drives `t_current` directly — animation is GPU-side, no JS frame work.
4. Click-to-inspect resolves vertex_id → Schaefer parcel via the `vertex_to_parcel`
   array, then opens the existing sidebar with that parcel's metadata.

## Risk + fallback

- WebGL2 required for `texelFetch` and integer bitwise. Already a hard dep
  (Three.js r170+). If a judge runs the demo on iOS Safari (WebGL1), we
  fall back to the existing 50-marker code via a feature flag.
- Mesh integrity: `brain_fsaverage5.glb` (984 KB) must already have
  per-vertex `vertexId` as an attribute. If not, we generate it in a
  one-time preprocess pass on first viewer load and cache to localStorage.

## ETA

~3-4 hours of focused work. Mostly main.js edits + one server endpoint +
one preprocess script. Mesh loading + raycaster code is reused from the
existing viewer; only the color path is new.

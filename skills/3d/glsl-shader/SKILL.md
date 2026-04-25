---
name: glsl-shader
description: Write and explain GLSL fragment + vertex shaders for Three.js / R3F. Use when the user wants a custom material, a procedural pattern, a post-processing effect, or to understand an existing `.glsl` file.
version: 1.0.0
author: Mercury
license: MIT
metadata:
  hermes:
    tags: [GLSL, shaders, fragment, vertex, three.js, R3F, WebGL]
    category: creative
    related_skills: [three-js-component, three-js-debug]
---

# GLSL Shader Writing for Three.js

Three.js targets WebGL 2 (GLSL ES 3.00).  Three injects a chunk system
via `#include <...>` and predefines a handful of attributes / uniforms
the user shouldn't redeclare.

## When to Use

- "Write me a shader that does X"
- "How do I make a custom material that pulses / glows / transitions"
- "Explain this `.glsl` snippet"
- Post-processing effects beyond what `@react-three/postprocessing` ships

## 1. Minimum viable `ShaderMaterial`

```tsx
import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { ShaderMaterial } from "three";

const vertex = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragment = /* glsl */ `
  uniform float uTime;
  varying vec2 vUv;
  void main() {
    vec3 col = 0.5 + 0.5 * cos(uTime + vUv.xyx + vec3(0.0, 2.0, 4.0));
    gl_FragColor = vec4(col, 1.0);
  }
`;

function PulseMaterial() {
  const ref = useRef<ShaderMaterial>(null!);
  useFrame(({ clock }) => { ref.current.uniforms.uTime.value = clock.getElapsedTime(); });
  return (
    <shaderMaterial
      ref={ref}
      vertexShader={vertex}
      fragmentShader={fragment}
      uniforms={{ uTime: { value: 0 } }}
    />
  );
}
```

The `/* glsl */` template-literal comment is a hint to GLSL syntax
plugins (VS Code, JetBrains) — strictly cosmetic but worth keeping.

## 2. Predefined Three.js inputs (don't redeclare)

In **vertex shaders**:

| Name | Type | What |
|---|---|---|
| `position` | `attribute vec3` | Per-vertex position in object space |
| `normal` | `attribute vec3` | Per-vertex normal |
| `uv` | `attribute vec2` | Per-vertex UV coords |
| `modelMatrix` | `uniform mat4` | Object → world |
| `viewMatrix` | `uniform mat4` | World → camera |
| `projectionMatrix` | `uniform mat4` | Camera → clip |
| `modelViewMatrix` | `uniform mat4` | Object → camera (combined) |
| `cameraPosition` | `uniform vec3` | Camera world position |

In **fragment shaders**:

| Name | Type | What |
|---|---|---|
| `gl_FragCoord` | `vec4` | Screen pixel coord |
| `gl_FragColor` | `out vec4` | Final colour (set this) |

Anything you `varying` from vertex must be declared identically in the
fragment shader.

## 3. Common patterns

### Time-based pulse / glow

```glsl
float pulse = 0.5 + 0.5 * sin(uTime * 2.0);
gl_FragColor = vec4(baseColor * pulse, 1.0);
```

### Edge / fresnel for activation overlays (great for cortex)

```glsl
varying vec3 vNormal;
varying vec3 vViewPosition;
void main() {
  vec3 n = normalize(vNormal);
  vec3 v = normalize(vViewPosition);
  float fresnel = pow(1.0 - dot(n, v), 3.0);
  gl_FragColor = vec4(activationColor * fresnel, 1.0);
}
```

### Hot-cold colormap (use for fMRI / brain activation)

```glsl
vec3 hotCold(float v) {
  float t = clamp(v, 0.0, 1.0);
  vec3 cold = vec3(0.05, 0.15, 0.55);   // deep blue
  vec3 hot  = vec3(1.00, 0.65, 0.10);   // amber
  return mix(cold, hot, t);
}
```

### Noise (Inigo Quilez classic)

```glsl
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i),               hash(i + vec2(1.0, 0.0)), u.x),
             mix(hash(i + vec2(0.0,1)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
```

## 4. Wiring a per-vertex attribute (e.g. activation)

```tsx
const geom = new BufferGeometry();
geom.setAttribute("position", new BufferAttribute(positions, 3));
geom.setAttribute("activation", new BufferAttribute(activations, 1));
```

Vertex shader:

```glsl
attribute float activation;
varying float vActivation;
void main() {
  vActivation = activation;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
```

Fragment shader:

```glsl
varying float vActivation;
void main() {
  gl_FragColor = vec4(hotCold(vActivation), 1.0);
}
```

## 5. Verification

After editing a shader:

1. Save and let HMR rebuild.  If the shader fails to compile, Three
   logs `THREE.WebGLProgram: shader error: ...` to the DevTools
   console.  Read the line/column from the GLSL source to find the bug.
2. The first frame after a successful compile draws a mesh.  If you see
   a flash of pink / magenta, that's the WebGL "default broken material"
   — the shader compiled but something is undefined.
3. On a phone, test that GLSL ES 3.00 features (e.g. `texture()` not
   `texture2D()`) work — older Android WebGL drivers are flaky.

## Pitfalls

1. Three's chunk system is opt-in via `#include <common>` etc.  If you
   `#include` something but don't use the symbols it expects, you'll
   get a "X redefined" error.  Either include nothing or include and
   use.
2. WebGL 1 vs WebGL 2 syntax differs.  Three picks based on context;
   in WebGL 2, use `out vec4 fragColor` instead of `gl_FragColor`.
3. `precision highp float;` is the safe default but isn't always
   supported on mobile.  Switch to `mediump` if mobile shows banding.
4. Uniforms passed from JS must match the GLSL declaration exactly —
   `vec3` in GLSL needs a `THREE.Vector3` or `[r,g,b]` from JS.
5. R3F drops uniforms on remount.  Persist via `useMemo` over the
   `uniforms` object so HMR doesn't reset values to 0.

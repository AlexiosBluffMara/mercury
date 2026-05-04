---
name: three-js-debug
description: Diagnose Three.js / R3F bugs — blank canvas, wrong materials, missing lighting, broken animations, performance regressions, model-loading failures. Use when the user pastes a Three.js component that "doesn't work" or shows an empty canvas.
version: 1.0.0
author: Mercury
license: MIT
metadata:
  mercury:
    tags: [3D, three.js, react-three-fiber, R3F, debugging, GLSL, WebGL]
    category: creative
    related_skills: [three-js-component, glsl-shader]
---

# Three.js / R3F Debugging Checklist

Three.js fails silently more often than not.  Walk this list in order
before suggesting code changes.

## 1. Blank canvas — most common causes

| Symptom | Likely cause | Fix |
|---|---|---|
| Pure black or transparent canvas | Parent `<div>` has no height | Wrap `<Canvas>` in `h-screen` / `h-[60vh]` / explicit `style={{ height: 480 }}` |
| Canvas renders but mesh invisible | No light source (`meshStandardMaterial` needs lights) | Add `<ambientLight />` + `<directionalLight />`, or switch to `meshBasicMaterial` |
| Mesh visible but black | Material at `metalness=1, roughness=0` with no env map | Add `<Environment preset="city" />` from `@react-three/drei` |
| Camera inside the mesh | Default camera at `(0,0,0)`, mesh at `(0,0,0)` | Move camera: `<Canvas camera={{ position: [3, 2, 5] }}>` |
| Mesh way too small or huge | Wrong unit scale on imported model | Wrap in `<group scale={0.01}>` or 100, depending on direction |

## 2. Wrong materials / colors

- `meshBasicMaterial` ignores lights entirely — useful for HUD elements,
  wrong for "why is my object solid white".
- `meshStandardMaterial` and `meshPhysicalMaterial` need at least one
  non-ambient light.  Pure ambient looks flat and undefined.
- `color="red"` is fine but mixed with `metalness=1` produces a saturated
  chrome — usually you want `metalness=0.2-0.5, roughness=0.4-0.7`.
- Imported GLBs sometimes ship with `material.colorSpace = NoColorSpace`.
  Set `THREE.SRGBColorSpace` after load if colors look washed out.

## 3. Animation not running

- `useFrame` must be inside `<Canvas>` subtree.  Outside → silent no-op.
- If you mutate React state inside `useFrame`, you're rerendering on
  every frame — switch to `useRef` and mutate `ref.current.rotation`
  directly.
- `frameloop="demand"` (set on `<Canvas>`) means the scene only redraws
  when state changes — a `useFrame` mutation alone won't trigger a
  redraw.  Either drop `demand` or call `invalidate()` from `useThree`.

## 4. Model loading failures

```tsx
import { useGLTF } from "@react-three/drei";
import { Suspense } from "react";

<Canvas>
  <Suspense fallback={null}>
    <Model url="/models/brain.glb" />
  </Suspense>
</Canvas>
```

- DevTools Network tab → confirm the GLB is `200 OK`, not `404` (Vite
  serves from `public/`, not `src/`).
- DevTools Console → look for `THREE.GLTFLoader: Couldn't load asset`.
- `useGLTF` throws a Promise the first call — without `<Suspense>`
  React 19 surfaces it as an unhandled rejection.

## 5. Performance

Open DevTools → Performance tab, record 5 seconds.

| Symptom | Cause | Fix |
|---|---|---|
| Scene drops below 30 fps on a phone | DPR too high | `<Canvas dpr={[1, 1.5]}>` |
| 100% GPU even when idle | `frameloop="always"` (default) on a static scene | `frameloop="demand"` |
| Big stalls on first paint | Loading a large GLB synchronously | Wrap in `<Suspense>` and call `useGLTF.preload(url)` |
| Memory grows unbounded | Geometries / materials not disposed when component unmounts | Use refs with `useEffect` cleanup: `geom.dispose()`, `mat.dispose()` |

## 6. Verification

Run the dev server, navigate to the page, and check:

```text
DevTools Console → no warnings
DevTools Sources → no failed asset loads
DevTools Performance → ≥30 fps in record mode
DevTools "Three.js" tab (if Three.js DevTools extension installed) → scene graph populated
```

Mobile sanity: DevTools responsive mode at 375×812.  The canvas should
fit, respond to touch, and not lock the scroll on the parent page.

## Pitfalls

1. Don't pass `THREE` constructors with capital letters — `<Mesh />`
   compiles to nothing in R3F.  Always lowercase.
2. `OrbitControls` from drei conflicts with native page scroll on
   mobile.  Set `enablePan={false}` and the page can still scroll past
   the canvas with two-finger swipe outside.
3. `<Canvas>` inside a parent that uses `transform: scale(...)` will
   blur — use `transform: none` on the wrapper for crisp output.
4. R3F's `<color attach="background" args={["#0c1117"]} />` only works
   inside `<Canvas>`, not on the surrounding div.

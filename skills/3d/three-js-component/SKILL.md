---
name: three-js-component
description: Generate Three.js + React Three Fiber (R3F) components from a description. Use when the user asks for a 3D scene, a `<Canvas>` component, a procedural geometry, a custom mesh, or any browser 3D visualisation. Prefer R3F over raw Three.js boilerplate unless the user explicitly asks for vanilla Three.
version: 1.0.0
author: Mercury
license: MIT
metadata:
  mercury:
    tags: [3D, three.js, react-three-fiber, R3F, GLSL, WebGL, visualization]
    category: creative
    related_skills: [three-js-debug, glsl-shader, cortex-bridge]
prerequisites:
  packages:
    - three
    - "@react-three/fiber"
    - "@react-three/drei"
---

# Three.js + R3F Component Generator

Mercury ships React 19 + Vite + R3F + Three 0.180 in `mercury-web/`, and
Cortex's webapp uses the same stack.  Default to R3F — it's terser, plays
well with React state, and avoids manual `requestAnimationFrame` loops.

## When to Use

- "Make a 3D viewer for X"
- "Add a rotating cube / mesh / shader to the dashboard"
- "Render this brain scan / point cloud / geometry"
- Anything that produces a `<Canvas>` or `Scene` block

## 1. Minimum viable R3F scene

```tsx
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Environment } from "@react-three/drei";

export function Scene() {
  return (
    <Canvas camera={{ position: [3, 2, 5], fov: 50 }}>
      <ambientLight intensity={0.4} />
      <directionalLight position={[5, 5, 5]} intensity={1.2} />
      <mesh>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial color="silver" metalness={0.6} roughness={0.3} />
      </mesh>
      <OrbitControls enableDamping />
      <Environment preset="city" />
    </Canvas>
  );
}
```

The `<Canvas>` autoresizes to its parent — wrap it in a div with explicit
height (`h-screen`, `h-[60vh]`, etc.) or it'll collapse to 0px.

## 2. Animating with `useFrame`

```tsx
import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh } from "three";

function Spinner() {
  const ref = useRef<Mesh>(null!);
  useFrame((_, dt) => { ref.current.rotation.y += dt * 0.5; });
  return (
    <mesh ref={ref}>
      <torusKnotGeometry args={[1, 0.3, 128, 32]} />
      <meshStandardMaterial color="#88ccff" />
    </mesh>
  );
}
```

`useFrame` only runs while the component is mounted inside `<Canvas>`.
Don't import it elsewhere or it throws "R3F: useFrame is not supported
outside of a Canvas".

## 3. Loading models (GLTF / GLB)

```tsx
import { useGLTF } from "@react-three/drei";

function Model({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} />;
}

useGLTF.preload("/models/brain.glb");
```

Put models under `mercury-web/public/models/` so Vite serves them
statically.

## 4. Brain-scan-shaped data

For Cortex output (20,484-vertex BOLD prediction tensors), convert to a
`BufferGeometry` with `Float32Array` positions:

```tsx
import { BufferGeometry, BufferAttribute, Points, PointsMaterial } from "three";

function VertexCloud({ positions, activations }: {
  positions: Float32Array;       // length = vertices * 3
  activations: Float32Array;     // length = vertices, normalised 0-1
}) {
  const geom = useMemo(() => {
    const g = new BufferGeometry();
    g.setAttribute("position", new BufferAttribute(positions, 3));
    g.setAttribute("activation", new BufferAttribute(activations, 1));
    return g;
  }, [positions, activations]);
  return (
    <points geometry={geom}>
      <pointsMaterial vertexColors size={0.01} sizeAttenuation />
    </points>
  );
}
```

## 5. Performance tips

- Wrap heavy components in `<Suspense fallback={null}>`.
- Use `<PerformanceMonitor>` from drei to step down quality on slow GPUs.
- Avoid React state inside `useFrame` — mutate refs directly.
- Set `dpr={[1, 1.5]}` on `<Canvas>` to cap retina cost on phones.
- `frameloop="demand"` redraws only on state change (great for static viewers).

## Verification

Before reporting "done":

1. `cd mercury-web && npm run build` — must compile cleanly.
2. `npm run dev` — open the page in the browser, the canvas should
   render without warnings in the DevTools console.
3. On mobile (DevTools responsive mode at 375×812), the canvas should
   not push the page out of bounds and should respond to touch drag if
   `OrbitControls` are mounted.

## Pitfalls

1. `<Canvas>` with no parent height → 0px tall scene.  Always wrap in a
   sized container.
2. R3F lowercase JSX maps directly to Three constructors — `<mesh>` not
   `<Mesh>`.  Capitalising compiles but renders nothing.
3. Loading large GLBs synchronously blocks the first paint.  Use
   `<Suspense>` + a loader fallback.
4. `metalness=1, roughness=0` looks like a chrome ball with no detail
   unless an environment map is mounted.
5. `fov` larger than 70 produces fisheye distortion that reads as a bug
   on flat geometry.  Stay around 45–55.

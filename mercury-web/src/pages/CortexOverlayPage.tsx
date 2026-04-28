import { Suspense, useEffect, useMemo, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Cortex } from "@/components/fmri-overlay/cortex-overlay";
import type { Colormap } from "@/components/fmri-overlay/colormaps";

// R3F's auto-resize observer doesn't fire inside Mercury's app shell on this
// build — the canvas stays at the HTML default 300×150.  We pin it every
// frame to a known-good size + camera aspect, and slowly auto-rotate the
// brain so it's clearly visible without an OrbitControls dep.
function PinSizeAndSpin({ width, height }: { width: number; height: number }) {
  const { gl, camera, scene } = useThree();
  useEffect(() => {
    gl.setSize(width, height, true);
    if (camera instanceof Object && "aspect" in camera) {
      (camera as THREE_PerspectiveCamera).aspect = width / height;
      (camera as THREE_PerspectiveCamera).updateProjectionMatrix();
    }
  }, [gl, camera, width, height]);
  useFrame((_, dt) => {
    // Spin the whole scene about Y so the brain is obviously rotating
    scene.rotation.y += dt * 0.4;
  });
  return null;
}
type THREE_PerspectiveCamera = { aspect: number; updateProjectionMatrix: () => void; isPerspectiveCamera: boolean };

const N_VERTS = 20484;
const N_T     = 100;

// Generate a deterministic synthetic BOLD trace shaped like TRIBE v2 output:
//   shape [100, 20484], z-scored floats. Two slow sinusoids out-of-phase
//   across the cortex give a pleasing pulse without being noise.
function buildSyntheticTrace(): Float32Array {
  const out = new Float32Array(N_T * N_VERTS);
  for (let t = 0; t < N_T; t++) {
    const phase = (t / N_T) * Math.PI * 4;
    for (let v = 0; v < N_VERTS; v++) {
      const a = Math.sin(v * 0.00073 + phase);
      const b = Math.cos(v * 0.00031 - phase * 0.6);
      out[t * N_VERTS + v] = 1.6 * a * b;
    }
  }
  return out;
}

export default function CortexOverlayPage() {
  const trace = useMemo(buildSyntheticTrace, []);
  const [colormap, setColormap] = useState<Colormap>("rdbu");
  const [playing,  setPlaying]  = useState(true);
  const [time,     setTime]     = useState<number | undefined>(undefined);

  useEffect(() => { document.title = "Mercury — Cortex Overlay"; }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", padding: 16, gap: 12 }}>
      <header>
        <h1 style={{ margin: 0, fontSize: 20 }}>Cortex Overlay — <code>fmri-overlay</code> skill demo</h1>
        <p style={{ margin: "4px 0 0", opacity: 0.7, fontSize: 13 }}>
          Three.js render of a synthetic BOLD trace shaped like TRIBE v2 output
          ({N_T} timepoints × {N_VERTS} vertices). Real TRIBE output drops in by
          replacing <code>buildSyntheticTrace()</code> with the API call.
        </p>
      </header>

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <label>Colormap:</label>
        {(["rdbu", "viridis", "hot"] as Colormap[]).map(c => (
          <button
            key={c}
            onClick={() => setColormap(c)}
            style={{
              padding: "4px 10px",
              border:  c === colormap ? "1px solid #888" : "1px solid #333",
              background: c === colormap ? "#1a1a1a" : "transparent",
              color: "inherit",
              cursor: "pointer",
            }}
          >{c}</button>
        ))}
        <span style={{ width: 16 }} />
        <button
          onClick={() => setPlaying(p => !p)}
          style={{ padding: "4px 10px", border: "1px solid #444", background: "transparent", color: "inherit", cursor: "pointer" }}
        >{playing ? "Pause" : "Play"}</button>
        <button
          onClick={() => { setTime(0); setPlaying(true); }}
          style={{ padding: "4px 10px", border: "1px solid #444", background: "transparent", color: "inherit", cursor: "pointer" }}
        >Restart</button>
      </div>

      <div style={{ position: "relative", width: 300, height: 150, border: "1px solid #2a2a2a", borderRadius: 6, overflow: "hidden", background: "#0a0a0a" }}>
        <Canvas
          camera={{ position: [0, 0, 4], fov: 35 }}
          style={{ width: 300, height: 150, display: "block" }}
          gl={{ antialias: true }}
          dpr={[1, 2]}
        >
          <ambientLight intensity={0.5} />
          <directionalLight position={[100, 100, 100]} intensity={0.7} />
          <directionalLight position={[-100, -50, -50]} intensity={0.3} />
          <Suspense fallback={null}>
            <Cortex
              trace={trace}
              fps={2}
              colormap={colormap}
              playing={playing}
              time={time}
              meshUrl="/data/fsaverage5_pial.glb"
              range={[-2.5, 2.5]}
            />
          </Suspense>
          <PinSizeAndSpin width={300} height={150} />
        </Canvas>
      </div>

      <footer style={{ fontSize: 12, opacity: 0.6 }}>
        20,484-vertex fsaverage5 mesh · {N_T} timepoints @ 2 Hz · range ±2.5 z ·
        BOLD scalar packed as a Data3DTexture, sampled in the vertex shader,
        mapped through a 256-entry RGBA LUT in the fragment shader.
      </footer>
    </div>
  );
}

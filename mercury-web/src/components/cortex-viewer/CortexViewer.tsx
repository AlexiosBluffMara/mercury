// Vanilla three.js cortex viewer.  Avoids React Three Fiber entirely so we
// own the canvas, the resize observer, the render loop, and disposal —
// R3F's auto-resize doesn't fire reliably inside Mercury's app shell.
//
// Public surface mirrors the fmri-overlay skill contract: take a BOLD
// trace [n_t, 20484], a colormap, an optional time/playing override, and
// render the activation onto an fsaverage5 mesh with our custom GLSL3
// shaders.  The component manages its own renderer + scene + camera, and
// disposes everything cleanly on unmount.

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { colormapLUT, type Colormap } from "@/components/fmri-overlay/colormaps";
import { cortexVertexShader, cortexFragmentShader } from "@/components/fmri-overlay/shaders";

export interface CortexViewerProps {
  /** Real BOLD trace [nT*20484].  Optional — when absent or `demo` is true,
   *  the shader synthesises a spatially-coherent activation from vertex
   *  positions + time.  Drop in real TRIBE v2 output to switch to live data. */
  trace?:    Float32Array;
  nT?:       number;
  fps?:      number;                // default 2 (TRIBE v2 native)
  colormap?: Colormap;              // default "rdbu"
  range?:    [number, number];      // colormap z-range, default [-2.5, 2.5]
  meshUrl?:  string;
  playing?:  boolean;
  /** Force demo (synthetic) activation. Default true if `trace` is absent. */
  demo?:     boolean;
  /** Auto-rotate the brain (degrees/sec). 0 disables. Default 12. */
  spinRate?: number;
}

const FSAVERAGE5_VERTS = 20484;

export function CortexViewer(props: CortexViewerProps): JSX.Element {
  const {
    trace,
    nT       = trace ? trace.length / FSAVERAGE5_VERTS : 100,
    fps      = 2,
    colormap = "rdbu",
    range    = [-2.5, 2.5],
    meshUrl  = "/data/fsaverage5_pial.glb",
    playing  = true,
    demo     = !trace,
    spinRate = 12,
  } = props;

  const containerRef = useRef<HTMLDivElement>(null);
  const stateRef     = useRef<{
    renderer:  THREE.WebGLRenderer;
    scene:     THREE.Scene;
    camera:    THREE.PerspectiveCamera;
    controls:  OrbitControls;
    material?: THREE.ShaderMaterial;
    cortex?:   THREE.Mesh;
    raf:       number;
    ro:        ResizeObserver;
    disposed:  boolean;
  } | null>(null);

  const playingRef = useRef(playing);
  const spinRef    = useRef(spinRate);
  useEffect(() => { playingRef.current = playing;  }, [playing]);
  useEffect(() => { spinRef.current    = spinRate; }, [spinRate]);

  // ── Mount: set up renderer + scene + camera + load mesh ────────────────────
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene    = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0a);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    container.appendChild(renderer.domElement);

    // Camera with sensible default for a 2-unit brain
    const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 100);
    camera.position.set(0, 0.6, 4.6);

    // Soft fill lighting (mostly cosmetic — shader self-colours via LUT)
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dl = new THREE.DirectionalLight(0xffffff, 0.5);
    dl.position.set(2, 3, 4);
    scene.add(dl);

    // OrbitControls — drag/scroll to inspect, no need for drei
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping  = true;
    controls.dampingFactor  = 0.06;
    controls.rotateSpeed    = 0.6;
    controls.minDistance    = 2.6;
    controls.maxDistance    = 9;

    // Resize observer — owns canvas dimensions ourselves so we never get
    // stuck at the HTML default 300×150.
    const ro = new ResizeObserver((entries) => {
      const e = entries[0];
      if (!e) return;
      const { width, height } = e.contentRect;
      const w = Math.max(1, Math.round(width));
      const h = Math.max(1, Math.round(height));
      renderer.setSize(w, h, true);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    });
    ro.observe(container);

    const state = stateRef.current = {
      renderer, scene, camera, controls,
      raf: 0, ro, disposed: false,
    };

    // Load the cortex mesh asynchronously, then attach the ShaderMaterial
    new GLTFLoader().load(
      meshUrl,
      (gltf) => {
        if (state.disposed) return;
        let geom: THREE.BufferGeometry | null = null;
        gltf.scene.traverse((o) => {
          if (!geom && (o as THREE.Mesh).isMesh) geom = (o as THREE.Mesh).geometry as THREE.BufferGeometry;
        });
        if (!geom) { console.error("[CortexViewer] no Mesh in GLB"); return; }
        geom.computeVertexNormals();

        const boldTex = makeBoldTexture(trace ?? new Float32Array(FSAVERAGE5_VERTS), nT);
        const lutTex  = makeLutTexture(colormap);
        const material = new THREE.ShaderMaterial({
          uniforms: {
            uBoldTex: { value: boldTex },
            uLut:     { value: lutTex },
            uTime:    { value: 0 },
            uFps:     { value: fps },
            uNT:      { value: nT },
            uRange:   { value: new THREE.Vector2(range[0], range[1]) },
            uDemo:    { value: demo },
          },
          vertexShader:   cortexVertexShader,
          fragmentShader: cortexFragmentShader,
          glslVersion:    THREE.GLSL3,
        });
        const cortex = new THREE.Mesh(geom, material);
        scene.add(cortex);
        state.cortex   = cortex;
        state.material = material;
      },
      undefined,
      (err) => console.error("[CortexViewer] GLB load failed:", err),
    );

    // Render loop
    const t0 = performance.now();
    let prevTime = t0;
    let traceTime = 0;
    const tick = (nowMs: number) => {
      if (state.disposed) return;
      state.raf = requestAnimationFrame(tick);
      const dt = (nowMs - prevTime) / 1000;
      prevTime = nowMs;

      controls.update();

      if (state.cortex && spinRef.current !== 0) {
        state.cortex.rotation.y += (spinRef.current * Math.PI / 180) * dt;
      }
      if (state.material && playingRef.current) {
        traceTime += dt;
        // Loop the trace seamlessly
        const total = nT / fps;
        if (total > 0) traceTime = traceTime % total;
        state.material.uniforms.uTime.value = traceTime;
      }

      renderer.render(scene, camera);
    };
    state.raf = requestAnimationFrame(tick);

    // ── Cleanup ───────────────────────────────────────────────────────────────
    return () => {
      state.disposed = true;
      cancelAnimationFrame(state.raf);
      ro.disconnect();
      controls.dispose();
      if (state.material) {
        const u = state.material.uniforms;
        (u.uBoldTex.value as THREE.Texture | null)?.dispose();
        (u.uLut.value as THREE.Texture | null)?.dispose();
        state.material.dispose();
      }
      if (state.cortex) {
        state.cortex.geometry.dispose();
      }
      renderer.dispose();
      if (renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement);
      }
    };
    // We intentionally do NOT depend on `trace` / `colormap` / `range` here —
    // those are hot-swapped via the dedicated effects below so we don't tear
    // down the WebGL context every prop change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meshUrl, fps, nT]);

  // Hot-swap the trace texture without rebuilding the renderer
  useEffect(() => {
    const m = stateRef.current?.material;
    if (!m) return;
    if (!trace) return;                                     // demo mode skips
    const old = m.uniforms.uBoldTex.value as THREE.Texture | undefined;
    const next = makeBoldTexture(trace, nT);
    m.uniforms.uBoldTex.value = next;
    old?.dispose();
  }, [trace, nT]);

  // Hot-swap demo flag
  useEffect(() => {
    const m = stateRef.current?.material;
    if (!m) return;
    m.uniforms.uDemo.value = demo;
  }, [demo]);

  // Hot-swap the colormap LUT
  useEffect(() => {
    const m = stateRef.current?.material;
    if (!m) return;
    const old = m.uniforms.uLut.value as THREE.Texture | undefined;
    m.uniforms.uLut.value = makeLutTexture(colormap);
    old?.dispose();
  }, [colormap]);

  // Hot-swap the colormap range
  useEffect(() => {
    const m = stateRef.current?.material;
    if (!m) return;
    (m.uniforms.uRange.value as THREE.Vector2).set(range[0], range[1]);
  }, [range]);

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width:    "100%",
        height:   "100%",
        minHeight: 360,
        cursor:   "grab",
        background: "#0a0a0a",
      }}
    />
  );
}

// ── helpers ────────────────────────────────────────────────────────────────────

function makeBoldTexture(trace: Float32Array, nT: number): THREE.Data3DTexture {
  const tex = new THREE.Data3DTexture(trace, FSAVERAGE5_VERTS, 1, nT);
  tex.format     = THREE.RedFormat;
  tex.type       = THREE.FloatType;
  tex.minFilter  = THREE.LinearFilter;
  tex.magFilter  = THREE.LinearFilter;
  tex.wrapS      = THREE.ClampToEdgeWrapping;
  tex.wrapT      = THREE.ClampToEdgeWrapping;
  tex.wrapR      = THREE.ClampToEdgeWrapping;
  tex.needsUpdate = true;
  return tex;
}

function makeLutTexture(name: Colormap): THREE.DataTexture {
  const tex = new THREE.DataTexture(
    colormapLUT(name), 256, 1, THREE.RGBAFormat, THREE.UnsignedByteType,
  );
  tex.minFilter  = THREE.LinearFilter;
  tex.magFilter  = THREE.LinearFilter;
  tex.wrapS      = THREE.ClampToEdgeWrapping;
  tex.wrapT      = THREE.ClampToEdgeWrapping;
  tex.needsUpdate = true;
  return tex;
}

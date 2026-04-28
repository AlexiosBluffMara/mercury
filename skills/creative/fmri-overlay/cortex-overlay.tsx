import { useEffect, useMemo, useRef, useState, type JSX } from "react";
import { useFrame, useLoader } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { colormapLUT, type Colormap } from "./colormaps";
import { cortexVertexShader, cortexFragmentShader } from "./shaders";

const FSAVERAGE5_VERTS = 20484;

export interface CortexProps {
  /** BOLD trace. Shape [n_t, 20484]. Required. */
  trace: Float32Array | number[][];
  /** Frames per second of the trace. Default 2 (TRIBE v2 native). */
  fps?: number;
  /** Initial colormap. Default "rdbu". */
  colormap?: Colormap;
  /** Scalar range for the colormap. Default [-3, 3] (z-score). */
  range?: [number, number];
  /** Whether the timeline is playing. Controlled when paired with `time`. */
  playing?: boolean;
  /** Wall-clock seconds offset into the trace (controlled mode). */
  time?: number;
  /** URL to the fsaverage5 pial GLB. */
  meshUrl?: string;
}

function flatten(trace: Float32Array | number[][]): { flat: Float32Array; nT: number } {
  if (trace instanceof Float32Array) {
    if (trace.length % FSAVERAGE5_VERTS !== 0) {
      throw new Error(
        `BOLD trace length ${trace.length} is not a multiple of ${FSAVERAGE5_VERTS} ` +
        `(fsaverage5 vertex count).`,
      );
    }
    return { flat: trace, nT: trace.length / FSAVERAGE5_VERTS };
  }
  const nT = trace.length;
  const flat = new Float32Array(nT * FSAVERAGE5_VERTS);
  for (let t = 0; t < nT; t++) {
    if (trace[t].length !== FSAVERAGE5_VERTS) {
      throw new Error(
        `BOLD trace timepoint ${t} has ${trace[t].length} values, expected ${FSAVERAGE5_VERTS}.`,
      );
    }
    flat.set(trace[t], t * FSAVERAGE5_VERTS);
  }
  return { flat, nT };
}

export function Cortex(props: CortexProps): JSX.Element {
  const {
    trace,
    fps = 2,
    colormap = "rdbu",
    range = [-3, 3],
    playing = true,
    time,
    meshUrl = "/data/fsaverage5_pial.glb",
  } = props;

  const gltf = useLoader(GLTFLoader, meshUrl);
  const geometry = useMemo<THREE.BufferGeometry>(() => {
    let geom: THREE.BufferGeometry | null = null;
    gltf.scene.traverse((o) => {
      if (!geom && (o as THREE.Mesh).isMesh) geom = (o as THREE.Mesh).geometry;
    });
    if (!geom) throw new Error("fsaverage5 GLB has no Mesh");
    if (geom.attributes.position.count !== FSAVERAGE5_VERTS) {
      throw new Error(
        `Mesh has ${geom.attributes.position.count} vertices, expected ${FSAVERAGE5_VERTS}.`,
      );
    }
    return geom;
  }, [gltf]);

  const { boldTex, nT } = useMemo(() => {
    const { flat, nT } = flatten(trace);
    const tex = new THREE.Data3DTexture(flat, FSAVERAGE5_VERTS, 1, nT);
    tex.format    = THREE.RedFormat;
    tex.type      = THREE.FloatType;
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    tex.wrapS = tex.wrapT = tex.wrapR = THREE.ClampToEdgeWrapping;
    tex.needsUpdate = true;
    return { boldTex: tex, nT };
  }, [trace]);

  const [activeColormap, setActiveColormap] = useState(colormap);
  useEffect(() => setActiveColormap(colormap), [colormap]);

  const lutTex = useMemo(() => {
    const lut = colormapLUT(activeColormap);
    const tex = new THREE.DataTexture(lut, 256, 1, THREE.RGBAFormat, THREE.UnsignedByteType);
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
    tex.needsUpdate = true;
    return tex;
  }, [activeColormap]);

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uBoldTex: { value: boldTex },
          uLut:     { value: lutTex },
          uTime:    { value: 0 },
          uFps:     { value: fps },
          uNT:      { value: nT },
          uRange:   { value: new THREE.Vector2(range[0], range[1]) },
        },
        vertexShader:   cortexVertexShader,
        fragmentShader: cortexFragmentShader,
        glslVersion:    THREE.GLSL3,
      }),
    // boldTex change implies a fresh material; lutTex change is hot-swappable.
    [boldTex, nT, fps],
  );

  // Hot-swap the LUT and range without rebuilding the material
  useEffect(() => { material.uniforms.uLut.value   = lutTex; }, [material, lutTex]);
  useEffect(() => { material.uniforms.uRange.value.set(range[0], range[1]); }, [material, range]);

  const localTime = useRef(0);
  useFrame((_, dt) => {
    if (typeof time === "number") {
      material.uniforms.uTime.value = time;
    } else if (playing) {
      localTime.current += dt;
      material.uniforms.uTime.value = localTime.current;
    }
  });

  // Dispose on unmount
  useEffect(
    () => () => {
      boldTex.dispose();
      lutTex.dispose();
      material.dispose();
    },
    [boldTex, lutTex, material],
  );

  return <mesh geometry={geometry} material={material} />;
}

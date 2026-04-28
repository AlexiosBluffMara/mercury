// GLSL shaders for the fmri-overlay cortex viewer.
// Vertex shader uses gl_VertexID to index a Data3DTexture of shape
// [n_t × 1 × 20484]; fragment shader maps the resulting scalar through
// a 256-entry RGBA LUT. WebGL2 only — three.js 0.180 + R3F 8 default
// to the WebGL2 renderer.

export const cortexVertexShader: string = /* glsl */ `
precision highp float;
precision highp sampler3D;

uniform sampler3D uBoldTex;
uniform float     uTime;     // wall-clock seconds into the trace
uniform float     uFps;      // trace fps (TRIBE v2 native = 2)
uniform float     uNT;       // number of timepoints in the trace
uniform vec2      uRange;    // [zMin, zMax] for normalisation in fragment

varying float vScalar;

void main() {
  // Vertex index in [0, 20484). Map to U coord in [0, 1).
  float u = (float(gl_VertexID) + 0.5) / 20484.0;
  // Time coord in [0, 1] — clamped so we don't sample outside the trace.
  float w = clamp(uTime * uFps / max(uNT - 1.0, 1.0), 0.0, 1.0);
  vScalar = texture(uBoldTex, vec3(u, 0.5, w)).r;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

export const cortexFragmentShader: string = /* glsl */ `
precision highp float;

uniform sampler2D uLut;     // 256 × 1 RGBA, sRGB
uniform vec2      uRange;   // [zMin, zMax]

varying float vScalar;

void main() {
  float t = clamp((vScalar - uRange.x) / max(uRange.y - uRange.x, 1e-6), 0.0, 1.0);
  vec4 c = texture2D(uLut, vec2(t, 0.5));
  gl_FragColor = c;
}
`;

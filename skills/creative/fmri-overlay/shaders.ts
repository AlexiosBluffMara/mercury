// GLSL shaders for the fmri-overlay cortex viewer.
// Vertex shader uses gl_VertexID to index a Data3DTexture of shape
// [n_t × 1 × 20484]; fragment shader maps the resulting scalar through
// a 256-entry RGBA LUT. WebGL2 only — three.js 0.180 + R3F 8 default
// to the WebGL2 renderer.

// GLSL 3.00 ES — paired with `glslVersion: THREE.GLSL3` on the ShaderMaterial.
// three.js auto-prepends the version directive and the standard uniforms /
// attributes (projectionMatrix, modelViewMatrix, position, normal) at the
// right scope.
//
// Two modes:
//   uDemo = true   → synthesise a spatially-coherent BOLD signal directly
//                    from the vertex position + uTime.  Always looks great,
//                    no per-vertex BOLD data needed.  Used when real TRIBE
//                    output isn't loaded yet.
//   uDemo = false  → look up the real BOLD scalar from a Data3DTexture,
//                    indexed by gl_VertexID across width and time across depth.
//
// Fragment shader is mode-agnostic — just maps vScalar through the LUT and
// applies a small bit of normal-based shading so the geometry reads.

export const cortexVertexShader: string = /* glsl */ `
precision highp float;
precision highp sampler3D;

uniform sampler3D uBoldTex;
uniform float     uTime;
uniform float     uFps;
uniform float     uNT;
uniform vec2      uRange;
uniform bool      uDemo;

out float vScalar;
out vec3  vNormal;

void main() {
  vNormal = normalize(normalMatrix * normal);

  if (uDemo) {
    // Spatially-coherent synthetic activation built from the vertex
    // position alone — three superposed bands at different frequencies
    // give a complex but smooth pattern that pulses with uTime.
    float a = sin(position.x * 5.2 + uTime * 0.9);
    float b = cos(position.y * 4.5 - uTime * 0.7);
    float c = sin(position.z * 3.7 + uTime * 1.2);
    vScalar = 1.6 * (0.55 * a * b + 0.45 * c);
  } else {
    float u = (float(gl_VertexID) + 0.5) / 20484.0;
    float w = clamp(uTime * uFps / max(uNT - 1.0, 1.0), 0.0, 1.0);
    vScalar = texture(uBoldTex, vec3(u, 0.5, w)).r;
  }

  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

export const cortexFragmentShader: string = /* glsl */ `
precision highp float;

uniform sampler2D uLut;     // 256 × 1 RGBA, sRGB
uniform vec2      uRange;   // [zMin, zMax]

in  float vScalar;
in  vec3  vNormal;
out vec4  outColor;

const vec3 LIGHT_DIR = normalize(vec3(0.4, 0.7, 1.0));

void main() {
  float t = clamp((vScalar - uRange.x) / max(uRange.y - uRange.x, 1e-6), 0.0, 1.0);
  vec4  lutSample = texture(uLut, vec2(t, 0.5));

  // Soft normal-based shading so the cortex isn't flat — keeps the geometry
  // legible without overpowering the colormap.
  float ndl    = max(dot(normalize(vNormal), LIGHT_DIR), 0.0);
  float shade  = mix(0.55, 1.05, ndl);   // ambient floor + diffuse term

  outColor = vec4(lutSample.rgb * shade, 1.0);
}
`;

// Pre-computed RGBA colormap LUTs for the fmri-overlay skill.
// Each LUT is 256 entries × 4 channels = 1024 bytes, samples linearly
// interpolated between the published stop tables below.

export type Colormap = "rdbu" | "viridis" | "hot";

type Stop = readonly [t: number, rgb: readonly [number, number, number]];

const STOPS: Record<Colormap, readonly Stop[]> = {
  rdbu: [
    [0.0,  [33,  102, 172]],
    [0.25, [103, 169, 207]],
    [0.5,  [247, 247, 247]],
    [0.75, [239, 138,  98]],
    [1.0,  [178,  24,  43]],
  ],
  viridis: [
    [0.0,  [68,    1,  84]],
    [0.25, [59,   82, 139]],
    [0.5,  [33,  144, 141]],
    [0.75, [94,  201,  98]],
    [1.0,  [253, 231,  37]],
  ],
  hot: [
    [0.0,  [10,    0,   0]],
    [0.25, [128,  10,   0]],
    [0.5,  [220,  60,   0]],
    [0.75, [255, 165,   0]],
    [1.0,  [255, 250, 200]],
  ],
};

function interp(t: number, stops: readonly Stop[]): [number, number, number] {
  if (t <= stops[0][0]) return [...stops[0][1]] as [number, number, number];
  const last = stops[stops.length - 1];
  if (t >= last[0]) return [...last[1]] as [number, number, number];
  for (let i = 0; i < stops.length - 1; i++) {
    const [t0, c0] = stops[i];
    const [t1, c1] = stops[i + 1];
    if (t >= t0 && t <= t1) {
      const u = (t - t0) / (t1 - t0);
      return [
        Math.round(c0[0] + u * (c1[0] - c0[0])),
        Math.round(c0[1] + u * (c1[1] - c0[1])),
        Math.round(c0[2] + u * (c1[2] - c0[2])),
      ];
    }
  }
  return [...last[1]] as [number, number, number];
}

export function colormapLUT(name: Colormap): Uint8Array {
  const stops = STOPS[name];
  const lut = new Uint8Array(1024);
  for (let i = 0; i < 256; i++) {
    const [r, g, b] = interp(i / 255, stops);
    const o = i * 4;
    lut[o]     = r;
    lut[o + 1] = g;
    lut[o + 2] = b;
    lut[o + 3] = 255;
  }
  return lut;
}

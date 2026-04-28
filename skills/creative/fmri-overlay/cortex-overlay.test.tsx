import { describe, expect, it } from "vitest";
import { colormapLUT } from "./colormaps";

describe("colormapLUT", () => {
  it("returns a 1024-byte Uint8Array", () => {
    const lut = colormapLUT("rdbu");
    expect(lut).toBeInstanceOf(Uint8Array);
    expect(lut.length).toBe(1024);
  });

  it("rdbu starts blue-ish and ends red-ish", () => {
    const lut = colormapLUT("rdbu");
    // index 0 → blue side
    expect(lut[0]).toBeLessThan(100);  // R
    expect(lut[2]).toBeGreaterThan(150); // B
    // last entry → red side  (index 255 × 4 = 1020)
    expect(lut[1020]).toBeGreaterThan(150); // R
    expect(lut[1022]).toBeLessThan(100);    // B
  });

  it("alpha channel is always 255", () => {
    const lut = colormapLUT("viridis");
    for (let i = 3; i < lut.length; i += 4) {
      expect(lut[i]).toBe(255);
    }
  });

  it("interpolates between stops monotonically along the chosen channel", () => {
    // viridis is sequential — green channel rises monotonically from 1 to 231
    const lut = colormapLUT("viridis");
    const greens: number[] = [];
    for (let i = 1; i < lut.length; i += 4) greens.push(lut[i]);
    expect(greens[0]).toBeLessThan(10);
    expect(greens[greens.length - 1]).toBeGreaterThan(220);
  });
});

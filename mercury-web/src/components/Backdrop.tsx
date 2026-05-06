import { useGpuTier } from "@nous-research/ui/hooks/use-gpu-tier";

/**
 * Mercury backdrop — clean RTK look.
 *
 * Originally replicated the @nous-research/ui Overlays stack (inverted JPEG
 * filler + difference blend + warm vignette + SVG noise) which gave the UI
 * a strong olive/green cast. The Red Team Kitchen brand language is much
 * simpler: near-black canvas + a subtle ISU-red radial glow at top-left,
 * optional very-low-opacity noise on capable GPUs.
 *
 * Layer stack:
 *   z-1   solid `var(--background-base)` canvas
 *   z-2   subtle ISU-red radial glow (top, low opacity)
 *   z-101 ~10% opacity SVG noise (only on GPU tier > 0)
 */
export function Backdrop() {
  const gpuTier = useGpuTier();

  return (
    <>
      {/* z-1: solid RTK canvas */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[1]"
        style={{ backgroundColor: "var(--background-base)" }}
      />

      {/* z-2: subtle ISU-red glow at top-center */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[2]"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% -20%, var(--accent-glow), transparent 60%)",
          opacity: 0.6,
        }}
      />

      {/* z-101: very subtle noise grain on capable GPUs only */}
      {gpuTier > 0 && (
        <div
          aria-hidden
          className="pointer-events-none fixed inset-0 z-[101]"
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' fill='%23ffffff' filter='url(%23n)' opacity='0.4'/%3E%3C/svg%3E\")",
            backgroundSize: "512px 512px",
            mixBlendMode: "overlay",
            opacity: "calc(0.06 * var(--noise-opacity-mul, 1))",
          }}
        />
      )}
    </>
  );
}

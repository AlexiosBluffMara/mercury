import { useEffect, useState, type CSSProperties } from "react";
import { CortexViewer } from "@/components/cortex-viewer/CortexViewer";
import type { Colormap } from "@/components/fmri-overlay/colormaps";
import narr from "@/data/cortex-narrations.json";

type Tier = "toddler" | "clinician" | "researcher";

const TIER_LABEL: Record<Tier, string> = {
  toddler:    "5-year-old",
  clinician:  "Clinician",
  researcher: "Researcher",
};

const COLORMAPS: Colormap[] = ["rdbu", "viridis", "hot"];

const COLORMAP_BLURBS: Record<Colormap, string> = {
  rdbu:    "diverging — blue ←→ red around zero. Best for signed BOLD z-scores.",
  viridis: "sequential — perceptually uniform, color-blind safe. Magnitude only.",
  hot:     "sequential — black through red to white. Pop-y, good for demos.",
};

const PANEL: CSSProperties = {
  background:    "rgba(15, 18, 22, 0.7)",
  border:        "1px solid #1f2630",
  borderRadius:  10,
  padding:       "14px 16px",
};

const PANEL_TITLE: CSSProperties = {
  margin:      "0 0 6px",
  fontSize:    11,
  letterSpacing: "0.12em",
  textTransform: "uppercase" as const,
  color:       "#9aaab8",
  fontWeight:  600,
};

const PANEL_BODY: CSSProperties = {
  margin:    0,
  fontSize:  13,
  lineHeight: 1.55,
  color:     "#d6dde3",
};

const BUTTON_BASE: CSSProperties = {
  padding:        "6px 12px",
  border:         "1px solid #2c3742",
  borderRadius:   6,
  background:     "transparent",
  color:          "#d6dde3",
  cursor:         "pointer",
  fontSize:       12,
  letterSpacing:  "0.04em",
  transition:     "border-color 120ms, background 120ms",
};

const BUTTON_ON: CSSProperties = {
  ...BUTTON_BASE,
  borderColor: "#5b8def",
  background:  "rgba(91, 141, 239, 0.14)",
  color:       "#e7eef5",
};

export default function CortexOverlayPage() {
  const [colormap, setColormap] = useState<Colormap>("rdbu");
  const [playing,  setPlaying]  = useState(true);
  const [tier,     setTier]     = useState<Tier>("toddler");
  const [zRange,   setZRange]   = useState(2.5);

  useEffect(() => { document.title = "Mercury — Cortex Overlay"; }, []);

  return (
    <div style={{
      display:        "grid",
      gridTemplateColumns: "minmax(0, 1fr) minmax(280px, 380px)",
      gap:            16,
      padding:        16,
      height:         "100%",
      minHeight:      "calc(100vh - 200px)",
      overflow:       "auto",
      color:          "#d6dde3",
      fontFamily:     "system-ui, -apple-system, Segoe UI, sans-serif",
    }}>
      {/* ── Left column: header + viewer + footer ─────────────────────────── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0, minHeight: 0 }}>
        <header style={{ flex: "0 0 auto" }}>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, color: "#f0f4f8" }}>
            Cortex Overlay
            <span style={{ marginLeft: 10, fontSize: 13, color: "#7e8b97", fontWeight: 400 }}>
              <code>fmri-overlay</code> skill · live demo
            </span>
          </h1>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "#9aaab8", lineHeight: 1.5 }}>
            {narr.intro}
          </p>
        </header>

        <div style={{
          flex: "1 1 auto",
          minHeight: 0,
          position: "relative",
          borderRadius: 10,
          overflow: "hidden",
          border: "1px solid #1f2630",
          background: "#0a0a0a",
          boxShadow: "0 0 50px rgba(0,0,0,0.6) inset",
        }}>
          <CortexViewer
            colormap={colormap}
            playing={playing}
            range={[-zRange, zRange]}
            spinRate={10}
            demo
          />
          <div style={{
            position: "absolute",
            top: 12, left: 12,
            padding: "4px 10px",
            background: "rgba(15,18,22,0.85)",
            border: "1px solid #1f2630",
            borderRadius: 999,
            fontSize: 11,
            letterSpacing: "0.08em",
            color: "#9aaab8",
            pointerEvents: "none",
          }}>
            DEMO · synthetic spatial activation · drag to orbit · scroll to zoom
          </div>
        </div>

        {/* Controls strip */}
        <div style={{
          flex: "0 0 auto",
          display: "flex",
          gap: 16,
          alignItems: "center",
          flexWrap: "wrap",
          padding: "10px 14px",
          ...PANEL,
        }}>
          <ControlGroup label="Colormap">
            {COLORMAPS.map(c => (
              <button
                key={c}
                onClick={() => setColormap(c)}
                style={c === colormap ? BUTTON_ON : BUTTON_BASE}
              >{c}</button>
            ))}
          </ControlGroup>

          <ControlGroup label="Playback">
            <button onClick={() => setPlaying(p => !p)}
                    style={playing ? BUTTON_BASE : BUTTON_ON}>
              {playing ? "Pause" : "Play"}
            </button>
          </ControlGroup>

          <ControlGroup label={`Range ±${zRange.toFixed(1)}`}>
            <input
              type="range"
              min={0.5} max={4} step={0.1}
              value={zRange}
              onChange={(e) => setZRange(Number(e.target.value))}
              style={{ accentColor: "#5b8def", width: 140 }}
            />
          </ControlGroup>

          <span style={{ marginLeft: "auto", fontSize: 11, color: "#7e8b97" }}>
            20,484 verts · 100 timepoints · 2 Hz · {COLORMAP_BLURBS[colormap]}
          </span>
        </div>
      </div>

      {/* ── Right column: scrollable panels ───────────────────────────────── */}
      <aside style={{
        display: "flex",
        flexDirection: "column",
        gap: 10,
        minHeight: 0,
        overflowY: "auto",
        paddingRight: 4,
      }}>
        <Panel title="Pipeline">{narr.pipeline}</Panel>

        <div style={PANEL}>
          <h3 style={PANEL_TITLE}>Narration</h3>
          <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
            {(["toddler", "clinician", "researcher"] as Tier[]).map(t => (
              <button
                key={t}
                onClick={() => setTier(t)}
                style={t === tier ? BUTTON_ON : BUTTON_BASE}
              >{TIER_LABEL[t]}</button>
            ))}
          </div>
          <p style={{ ...PANEL_BODY, fontStyle: tier === "toddler" ? "italic" : "normal" }}>
            {narr[tier]}
          </p>
          <p style={{ marginTop: 10, fontSize: 11, color: "#7e8b97" }}>
            Generated by <code>gemma4:26b</code> via local Ollama. Regenerate
            with <code>node scripts/generate_cortex_text.mjs</code>.
          </p>
        </div>

        <Panel title="What is BOLD?">{narr.bold}</Panel>
        <Panel title="What is TRIBE v2?">{narr.tribe}</Panel>
        <Panel title="What is fsaverage5?">{narr.fsaverage5}</Panel>
        <Panel title="Why these colors?">{narr.colormap}</Panel>

        <div style={{ ...PANEL, fontSize: 11, color: "#7e8b97" }}>
          Page is rendering a synthetic, position-driven activation pattern
          (no live TRIBE pass). Swap to real TRIBE output by pointing
          <code> CortexViewer </code> at a backend-served BOLD trace and
          setting <code>demo={"{false}"}</code>.
          <br /><br />
          Gemma is a trademark of Google LLC.
        </div>
      </aside>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={PANEL}>
      <h3 style={PANEL_TITLE}>{title}</h3>
      <p style={PANEL_BODY}>{children}</p>
    </div>
  );
}

function ControlGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <label style={{ fontSize: 10, letterSpacing: "0.1em", color: "#7e8b97", textTransform: "uppercase" }}>
        {label}
      </label>
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>{children}</div>
    </div>
  );
}

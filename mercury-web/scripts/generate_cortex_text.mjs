// Pre-generate Gemma 4 narration for the /cortex page.  Runs once at build
// time; the JSON is bundled with the app.  Ollama must be running locally
// (gemma4:26b on the 5090).  ~30s end-to-end.
//
// Usage:  node scripts/generate_cortex_text.mjs
import fs from "node:fs/promises";
import path from "node:path";

const OLLAMA_URL = process.env.OLLAMA_URL ?? "http://localhost:11434";
const MODEL      = process.env.GEMMA_MODEL ?? "gemma4:26b";
const OUT_PATH   = path.resolve("src/data/cortex-narrations.json");

const PROMPTS = {
  intro: `Write a 2-sentence introduction for a 3D brain visualization page. The page shows the predicted cortical activation (BOLD response) of a person watching a video, rendered on a 20,484-vertex fsaverage5 cortex mesh in three.js. Be warm but precise. No emoji. Don't say "imagine" or "welcome".`,

  bold: `In 60 words, explain BOLD signal in the context of fMRI. Be plain. Don't use the words "fancy" or "imagine". Mention oxygen + neural activity + the ~2-second hemodynamic delay.`,

  tribe: `In 70 words, explain what TRIBE v2 is — Meta's brain-response foundation model from the Gallant Lab at UC Berkeley. It predicts BOLD activation across 20,484 fsaverage5 vertices over 100 timepoints (50 seconds at 2Hz) given a multimodal stimulus (video, audio, text). Mention: it's a foundation model, the input is multimodal, output is per-vertex BOLD timeseries, license is CC-BY-NC.`,

  fsaverage5: `In 60 words, explain what the fsaverage5 cortex mesh is. Mention: standard FreeSurfer template, 20,484 vertices total (10,242 per hemisphere), inflated/pial variants, and that it's the canonical low-resolution mesh for neuroimaging publications. Be terse.`,

  toddler: `Imagine you're explaining what's happening in a person's brain when they watch a 20-second cat video. Speak to a 6-year-old. 50 words max. Use words like "your eyes" and "the part that helps you see". No clinical terms.`,

  clinician: `In 120 words, explain to a clinician what BOLD activation across V1, V2, MT/V5, and the superior temporal sulcus would look like in response to a 20-second cat video stimulus. Reference Brodmann areas where useful. Comment on temporal dynamics — peak ~5-6 seconds post-onset, return to baseline by ~12 seconds. Plain prose, no bullet points.`,

  researcher: `In 150 words, explain to a neuroscience researcher what TRIBE v2 predicts for a 20-second cat video stimulus. Reference: V-JEPA 2 visual encoder, wav2vec-BERT audio encoder, Llama-3.2-3B text encoder, the Glasser parcellation, expected hemodynamic response function, and which Glasser parcels (V1, V2, V3, hMT+, STSdp, FFC) typically peak. Mention intra-subject vs inter-subject variability. Plain prose.`,

  colormap: `In 50 words, explain why we use a diverging colormap (rdbu — red/white/blue) for BOLD z-scores. Mention that white = zero / no change from baseline, red = positive activation, blue = deactivation, and that the symmetry is important.`,

  pipeline: `In 70 words, describe the end-to-end pipeline that produced what you're looking at. Steps: (1) media gate via Gemma 4 E4B vision check, (2) GPU swap to TRIBE v2 on the RTX 5090, (3) TRIBE forward pass producing the BOLD timeseries, (4) GPU swap back to Gemma for narration, (5) three.js renders the BOLD on the cortex mesh. Local-only, no cloud.`,
};

async function ask(prompt) {
  const r = await fetch(`${OLLAMA_URL}/api/generate`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({
      model:   MODEL,
      prompt,
      stream:  false,
      think:   false,
      options: { temperature: 0.4, num_predict: 400 },
    }),
  });
  if (!r.ok) throw new Error(`ollama ${r.status}: ${await r.text()}`);
  const j = await r.json();
  return (j.response ?? "").trim();
}

async function main() {
  console.log(`generating with ${MODEL} via ${OLLAMA_URL}`);
  const out = {};
  for (const [k, prompt] of Object.entries(PROMPTS)) {
    process.stdout.write(`  ${k} ... `);
    const t0 = Date.now();
    out[k] = await ask(prompt);
    console.log(`${out[k].split(/\s+/).length} words (${((Date.now() - t0) / 1000).toFixed(1)}s)`);
  }
  out.__meta = {
    model:        MODEL,
    generated_at: new Date().toISOString(),
    note:         "Pre-generated narration text for the /cortex page. Regenerate by running this script — Ollama must be reachable.",
  };
  await fs.mkdir(path.dirname(OUT_PATH), { recursive: true });
  await fs.writeFile(OUT_PATH, JSON.stringify(out, null, 2), "utf-8");
  console.log(`wrote ${OUT_PATH}`);
}

main().catch(e => { console.error(e); process.exit(1); });

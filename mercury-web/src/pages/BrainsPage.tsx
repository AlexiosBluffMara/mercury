import { useEffect, useState } from "react";
import {
  Cpu,
  Sparkles,
  Eye,
  Code,
  Zap,
  HardDrive,
  Globe,
  AlertCircle,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * BrainsPage — read-only view of Mercury's dual-brain architecture.
 *
 * Mirrors mercury/copilot_models.py.  Once the FastAPI backend exposes
 * /api/mercury/brains, this page will also show the live GPU state
 * from Cortex and let the user override the routing preference.  For
 * now it renders the static catalog so the page is useful immediately.
 */

interface ModelRow {
  modelId: string;
  provider: string;
  multiplier: number;
  apiMode: string;
  vision: boolean;
  tools: boolean;
  note: string;
}

const ZERO_PREMIUM: ModelRow[] = [
  {
    modelId: "gpt-5-mini",
    provider: "copilot",
    multiplier: 0,
    apiMode: "chat_completions",
    vision: false,
    tools: true,
    note: "Default fulltime brain — newest 0x model, GPT-5 family reasoning.",
  },
  {
    modelId: "gpt-4o",
    provider: "copilot",
    multiplier: 0,
    apiMode: "chat_completions",
    vision: true,
    tools: true,
    note: "0x multimodal — vision when Gemma 4 isn't available.",
  },
  {
    modelId: "gpt-4.1",
    provider: "copilot",
    multiplier: 0,
    apiMode: "chat_completions",
    vision: false,
    tools: true,
    note: "0x backup; consistency mode when GPT-5 mini misbehaves.",
  },
];

const PARTTIME: ModelRow[] = [
  {
    modelId: "gemma4:e4b",
    provider: "ollama",
    multiplier: 0,
    apiMode: "chat_completions",
    vision: true,
    tools: false,
    note: "Local Gemma 4 E4B (~10 GB VRAM, ~196 tok/s on RTX 5090).",
  },
];

const ESCALATIONS: ModelRow[] = [
  {
    modelId: "claude-sonnet-4-6",
    provider: "copilot",
    multiplier: 1,
    apiMode: "anthropic_messages",
    vision: true,
    tools: true,
    note: "1x escalation; best for hard reasoning + long agentic chains.",
  },
  {
    modelId: "gpt-5.4",
    provider: "copilot",
    multiplier: 1,
    apiMode: "chat_completions",
    vision: false,
    tools: true,
    note: "1x escalation; OpenAI flagship code+reasoning model.",
  },
  {
    modelId: "gpt-5.3-codex",
    provider: "copilot",
    multiplier: 1,
    apiMode: "codex_responses",
    vision: false,
    tools: true,
    note: "1x escalation; LTS code-tuned model through Feb 2027.",
  },
  {
    modelId: "gemini-2.5-pro",
    provider: "vertex",
    multiplier: 1,
    apiMode: "chat_completions",
    vision: true,
    tools: true,
    note: "Long-context / multimodal escalation via Gemini Enterprise Agent Platform.",
  },
];

interface MercuryBrainsResponse {
  cortex: { state: string; available: boolean };
  tailscale: { running: boolean; hostname: string | null; magic_dns: string | null };
  preference: "auto" | "copilot" | "gemma" | "escalate";
}

function MultiplierBadge({ multiplier }: { multiplier: number }) {
  const variant =
    multiplier === 0 ? "free" : multiplier <= 1 ? "paid" : "premium";
  const label =
    multiplier === 0 ? "0x" : `${multiplier}x`;
  const colorClass =
    variant === "free"
      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
      : variant === "paid"
        ? "bg-sky-500/15 text-sky-300 border-sky-500/30"
        : "bg-amber-500/15 text-amber-300 border-amber-500/30";
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 text-[0.65rem] tracking-wider uppercase border",
        colorClass,
      )}
    >
      {label}
    </span>
  );
}

function ModelCard({ row, role }: { row: ModelRow; role?: string }) {
  return (
    <Card className="break-inside-avoid">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <CardTitle className="font-mono text-sm break-all">{row.modelId}</CardTitle>
            <CardDescription className="text-[0.7rem] uppercase tracking-wider mt-1">
              {row.provider}
              {role && <span className="ml-2 text-foreground/50">· {role}</span>}
            </CardDescription>
          </div>
          <MultiplierBadge multiplier={row.multiplier} />
        </div>
      </CardHeader>
      <CardContent className="text-xs text-midground/80 leading-relaxed">
        <p>{row.note}</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {row.vision && (
            <Badge className="text-[0.6rem]">
              <Eye className="mr-1 h-3 w-3" />vision
            </Badge>
          )}
          {row.tools && (
            <Badge className="text-[0.6rem]">
              <Code className="mr-1 h-3 w-3" />tools
            </Badge>
          )}
          <Badge className="text-[0.6rem]">{row.apiMode}</Badge>
        </div>
      </CardContent>
    </Card>
  );
}

function StatusPill({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Cpu;
  label: string;
  value: string;
  tone: "ok" | "warn" | "off";
}) {
  const toneClass =
    tone === "ok"
      ? "border-emerald-500/40 text-emerald-300"
      : tone === "warn"
        ? "border-amber-500/40 text-amber-300"
        : "border-foreground/20 text-foreground/50";
  return (
    <div
      className={cn(
        "flex min-w-0 items-center gap-2 border px-3 py-2",
        toneClass,
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <div className="min-w-0">
        <div className="text-[0.6rem] uppercase tracking-wider opacity-70">
          {label}
        </div>
        <div className="font-mono text-xs truncate">{value}</div>
      </div>
    </div>
  );
}

export default function BrainsPage() {
  const [live, setLive] = useState<MercuryBrainsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/mercury/brains");
        if (!res.ok) {
          if (res.status === 404) {
            setError("Mercury backend endpoint not yet wired");
          } else {
            setError(`HTTP ${res.status}`);
          }
          return;
        }
        const data = (await res.json()) as MercuryBrainsResponse;
        if (!cancelled) setLive(data);
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const cortexState = live?.cortex.state ?? "unknown";
  const tailscaleRunning = live?.tailscale.running ?? false;
  const tailnetName = live?.tailscale.magic_dns ?? null;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="flex-none px-4 sm:px-6 py-4 border-b border-current/10">
        <div className="flex items-center gap-2">
          <Cpu className="h-5 w-5 text-midground/80" />
          <h1 className="text-lg font-semibold tracking-wide">Brains</h1>
        </div>
        <p className="mt-1 text-xs text-midground/60">
          Mercury's dual-brain architecture and live routing state.
        </p>
      </header>

      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <section className="mb-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3">
            <StatusPill
              icon={HardDrive}
              label="Cortex GPU"
              value={cortexState}
              tone={
                cortexState === "tribe_active"
                  ? "warn"
                  : cortexState === "unavailable" || cortexState === "unknown"
                    ? "off"
                    : "ok"
              }
            />
            <StatusPill
              icon={Globe}
              label="Tailnet"
              value={tailnetName ?? (tailscaleRunning ? "running" : "off")}
              tone={tailscaleRunning ? "ok" : "off"}
            />
            <StatusPill
              icon={Sparkles}
              label="Default brain"
              value="gpt-5-mini"
              tone="ok"
            />
            <StatusPill
              icon={Zap}
              label="Routing"
              value={live?.preference ?? "auto"}
              tone="ok"
            />
          </div>
          {error && (
            <div className="mt-3 flex items-start gap-2 border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-200">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>
                Live data unavailable — {error}.  Showing the static catalog
                from <code className="font-mono">mercury/copilot_models.py</code>.
              </span>
            </div>
          )}
        </section>

        <section className="mb-6">
          <h2 className="mb-3 text-xs uppercase tracking-[0.15em] text-midground/60">
            Fulltime · 0x Premium (free on Pro+)
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {ZERO_PREMIUM.map((row, i) => (
              <ModelCard
                key={row.modelId}
                row={row}
                role={i === 0 ? "default" : i === 1 ? "vision" : "backup"}
              />
            ))}
          </div>
        </section>

        <section className="mb-6">
          <h2 className="mb-3 text-xs uppercase tracking-[0.15em] text-midground/60">
            Part-time · Local
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {PARTTIME.map((row) => (
              <ModelCard key={row.modelId} row={row} role="memory · vision · narration" />
            ))}
          </div>
        </section>

        <section className="mb-6">
          <h2 className="mb-3 text-xs uppercase tracking-[0.15em] text-midground/60">
            Escalation · 1x Premium (opt-in)
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {ESCALATIONS.map((row) => (
              <ModelCard key={row.modelId} row={row} />
            ))}
          </div>
        </section>

        <section className="text-[0.7rem] text-midground/50 border-t border-current/10 pt-4">
          <p>
            Routing rule: code/plan turns prefer Copilot, vision/quick/cortex
            prefer Gemma 4 E4B, and Gemma is dropped from candidates whenever
            Cortex's GPU scheduler reports <code className="font-mono">tribe_active</code>.
            See <code className="font-mono">mercury/router.py</code> for details.
          </p>
        </section>
      </div>
    </div>
  );
}

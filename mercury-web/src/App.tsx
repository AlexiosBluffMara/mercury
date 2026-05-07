import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import {
  Routes,
  Route,
  NavLink,
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Activity,
  BarChart3,
  BookOpen,
  ChevronDown,
  Clock,
  Code,
  Cpu,
  Database,
  Download,
  Eye,
  FileText,
  Globe,
  Heart,
  KeyRound,
  Loader2,
  MessageSquare,
  Package,
  Puzzle,
  RotateCw,
  Settings,
  Shield,
  Sparkles,
  Star,
  Terminal,
  Wrench,
  X,
  Zap,
} from "lucide-react";
import { SelectionSwitcher } from "@nous-research/ui";
import { cn } from "@/lib/utils";
import { Backdrop } from "@/components/Backdrop";
import { BottomNav } from "@/components/BottomNav";
import { SidebarFooter } from "@/components/SidebarFooter";
import { SidebarStatusStrip } from "@/components/SidebarStatusStrip";
import { PageHeaderProvider } from "@/contexts/PageHeaderProvider";
import { useSystemActions } from "@/contexts/useSystemActions";
import type { SystemAction } from "@/contexts/system-actions-context";
import { useNavVisibility, ALL_TOGGLEABLE_SECTIONS } from "@/hooks/useNavVisibility";
import type { NavSection } from "@/hooks/useNavVisibility";
import SessionsPage from "@/pages/SessionsPage";
import ChatPage from "@/pages/ChatPage";
const ConfigPage  = lazy(() => import("@/pages/ConfigPage"));
const DocsPage    = lazy(() => import("@/pages/DocsPage"));
const EnvPage     = lazy(() => import("@/pages/EnvPage"));
const LogsPage    = lazy(() => import("@/pages/LogsPage"));
const AnalyticsPage = lazy(() => import("@/pages/AnalyticsPage"));
const CronPage    = lazy(() => import("@/pages/CronPage"));
const SkillsPage  = lazy(() => import("@/pages/SkillsPage"));
const BrainsPage  = lazy(() => import("@/pages/BrainsPage"));
const CortexOverlayPage = lazy(() => import("@/pages/CortexOverlayPage"));
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { ThemeSwitcher } from "@/components/ThemeSwitcher";
import { useI18n } from "@/i18n";
import { PluginPage, PluginSlot, usePlugins } from "@/plugins";
import type { PluginManifest } from "@/plugins";
import { useTheme } from "@/themes";
import { isDashboardEmbeddedChatEnabled } from "@/lib/dashboard-flags";

function RootRedirect() {
  return <Navigate to="/sessions" replace />;
}

const CHAT_NAV_ITEM: NavItemDef = {
  path: "/chat",
  labelKey: "chat",
  label: "Chat",
  icon: Terminal,
};

const BUILTIN_ROUTES_CORE: Record<string, ComponentType> = {
  "/": RootRedirect,
  "/sessions": SessionsPage,
  "/brains": BrainsPage,
  "/cortex": CortexOverlayPage,
  "/analytics": AnalyticsPage,
  "/logs": LogsPage,
  "/cron": CronPage,
  "/skills": SkillsPage,
  "/config": ConfigPage,
  "/env": EnvPage,
  "/docs": DocsPage,
};

/** Always visible. */
const PRIMARY_NAV: NavItemDef[] = [
  { path: "/sessions", labelKey: "sessions", label: "Sessions", icon: MessageSquare },
  { path: "/brains", labelKey: "brains", label: "Brains", icon: Cpu },
  { path: "/cortex", labelKey: "cortex", label: "Cortex", icon: Sparkles },
];

/** Useful day-to-day — toggleable. */
const ACTIVITY_NAV: Array<NavItemDef & { section: NavSection }> = [
  { path: "/analytics", labelKey: "analytics", label: "Analytics", icon: BarChart3, section: "analytics" },
  { path: "/logs", labelKey: "logs", label: "Logs", icon: FileText, section: "logs" },
];

/** Admin / config — hidden by default. */
const ADMIN_NAV: Array<NavItemDef & { section: NavSection }> = [
  { path: "/cron", labelKey: "cron", label: "Cron", icon: Clock, section: "cron" },
  { path: "/skills", labelKey: "skills", label: "Skills", icon: Package, section: "skills" },
  { path: "/config", labelKey: "config", label: "Config", icon: Settings, section: "config" },
  { path: "/env", labelKey: "keys", label: "Keys", icon: KeyRound, section: "env" },
  { path: "/docs", labelKey: "documentation", label: "Docs", icon: BookOpen, section: "docs" },
];

const SECTION_LABELS: Record<NavSection, string> = {
  analytics: "Analytics",
  logs: "Logs",
  cron: "Cron",
  skills: "Skills",
  config: "Config",
  env: "Keys",
  docs: "Docs",
};

const ICON_MAP: Record<string, ComponentType<{ className?: string }>> = {
  Activity, BarChart3, Clock, FileText, KeyRound, MessageSquare,
  Package, Settings, Puzzle, Sparkles, Terminal, Globe, Database,
  Shield, Wrench, Zap, Heart, Star, Code, Eye,
};

function resolveIcon(name: string): ComponentType<{ className?: string }> {
  return ICON_MAP[name] ?? Puzzle;
}

function buildNavItems(base: NavItemDef[], manifests: PluginManifest[]): NavItemDef[] {
  const items = [...base];
  for (const manifest of manifests) {
    if (manifest.tab.override || manifest.tab.hidden) continue;
    const item: NavItemDef = { path: manifest.tab.path, label: manifest.label, icon: resolveIcon(manifest.icon) };
    const pos = manifest.tab.position ?? "end";
    if (pos === "end") items.push(item);
    else if (pos.startsWith("after:")) {
      const idx = items.findIndex((i) => i.path === "/" + pos.slice(6));
      items.splice(idx >= 0 ? idx + 1 : items.length, 0, item);
    } else if (pos.startsWith("before:")) {
      const idx = items.findIndex((i) => i.path === "/" + pos.slice(7));
      items.splice(idx >= 0 ? idx : items.length, 0, item);
    } else items.push(item);
  }
  return items;
}

function buildRoutes(
  builtinRoutes: Record<string, ComponentType>,
  manifests: PluginManifest[],
): Array<{ key: string; path: string; element: ReactNode }> {
  const byOverride = new Map<string, PluginManifest>();
  const addons: PluginManifest[] = [];
  for (const m of manifests) { if (m.tab.override) byOverride.set(m.tab.override, m); else addons.push(m); }
  const routes: Array<{ key: string; path: string; element: ReactNode }> = [];
  for (const [path, Component] of Object.entries(builtinRoutes)) {
    const om = byOverride.get(path);
    routes.push(om ? { key: `override:${om.name}`, path, element: <PluginPage name={om.name} /> }
                   : { key: `builtin:${path}`, path, element: <Component /> });
  }
  for (const m of addons) {
    if (m.tab.hidden || builtinRoutes[m.tab.path]) continue;
    routes.push({ key: `plugin:${m.name}`, path: m.tab.path, element: <PluginPage name={m.name} /> });
  }
  for (const m of manifests) {
    if (!m.tab.hidden || builtinRoutes[m.tab.path] || m.tab.override) continue;
    routes.push({ key: `plugin:hidden:${m.name}`, path: m.tab.path, element: <PluginPage name={m.name} /> });
  }
  return routes;
}

/** Collapsible section header. */
function SectionHeader({ label, expanded, onToggle }: { label: string; expanded: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={cn(
        "group flex w-full items-center gap-1 px-4 pt-3.5 pb-1",
        "text-[0.6rem] font-semibold tracking-[0.12em] uppercase",
        "text-midground/25 hover:text-midground/50 transition-colors cursor-pointer",
        "focus-visible:outline-none",
      )}
    >
      <span className="flex-1 text-left leading-none">{label}</span>
      <ChevronDown className={cn("h-2.5 w-2.5 shrink-0 transition-transform duration-200", !expanded && "-rotate-90")} />
    </button>
  );
}

/** Premium nav link row. */
function NavRow({
  path, label, labelKey, icon: Icon, onClick, t,
}: NavItemDef & { onClick: () => void; t: ReturnType<typeof useI18n>["t"] }) {
  const navLabel = labelKey ? ((t.app.nav as Record<string, string>)[labelKey] ?? label) : label;
  return (
    <li>
      <NavLink
        to={path}
        end={path === "/sessions"}
        onClick={onClick}
        className={({ isActive }) =>
          cn(
            "group relative flex items-center gap-2.5 mx-2 px-3 py-2 rounded-md",
            "text-[0.8rem] font-medium tracking-[-0.005em]",
            "whitespace-nowrap transition-all duration-150 cursor-pointer",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#CC0000]/40",
            isActive
              ? "bg-gradient-to-r from-[rgba(204,0,0,0.12)] to-[rgba(238,45,63,0.08)] text-midground shadow-[inset_0_0_0_1px_rgba(204,0,0,0.2)]"
              : "text-midground/45 hover:text-midground/80 hover:bg-white/[0.04]",
          )
        }
      >
        {({ isActive }) => (
          <>
            {/* Active left accent bar */}
            {isActive && (
              <span
                aria-hidden
                className="absolute left-0 top-1/4 bottom-1/4 w-0.5 rounded-r-full"
                style={{ background: "linear-gradient(180deg, #CC0000, #ee2d3f)", boxShadow: "0 0 6px rgba(204,0,0,0.7)" }}
              />
            )}
            <Icon className={cn("h-3.5 w-3.5 shrink-0 transition-colors", isActive ? "text-[#ff5060]" : "text-midground/40 group-hover:text-midground/70")} />
            <span className="truncate leading-none">{navLabel}</span>
          </>
        )}
      </NavLink>
    </li>
  );
}

/** Inline visibility toggle row. */
function VisibilityToggle({ label, visible, onToggle }: { label: string; visible: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="flex w-full items-center gap-3 px-4 py-1.5 text-left cursor-pointer group focus-visible:outline-none"
    >
      <span
        className={cn(
          "relative h-3.5 w-6 shrink-0 rounded-full transition-colors duration-200",
          visible ? "bg-[#CC0000]/60" : "bg-white/10",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-2.5 w-2.5 rounded-full transition-transform duration-200",
            visible ? "translate-x-2.5 bg-white" : "translate-x-0.5 bg-white/40",
          )}
        />
      </span>
      <span className="text-xs font-medium text-midground/50 group-hover:text-midground/75 transition-colors">
        {label}
      </span>
    </button>
  );
}

export default function App() {
  const { t } = useI18n();
  const { pathname } = useLocation();
  const { manifests } = usePlugins();
  const { theme } = useTheme();
  const { isVisible, toggle } = useNavVisibility();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [activityExpanded, setActivityExpanded] = useState(true);
  const [adminExpanded, setAdminExpanded] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const closeMobile = useCallback(() => setMobileOpen(false), []);

  const normalizedPath = pathname.replace(/\/$/, "") || "/";
  const isDocsRoute = normalizedPath === "/docs";
  const isChatRoute = normalizedPath === "/chat";
  const embeddedChat = isDashboardEmbeddedChatEnabled();
  const layoutVariant = theme.layoutVariant ?? "standard";

  const builtinRoutes = useMemo(
    () => ({ ...BUILTIN_ROUTES_CORE, ...(embeddedChat ? { "/chat": ChatPage } : {}) }),
    [embeddedChat],
  );
  const primaryNav = useMemo(() => (embeddedChat ? [CHAT_NAV_ITEM, ...PRIMARY_NAV] : PRIMARY_NAV), [embeddedChat]);
  const allBuiltinNav = useMemo(() => [...primaryNav, ...ACTIVITY_NAV, ...ADMIN_NAV], [primaryNav]);
  const pluginItems = useMemo(() => buildNavItems(allBuiltinNav, manifests).slice(allBuiltinNav.length), [allBuiltinNav, manifests]);
  const pluginTabMeta = useMemo(() => manifests.filter((m) => !m.tab.hidden).map((m) => ({ path: m.tab.override ?? m.tab.path, label: m.label })), [manifests]);
  const routes = useMemo(() => buildRoutes(builtinRoutes, manifests), [builtinRoutes, manifests]);
  const visibleActivity = useMemo(() => ACTIVITY_NAV.filter((i) => isVisible(i.section)), [isVisible]);
  const visibleAdmin = useMemo(() => ADMIN_NAV.filter((i) => isVisible(i.section)), [isVisible]);

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMobileOpen(false); };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
  }, [mobileOpen]);

  useEffect(() => {
    const mql = window.matchMedia("(min-width: 1024px)");
    const cb = (e: MediaQueryListEvent) => { if (e.matches) setMobileOpen(false); };
    mql.addEventListener("change", cb);
    return () => mql.removeEventListener("change", cb);
  }, []);

  return (
    <div
      data-layout-variant={layoutVariant}
      className="flex h-dvh max-h-dvh min-h-0 flex-col overflow-hidden text-midground antialiased"
      style={{ background: "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(204,0,0,0.08), transparent), #080c12" }}
    >
      <SelectionSwitcher />
      <Backdrop />
      <PluginSlot name="backdrop" />

      {mobileOpen && (
        <button
          type="button"
          aria-label={t.app.closeNavigation}
          onClick={closeMobile}
          className="lg:hidden fixed inset-0 z-40 bg-black/70 backdrop-blur-md cursor-pointer"
        />
      )}

      <PluginSlot name="header-banner" />

      <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
        {/* ── Premium Sidebar ── */}
        <aside
          id="app-sidebar"
          aria-label={t.app.navigation}
          className={cn(
            "fixed top-0 left-0 z-50 flex h-dvh max-h-dvh w-60 min-h-0 flex-col",
            "transition-transform duration-200 ease-out",
            mobileOpen ? "translate-x-0" : "-translate-x-full",
            "lg:sticky lg:top-0 lg:translate-x-0 lg:shrink-0",
          )}
          style={{
            background: "linear-gradient(180deg, rgba(10,14,22,0.98) 0%, rgba(8,11,18,0.99) 100%)",
            borderRight: "1px solid rgba(255,255,255,0.06)",
            boxShadow: "4px 0 24px rgba(0,0,0,0.4)",
          }}
        >
          {/* Brand header */}
          <div className="flex h-14 shrink-0 items-center justify-between px-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
            <div className="flex items-center gap-2.5">
              {/* Accent orb */}
              <span
                aria-hidden
                className="h-5 w-5 shrink-0 rounded-full"
                style={{
                  background: "linear-gradient(135deg, #CC0000, #ee2d3f)",
                  boxShadow: "0 0 12px rgba(204,0,0,0.5)",
                }}
              />
              <span
                className="text-[0.95rem] font-semibold tracking-tight text-midground"
                style={{ letterSpacing: "-0.02em" }}
              >
                Mercury
              </span>
            </div>
            <button
              type="button"
              onClick={closeMobile}
              className="lg:hidden h-7 w-7 flex items-center justify-center rounded-md text-midground/40 hover:text-midground/80 hover:bg-white/[0.04] transition-colors cursor-pointer focus-visible:outline-none"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <PluginSlot name="header-left" />

          {/* Nav */}
          <nav className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden py-2 scrollbar-thin" aria-label={t.app.navigation}>
            {/* Primary */}
            <ul className="flex flex-col gap-0.5 px-0 pb-1">
              {primaryNav.map((item) => (
                <NavRow key={item.path} {...item} onClick={closeMobile} t={t} />
              ))}
              {pluginItems.map((item) => (
                <NavRow key={item.path} {...item} onClick={closeMobile} t={t} />
              ))}
            </ul>

            {/* Activity */}
            {visibleActivity.length > 0 && (
              <>
                <div className="sidebar-sep" />
                <SectionHeader label="Activity" expanded={activityExpanded} onToggle={() => setActivityExpanded((v) => !v)} />
                {activityExpanded && (
                  <ul className="flex flex-col gap-0.5 mt-0.5">
                    {visibleActivity.map((item) => <NavRow key={item.path} {...item} onClick={closeMobile} t={t} />)}
                  </ul>
                )}
              </>
            )}

            {/* Admin */}
            {visibleAdmin.length > 0 && (
              <>
                <div className="sidebar-sep" />
                <SectionHeader label="Admin" expanded={adminExpanded} onToggle={() => setAdminExpanded((v) => !v)} />
                {adminExpanded && (
                  <ul className="flex flex-col gap-0.5 mt-0.5">
                    {visibleAdmin.map((item) => <NavRow key={item.path} {...item} onClick={closeMobile} t={t} />)}
                  </ul>
                )}
              </>
            )}
          </nav>

          {/* System actions */}
          <SidebarSystemActions onNavigate={closeMobile} />

          {/* Footer: settings + theme + lang */}
          <div className="shrink-0" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
            {settingsOpen && (
              <div className="py-2" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                <p className="px-4 pt-1 pb-1 text-[0.6rem] font-semibold tracking-[0.1em] uppercase text-midground/25">
                  Visible Sections
                </p>
                {ALL_TOGGLEABLE_SECTIONS.map((s) => (
                  <VisibilityToggle key={s} label={SECTION_LABELS[s]} visible={isVisible(s)} onToggle={() => toggle(s)} />
                ))}
              </div>
            )}

            <div className="flex items-center justify-between gap-2 px-3 py-2.5">
              <div className="flex items-center gap-1.5">
                <PluginSlot name="header-right" />
                <ThemeSwitcher dropUp />
                <LanguageSwitcher />
              </div>
              <button
                type="button"
                onClick={() => setSettingsOpen((v) => !v)}
                title="Toggle visible sections"
                aria-expanded={settingsOpen}
                className={cn(
                  "h-7 w-7 flex items-center justify-center rounded-md transition-all cursor-pointer focus-visible:outline-none",
                  settingsOpen
                    ? "text-[#ff5060] bg-[#CC0000]/15"
                    : "text-midground/30 hover:text-midground/60 hover:bg-white/[0.04]",
                )}
              >
                <Settings className="h-3.5 w-3.5" />
              </button>
            </div>

            <SidebarFooter />
          </div>
        </aside>

        {/* ── Main content ── */}
        <PageHeaderProvider pluginTabs={pluginTabMeta}>
          <div
            className={cn(
              "relative z-2 flex min-w-0 min-h-0 flex-1 flex-col",
              "px-3 sm:px-5 xl:px-8",
              "pb-[calc(5rem+env(safe-area-inset-bottom))] lg:pb-0",
              isChatRoute ? "pt-1 sm:pt-2 lg:pt-3" : "pt-3 sm:pt-5 lg:pt-7",
              isDocsRoute && "min-h-0 flex-1",
            )}
          >
            <PluginSlot name="pre-main" />
            <div className={cn("w-full min-w-0", (isDocsRoute || isChatRoute) && "min-h-0 flex flex-1 flex-col")}>
              <Suspense
                fallback={
                  <div className="flex h-full min-h-[40vh] items-center justify-center text-midground/40">
                    <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
                  </div>
                }
              >
                <Routes>
                  {routes.map(({ key, path, element }) => (
                    <Route key={key} path={path} element={element} />
                  ))}
                  <Route path="*" element={<Navigate to="/sessions" replace />} />
                </Routes>
              </Suspense>
            </div>
            <PluginSlot name="post-main" />
          </div>
        </PageHeaderProvider>
      </div>

      <BottomNav onMore={() => setMobileOpen(true)} showChat={embeddedChat} />
      <PluginSlot name="overlay" />
    </div>
  );
}

function SidebarSystemActions({ onNavigate }: { onNavigate: () => void }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { activeAction, isBusy, isRunning, pendingAction, runAction } = useSystemActions();

  const items: SystemActionItem[] = [
    { action: "restart", icon: RotateCw, label: t.status.restartGateway, runningLabel: t.status.restartingGateway, spin: true },
    { action: "update", icon: Download, label: t.status.updateMercury, runningLabel: t.status.updatingMercury, spin: false },
  ];

  const handleClick = (action: SystemAction) => {
    if (isBusy) return;
    void runAction(action);
    navigate("/sessions");
    onNavigate();
  };

  return (
    <div className="shrink-0 flex flex-col py-1" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
      <span className="px-4 pt-1.5 pb-0.5 text-[0.58rem] font-semibold tracking-[0.12em] uppercase text-midground/22">
        {t.app.system}
      </span>
      <SidebarStatusStrip />
      <ul className="flex flex-col gap-0.5">
        {items.map(({ action, icon: Icon, label, runningLabel, spin }) => {
          const isPending = pendingAction === action;
          const isActionRunning = activeAction === action && isRunning && !isPending;
          const busy = isPending || isActionRunning;
          const disabled = isBusy && !busy;
          return (
            <li key={action}>
              <button
                type="button"
                onClick={() => handleClick(action)}
                disabled={disabled}
                aria-busy={busy}
                className={cn(
                  "group relative flex w-full items-center gap-2.5 mx-2 px-3 py-1.5 rounded-md",
                  "text-[0.78rem] font-medium text-left whitespace-nowrap",
                  "transition-all duration-150 cursor-pointer focus-visible:outline-none",
                  busy ? "text-midground/90 bg-white/[0.03]" : "text-midground/35 hover:text-midground/65 hover:bg-white/[0.03]",
                  "disabled:cursor-not-allowed disabled:opacity-25",
                )}
              >
                {isPending ? (
                  <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
                ) : (
                  <Icon className={cn("h-3.5 w-3.5 shrink-0", isActionRunning && spin && "animate-spin", isActionRunning && !spin && "animate-pulse")} />
                )}
                <span className="truncate">{isActionRunning ? runningLabel : label}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface NavItemDef {
  icon: ComponentType<{ className?: string }>;
  label: string;
  labelKey?: string;
  path: string;
}

interface SystemActionItem {
  action: SystemAction;
  icon: ComponentType<{ className?: string }>;
  label: string;
  runningLabel: string;
  spin: boolean;
}

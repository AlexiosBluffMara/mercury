import {
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
import { SelectionSwitcher, Typography } from "@nous-research/ui";
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
import ConfigPage from "@/pages/ConfigPage";
import DocsPage from "@/pages/DocsPage";
import EnvPage from "@/pages/EnvPage";
import SessionsPage from "@/pages/SessionsPage";
import LogsPage from "@/pages/LogsPage";
import AnalyticsPage from "@/pages/AnalyticsPage";
import CronPage from "@/pages/CronPage";
import SkillsPage from "@/pages/SkillsPage";
import ChatPage from "@/pages/ChatPage";
import BrainsPage from "@/pages/BrainsPage";
import CortexOverlayPage from "@/pages/CortexOverlayPage";
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

const CHAT_NAV_ITEM: NavItem = {
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

/** Primary nav — always visible in sidebar and bottom nav. */
const PRIMARY_NAV: NavItem[] = [
  { path: "/sessions", labelKey: "sessions", label: "Sessions", icon: MessageSquare },
  { path: "/brains", labelKey: "brains", label: "Brains", icon: Cpu },
  { path: "/cortex", labelKey: "cortex", label: "Cortex", icon: Sparkles },
];

/** Activity nav — useful day-to-day but not always needed. */
const ACTIVITY_NAV: Array<NavItem & { section: NavSection }> = [
  { path: "/analytics", labelKey: "analytics", label: "Analytics", icon: BarChart3, section: "analytics" },
  { path: "/logs", labelKey: "logs", label: "Logs", icon: FileText, section: "logs" },
];

/** Admin nav — infrequent configuration pages; hidden by default. */
const ADMIN_NAV: Array<NavItem & { section: NavSection }> = [
  { path: "/cron", labelKey: "cron", label: "Cron", icon: Clock, section: "cron" },
  { path: "/skills", labelKey: "skills", label: "Skills", icon: Package, section: "skills" },
  { path: "/config", labelKey: "config", label: "Config", icon: Settings, section: "config" },
  { path: "/env", labelKey: "keys", label: "Keys", icon: KeyRound, section: "env" },
  { path: "/docs", labelKey: "documentation", label: "Docs", icon: BookOpen, section: "docs" },
];

const ICON_MAP: Record<string, ComponentType<{ className?: string }>> = {
  Activity, BarChart3, Clock, FileText, KeyRound, MessageSquare,
  Package, Settings, Puzzle, Sparkles, Terminal, Globe, Database,
  Shield, Wrench, Zap, Heart, Star, Code, Eye,
};

function resolveIcon(name: string): ComponentType<{ className?: string }> {
  return ICON_MAP[name] ?? Puzzle;
}

function buildNavItems(primaryNav: NavItem[], manifests: PluginManifest[]): NavItem[] {
  const items = [...primaryNav];
  for (const manifest of manifests) {
    if (manifest.tab.override || manifest.tab.hidden) continue;
    const pluginItem: NavItem = {
      path: manifest.tab.path,
      label: manifest.label,
      icon: resolveIcon(manifest.icon),
    };
    const pos = manifest.tab.position ?? "end";
    if (pos === "end") {
      items.push(pluginItem);
    } else if (pos.startsWith("after:")) {
      const target = "/" + pos.slice(6);
      const idx = items.findIndex((i) => i.path === target);
      items.splice(idx >= 0 ? idx + 1 : items.length, 0, pluginItem);
    } else if (pos.startsWith("before:")) {
      const target = "/" + pos.slice(7);
      const idx = items.findIndex((i) => i.path === target);
      items.splice(idx >= 0 ? idx : items.length, 0, pluginItem);
    } else {
      items.push(pluginItem);
    }
  }
  return items;
}

function buildRoutes(
  builtinRoutes: Record<string, ComponentType>,
  manifests: PluginManifest[],
): Array<{ key: string; path: string; element: ReactNode }> {
  const byOverride = new Map<string, PluginManifest>();
  const addons: PluginManifest[] = [];
  for (const m of manifests) {
    if (m.tab.override) byOverride.set(m.tab.override, m);
    else addons.push(m);
  }
  const routes: Array<{ key: string; path: string; element: ReactNode }> = [];
  for (const [path, Component] of Object.entries(builtinRoutes)) {
    const om = byOverride.get(path);
    routes.push(om
      ? { key: `override:${om.name}`, path, element: <PluginPage name={om.name} /> }
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

/** Collapsible section header for the sidebar nav groups. */
function NavGroupHeader({
  label,
  expanded,
  onToggle,
}: {
  label: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={cn(
        "group flex w-full items-center gap-1.5 px-5 pt-3 pb-0.5",
        "font-mondwest text-[0.58rem] tracking-[0.16em] uppercase",
        "text-midground/30 hover:text-midground/50 transition-colors cursor-pointer",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/30",
      )}
    >
      <span className="flex-1 text-left leading-none">{label}</span>
      <ChevronDown
        className={cn(
          "h-3 w-3 shrink-0 transition-transform duration-200",
          !expanded && "-rotate-90",
        )}
      />
    </button>
  );
}

/** Inline section visibility toggle row. */
function VisibilityToggle({
  label,
  visible,
  onToggle,
}: {
  label: string;
  visible: boolean;
  onToggle: () => void;
}) {
  return (
    <label className="flex items-center gap-2.5 px-5 py-1 cursor-pointer group">
      <div
        role="checkbox"
        aria-checked={visible}
        onClick={onToggle}
        className={cn(
          "relative h-3.5 w-6 shrink-0 rounded-full transition-colors",
          visible ? "bg-midground/60" : "bg-midground/15",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-2.5 w-2.5 rounded-full bg-background-base transition-transform",
            visible ? "translate-x-2.5" : "translate-x-0.5",
          )}
          style={{ boxShadow: "0 0 0 1px color-mix(in srgb, var(--midground-base) 30%, transparent)" }}
        />
      </div>
      <span className="font-mondwest text-[0.72rem] tracking-[0.08em] text-midground/60 group-hover:text-midground/80 transition-colors normal-case">
        {label}
      </span>
    </label>
  );
}

/** Single nav link row — shared between all groups. */
function NavItem({
  path,
  label,
  labelKey,
  icon: Icon,
  onClick,
  t,
}: NavItem & { onClick: () => void; t: ReturnType<typeof useI18n>["t"] }) {
  const navLabel = labelKey
    ? ((t.app.nav as Record<string, string>)[labelKey] ?? label)
    : label;
  return (
    <li>
      <NavLink
        to={path}
        end={path === "/sessions"}
        onClick={onClick}
        className={({ isActive }) =>
          cn(
            "group relative flex items-center gap-3",
            "px-5 py-2",
            "font-mondwest text-[0.78rem] tracking-[0.1em]",
            "whitespace-nowrap transition-colors cursor-pointer",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground",
            isActive ? "text-midground" : "opacity-50 hover:opacity-90",
          )
        }
        style={{ clipPath: "var(--component-tab-clip-path)" }}
      >
        {({ isActive }) => (
          <>
            <Icon className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{navLabel}</span>
            <span
              aria-hidden
              className="absolute inset-y-0.5 left-1.5 right-1.5 bg-midground opacity-0 pointer-events-none transition-opacity duration-200 group-hover:opacity-5"
            />
            {isActive && (
              <span
                aria-hidden
                className="absolute left-0 top-0 bottom-0 w-px bg-midground"
                style={{ mixBlendMode: "plus-lighter" }}
              />
            )}
          </>
        )}
      </NavLink>
    </li>
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

  const primaryNav = useMemo(
    () => (embeddedChat ? [CHAT_NAV_ITEM, ...PRIMARY_NAV] : PRIMARY_NAV),
    [embeddedChat],
  );

  /** All nav items for plugin positioning logic. */
  const allBuiltinNav = useMemo(
    () => [...primaryNav, ...ACTIVITY_NAV, ...ADMIN_NAV],
    [primaryNav],
  );

  const pluginItems = useMemo(
    () => buildNavItems(allBuiltinNav, manifests).slice(allBuiltinNav.length),
    [allBuiltinNav, manifests],
  );

  const pluginTabMeta = useMemo(
    () =>
      manifests
        .filter((m) => !m.tab.hidden)
        .map((m) => ({ path: m.tab.override ?? m.tab.path, label: m.label })),
    [manifests],
  );

  const routes = useMemo(
    () => buildRoutes(builtinRoutes, manifests),
    [builtinRoutes, manifests],
  );

  const visibleActivity = useMemo(
    () => ACTIVITY_NAV.filter((item) => isVisible(item.section)),
    [isVisible],
  );

  const visibleAdmin = useMemo(
    () => ADMIN_NAV.filter((item) => isVisible(item.section)),
    [isVisible],
  );

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
    const onChange = (e: MediaQueryListEvent) => { if (e.matches) setMobileOpen(false); };
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  const sidebarNav = (
    <nav
      className="min-h-0 w-full flex-1 overflow-y-auto overflow-x-hidden py-1"
      aria-label={t.app.navigation}
    >
      {/* Primary group */}
      <ul className="flex flex-col pb-1">
        {primaryNav.map((item) => (
          <NavItem key={item.path} {...item} onClick={closeMobile} t={t} />
        ))}
        {pluginItems.map((item) => (
          <NavItem key={item.path} {...item} onClick={closeMobile} t={t} />
        ))}
      </ul>

      {/* Activity group */}
      {visibleActivity.length > 0 && (
        <>
          <div className="mx-5 border-t border-current/10" />
          <NavGroupHeader
            label="Activity"
            expanded={activityExpanded}
            onToggle={() => setActivityExpanded((v) => !v)}
          />
          {activityExpanded && (
            <ul className="flex flex-col">
              {visibleActivity.map((item) => (
                <NavItem key={item.path} {...item} onClick={closeMobile} t={t} />
              ))}
            </ul>
          )}
        </>
      )}

      {/* Admin group */}
      {visibleAdmin.length > 0 && (
        <>
          <div className="mx-5 border-t border-current/10 mt-1" />
          <NavGroupHeader
            label="Admin"
            expanded={adminExpanded}
            onToggle={() => setAdminExpanded((v) => !v)}
          />
          {adminExpanded && (
            <ul className="flex flex-col">
              {visibleAdmin.map((item) => (
                <NavItem key={item.path} {...item} onClick={closeMobile} t={t} />
              ))}
            </ul>
          )}
        </>
      )}
    </nav>
  );

  const sectionLabels: Record<string, string> = {
    analytics: "Analytics",
    logs: "Logs",
    cron: "Cron",
    skills: "Skills",
    config: "Config",
    env: "Keys",
    docs: "Docs",
  };

  return (
    <div
      data-layout-variant={layoutVariant}
      className="font-mondwest flex h-dvh max-h-dvh min-h-0 flex-col overflow-hidden bg-black text-midground antialiased"
    >
      <SelectionSwitcher />
      <Backdrop />
      <PluginSlot name="backdrop" />

      {/* Mobile nav backdrop */}
      {mobileOpen && (
        <button
          type="button"
          aria-label={t.app.closeNavigation}
          onClick={closeMobile}
          className="lg:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm cursor-pointer"
        />
      )}

      <PluginSlot name="header-banner" />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex min-h-0 min-w-0 flex-1">
          {/* Sidebar */}
          <aside
            id="app-sidebar"
            aria-label={t.app.navigation}
            className={cn(
              "fixed top-0 left-0 z-50 flex h-dvh max-h-dvh w-64 min-h-0 flex-col",
              "border-r border-current/20",
              "bg-background-base/95 backdrop-blur-sm",
              "transition-transform duration-200 ease-out",
              mobileOpen ? "translate-x-0" : "-translate-x-full",
              "lg:sticky lg:top-0 lg:translate-x-0 lg:shrink-0",
            )}
            style={{
              background: "var(--component-sidebar-background)",
              clipPath: "var(--component-sidebar-clip-path)",
              borderImage: "var(--component-sidebar-border-image)",
            }}
          >
            {/* Sidebar header */}
            <div className="flex h-14 shrink-0 items-center justify-between gap-2 px-5 border-b border-current/20">
              <Typography
                className="font-bold text-[1.125rem] leading-[0.95] tracking-[0.0525rem] text-midground uppercase"
                style={{ mixBlendMode: "plus-lighter" }}
              >
                Mercury
              </Typography>
              <button
                type="button"
                onClick={closeMobile}
                aria-label={t.app.closeNavigation}
                className="lg:hidden inline-flex h-7 w-7 items-center justify-center text-midground/70 hover:text-midground transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <PluginSlot name="header-left" />

            {sidebarNav}

            <SidebarSystemActions onNavigate={closeMobile} />

            {/* Settings + theme footer */}
            <div className="shrink-0 border-t border-current/20">
              {/* Section visibility panel */}
              {settingsOpen && (
                <div className="border-b border-current/10 py-2">
                  <p className="px-5 pt-1 pb-1.5 font-mondwest text-[0.58rem] tracking-[0.14em] text-midground/30 uppercase">
                    Visible Sections
                  </p>
                  {ALL_TOGGLEABLE_SECTIONS.map((section) => (
                    <VisibilityToggle
                      key={section}
                      label={sectionLabels[section] ?? section}
                      visible={isVisible(section)}
                      onToggle={() => toggle(section)}
                    />
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between gap-2 px-3 py-2">
                <div className="flex min-w-0 items-center gap-2">
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
                    "inline-flex h-7 w-7 items-center justify-center rounded",
                    "transition-colors cursor-pointer",
                    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/40",
                    settingsOpen
                      ? "text-midground bg-midground/10"
                      : "text-midground/40 hover:text-midground/70",
                  )}
                >
                  <Settings className="h-3.5 w-3.5" />
                </button>
              </div>

              <SidebarFooter />
            </div>
          </aside>

          {/* Main content */}
          <PageHeaderProvider pluginTabs={pluginTabMeta}>
            <div
              className={cn(
                "relative z-2 flex min-w-0 min-h-0 flex-1 flex-col",
                "px-3 sm:px-6",
                /* bottom padding for mobile bottom nav */
                "pb-20 lg:pb-0",
                isChatRoute
                  ? "pt-1 sm:pt-2 lg:pt-4"
                  : "pt-2 sm:pt-4 lg:pt-6",
                isDocsRoute && "min-h-0 flex-1",
              )}
            >
              <PluginSlot name="pre-main" />
              <div
                className={cn(
                  "w-full min-w-0",
                  (isDocsRoute || isChatRoute) && "min-h-0 flex flex-1 flex-col",
                )}
              >
                <Routes>
                  {routes.map(({ key, path, element }) => (
                    <Route key={key} path={path} element={element} />
                  ))}
                  <Route path="*" element={<Navigate to="/sessions" replace />} />
                </Routes>
              </div>
              <PluginSlot name="post-main" />
            </div>
          </PageHeaderProvider>
        </div>
      </div>

      {/* Mobile bottom nav — replaces the old fixed top header */}
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
    {
      action: "restart",
      icon: RotateCw,
      label: t.status.restartGateway,
      runningLabel: t.status.restartingGateway,
      spin: true,
    },
    {
      action: "update",
      icon: Download,
      label: t.status.updateMercury,
      runningLabel: t.status.updatingMercury,
      spin: false,
    },
  ];

  const handleClick = (action: SystemAction) => {
    if (isBusy) return;
    void runAction(action);
    navigate("/sessions");
    onNavigate();
  };

  return (
    <div className="shrink-0 flex flex-col border-t border-current/10 py-1">
      <span className="px-5 pt-0.5 pb-0.5 font-mondwest text-[0.58rem] tracking-[0.15em] uppercase opacity-30">
        {t.app.system}
      </span>

      <SidebarStatusStrip />

      <ul className="flex flex-col">
        {items.map(({ action, icon: Icon, label, runningLabel, spin }) => {
          const isPending = pendingAction === action;
          const isActionRunning = activeAction === action && isRunning && !isPending;
          const busy = isPending || isActionRunning;
          const displayLabel = isActionRunning ? runningLabel : label;
          const disabled = isBusy && !busy;

          return (
            <li key={action}>
              <button
                type="button"
                onClick={() => handleClick(action)}
                disabled={disabled}
                aria-busy={busy}
                className={cn(
                  "group relative flex w-full items-center gap-3",
                  "px-5 py-1.5",
                  "font-mondwest text-[0.75rem] tracking-[0.1em]",
                  "text-left whitespace-nowrap transition-opacity cursor-pointer",
                  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground",
                  busy ? "text-midground opacity-100" : "opacity-50 hover:opacity-90",
                  "disabled:cursor-not-allowed disabled:opacity-30",
                )}
              >
                {isPending ? (
                  <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
                ) : (
                  <Icon
                    className={cn(
                      "h-3.5 w-3.5 shrink-0",
                      isActionRunning && spin && "animate-spin",
                      isActionRunning && !spin && "animate-pulse",
                    )}
                  />
                )}
                <span className="truncate">{displayLabel}</span>
                <span
                  aria-hidden
                  className="absolute inset-y-0.5 left-1.5 right-1.5 bg-midground opacity-0 pointer-events-none transition-opacity duration-200 group-hover:opacity-5"
                />
                {busy && (
                  <span
                    aria-hidden
                    className="absolute left-0 top-0 bottom-0 w-px bg-midground"
                    style={{ mixBlendMode: "plus-lighter" }}
                  />
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface NavItem {
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

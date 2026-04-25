# Mercury — Web UI

Mobile-first dashboard for the Mercury agent. Forked from the Hermes Agent
dashboard (MIT, Nous Research) and rebranded with the Mercury Silver theme.

## Stack

- **Vite** + **React 19** + **TypeScript**
- **Tailwind CSS v4** with the Mercury Silver palette
  (deep slate-navy `#0c1117` + cool silver `#d6dde6`)
- **`@nous-research/ui`** as the design-system foundation (kept upstream;
  Mercury layers its own theme variables on top)
- **shadcn/ui**-style local primitives in `src/components/ui/`

## Tailscale-only access

Mercury's WebUI is intended to be reached via Tailscale, not exposed
publicly.  On the host:

```bash
tailscale serve --bg --https=443 http://localhost:8765
```

Then any device on the same tailnet (including the iOS / Android Tailscale
app) can reach `https://<your-host>.<tailnet>.ts.net`.  The backend trusts
the `Tailscale-User-Login` and `Tailscale-User-Name` headers Tailscale
injects, so no separate password layer is needed.

## Development

```bash
# Start the backend API server
cd ../
python -m hermes_cli.main web --no-open

# In another terminal, start the Vite dev server (with HMR + API proxy)
cd mercury-web/
npm run dev
```

The Vite dev server proxies `/api` requests to `http://127.0.0.1:9119`
(the FastAPI backend).  The dev server scrapes the live backend's session
token so authenticated `/api` calls work in HMR mode.

## Build

```bash
npm run build
```

This outputs to `../hermes_cli/web_dist/`, which the FastAPI server
serves as a static SPA.  The built assets are included in the Python
package via `pyproject.toml` package-data.

## Structure

```
src/
├── components/ui/   # Reusable UI primitives (Card, Badge, Button, Input, etc.)
├── contexts/        # PageHeader, SystemActions
├── hooks/           # useToast, useSidebarStatus, useConfirmDelete
├── i18n/            # en.ts, zh.ts
├── lib/             # API client + cn() helper
├── pages/
│   ├── SessionsPage   # Sessions list (default route)
│   ├── ChatPage       # Embedded TUI via xterm.js + /api/pty
│   ├── AnalyticsPage, LogsPage, CronPage, SkillsPage,
│   │ ConfigPage, EnvPage, DocsPage
│   └── BrainsPage     # Mercury-specific: dual-brain status + override (TODO)
├── plugins/         # Dashboard plugin SDK
├── themes/          # ThemeProvider (overlays Mercury Silver palette)
├── App.tsx          # Main layout, sidebar drawer, navigation
├── main.tsx         # React entry point
└── index.css        # Tailwind imports + Mercury Silver theme variables
```

## Mobile-first

The layout uses a sidebar-drawer pattern: collapsed off-canvas under
`lg` (1024px), sticky-side at `lg` and above.  All interactive controls
target ≥44px tap area on mobile.  The Tailscale app on iOS/Android puts
your phone on the tailnet, so the WebUI works natively in mobile Safari /
Chrome without any port forwarding or public exposure.

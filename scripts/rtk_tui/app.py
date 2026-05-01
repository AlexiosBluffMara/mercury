"""Textual TUI for live operator control of the rtk-* stack.

Layout
------
    +---------------------+----------------------------+
    |  Services (DataTable) |  Health summary (right)    |
    +---------------------+----------------------------+
    |  Log tail for highlighted service                  |
    +-----------------------------------------------------+
    |  (optional) Test panel                              |
    +-----------------------------------------------------+
    Footer:  r restart  R restart-all  s stop  l cycle-log  t test  q quit

Hotkeys are wired via Textual ``BINDINGS``. Polling cadence:
    - service status + GPU + cortex/mercury health: every 3 s
    - tunnel info: every 5 s
    - log tail of highlighted service: every 1 s
"""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass
from typing import ClassVar

import httpx
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Input, Static

from rtk_tui import health_probes
from rtk_tui.service_control import LOG_PATHS, SERVICES, ServiceController

# ISU brand colors -----------------------------------------------------------
ISU_CARDINAL = "#CC0000"
ISU_GOLD = "#F6A917"
ISU_BLUE = "#56758f"


# ---------------------------------------------------------------------------
# Test panel — a tiny overlay that POSTs {prompt: "..."} to mercury or cortex
# ---------------------------------------------------------------------------

@dataclass
class TestTarget:
    label: str
    url: str


TEST_TARGETS: list[TestTarget] = [
    TestTarget("mercury", "http://localhost:8767/api/chat"),
    TestTarget("cortex", "http://localhost:8765/api/generate"),
]


class TestPanel(Static):
    """Small input box + response area. Toggle visibility with ``t``."""

    DEFAULT_CSS = """
    TestPanel {
        display: none;
        height: 9;
        border: tall $accent;
        padding: 0 1;
    }
    TestPanel.-visible {
        display: block;
    }
    TestPanel #test-input {
        height: 3;
    }
    TestPanel #test-output {
        height: 4;
        color: $text-muted;
    }
    """

    target_index: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        yield Static(self._title(), id="test-title")
        yield Input(placeholder="hello (Enter to send, Tab to switch target)", id="test-input")
        yield Static("(no response yet)", id="test-output")

    def _title(self) -> str:
        tgt = TEST_TARGETS[self.target_index]
        return f"[b]Test panel[/b]  target=[{ISU_GOLD}]{tgt.label}[/] -> {tgt.url}   (Tab cycles)"

    def cycle_target(self) -> None:
        self.target_index = (self.target_index + 1) % len(TEST_TARGETS)
        self.query_one("#test-title", Static).update(self._title())

    async def submit(self, prompt: str) -> None:
        out = self.query_one("#test-output", Static)
        out.update("(sending...)")
        target = TEST_TARGETS[self.target_index]
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(target.url, json={"prompt": prompt})
            head = (resp.text or "").strip().replace("\n", " ")[:400]
            out.update(f"[{ISU_BLUE}]HTTP {resp.status_code}[/] {head}")
        except httpx.HTTPError as exc:
            out.update(f"[{ISU_CARDINAL}]error[/] {exc.__class__.__name__}: {exc}")


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

class RtkApp(App):
    """RTK operator TUI."""

    TITLE = "RTK operator console"
    SUB_TITLE = "rtk-cloudflared / rtk-cortex-webapp / rtk-mercury-gateway"

    CSS: ClassVar[str] = f"""
    Screen {{
        background: $surface;
    }}
    #top {{
        height: 12;
    }}
    #services-table {{
        width: 60%;
        border: tall {ISU_CARDINAL};
    }}
    #health-summary {{
        width: 40%;
        border: tall {ISU_BLUE};
        padding: 0 1;
    }}
    #log-pane {{
        height: 1fr;
        border: tall {ISU_GOLD};
        padding: 0 1;
        overflow-y: auto;
    }}
    .ok {{ color: {ISU_GOLD}; }}
    .bad {{ color: {ISU_CARDINAL}; }}
    .neutral {{ color: {ISU_BLUE}; }}
    """

    BINDINGS = [
        Binding("r", "restart_one", "Restart"),
        Binding("R", "restart_all", "Restart-all"),
        Binding("s", "stop_one", "Stop"),
        Binding("l", "cycle_log", "Cycle log"),
        Binding("t", "toggle_test", "Test panel"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.controller = ServiceController()
        self._log_streams = itertools.cycle(["out", "err"])
        self._current_log_stream: dict[str, str] = {svc: "out" for svc in SERVICES}
        self._client: httpx.AsyncClient | None = None
        self._latest_probes: health_probes.ProbeBundle | None = None

    # -- Compose ------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="top"):
            table = DataTable(id="services-table", cursor_type="row", zebra_stripes=True)
            yield table
            yield Static("(loading health...)", id="health-summary")
        yield Static("(select a service)", id="log-pane")
        yield TestPanel(id="test-panel")
        yield Footer()

    # -- Lifecycle ----------------------------------------------------------

    async def on_mount(self) -> None:
        table = self.query_one("#services-table", DataTable)
        table.add_columns("service", "state", "detail")
        for svc in SERVICES:
            table.add_row(svc, "...", "", key=svc)
        table.cursor_type = "row"
        table.focus()

        self._client = httpx.AsyncClient()

        # poll loops
        self.set_interval(3.0, self._tick_status)
        self.set_interval(5.0, self._tick_tunnel)
        self.set_interval(1.0, self._tick_log)
        # one immediate refresh so the user doesn't stare at "..."
        self.run_worker(self._tick_status(), exclusive=False)
        self.run_worker(self._tick_tunnel(), exclusive=False)

    async def on_unmount(self) -> None:
        if self._client:
            await self._client.aclose()

    # -- Polling ------------------------------------------------------------

    async def _tick_status(self) -> None:
        # Service statuses (cheap, sync subprocess wrapped in to_thread)
        loop = asyncio.get_running_loop()
        statuses = await asyncio.gather(*[
            loop.run_in_executor(None, self.controller.status, svc) for svc in SERVICES
        ])

        # GPU + http health
        if self._client is not None:
            gpu = await health_probes.probe_gpu(self._client)
            cortex = await health_probes.probe_http(self._client, f"{health_probes.CORTEX_URL}/api/health")
            mercury = await health_probes.probe_http(self._client, f"{health_probes.MERCURY_URL}/api/health")
        else:
            gpu = health_probes.GpuState()
            cortex = health_probes.HttpHealth(url=f"{health_probes.CORTEX_URL}/api/health")
            mercury = health_probes.HttpHealth(url=f"{health_probes.MERCURY_URL}/api/health")

        if self._latest_probes is None:
            self._latest_probes = health_probes.ProbeBundle()
        self._latest_probes.gpu = gpu
        self._latest_probes.cortex = cortex
        self._latest_probes.mercury = mercury

        table = self.query_one("#services-table", DataTable)
        for s in statuses:
            try:
                table.update_cell(s.name, "state", self._format_state(s.state))
                table.update_cell(s.name, "detail", s.detail or "")
            except Exception:  # noqa: BLE001 — table not yet ready
                continue

        self._render_health()

    async def _tick_tunnel(self) -> None:
        info = await health_probes.probe_tunnel()
        if self._latest_probes is None:
            self._latest_probes = health_probes.ProbeBundle()
        self._latest_probes.tunnel = info
        self._render_health()

    async def _tick_log(self) -> None:
        svc = self._highlighted_service()
        if not svc:
            return
        stream = self._current_log_stream.get(svc, "out")
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            None, lambda: self.controller.tail_log(svc, lines=40, stream=stream)
        )
        path = LOG_PATHS[svc].out if stream == "out" else LOG_PATHS[svc].err
        title = f"[b]{svc}[/]  log=[{ISU_GOLD}]{stream}[/]  ({path})"
        pane = self.query_one("#log-pane", Static)
        pane.update(f"{title}\n\n{text}")

    # -- Rendering ----------------------------------------------------------

    @staticmethod
    def _format_state(state: str) -> str:
        color = {
            "running": ISU_GOLD,
            "stopped": ISU_CARDINAL,
            "errored": ISU_CARDINAL,
            "starting": ISU_BLUE,
            "stopping": ISU_BLUE,
        }.get(state, ISU_BLUE)
        return f"[{color}]{state}[/]"

    def _render_health(self) -> None:
        if not self._latest_probes:
            return
        b = self._latest_probes
        tunnel_color = ISU_GOLD if b.tunnel.healthy else ISU_CARDINAL
        cortex_color = ISU_GOLD if b.cortex.ok else ISU_CARDINAL
        mercury_color = ISU_GOLD if b.mercury.ok else ISU_CARDINAL

        if b.gpu.available and b.gpu.vram_free_mb is not None:
            gpu_line = (
                f"[{ISU_GOLD}]GPU[/]    free={b.gpu.vram_free_mb}MB / {b.gpu.vram_total_mb}MB  "
                f"sched={b.gpu.scheduler_state}  q={b.gpu.queue_depth}"
            )
        else:
            gpu_line = f"[{ISU_CARDINAL}]GPU[/]    {b.gpu.detail or 'no data'}"

        body = (
            f"[b]Tunnel[/] [{tunnel_color}]{b.tunnel.name}[/] "
            f"conns={b.tunnel.connections}  {b.tunnel.detail}\n"
            f"[b]Cortex[/] [{cortex_color}]{b.cortex.url}[/]  "
            f"{b.cortex.detail or 'ok' if b.cortex.ok else b.cortex.detail}\n"
            f"[b]Mercury[/] [{mercury_color}]{b.mercury.url}[/]  "
            f"{b.mercury.detail or 'ok' if b.mercury.ok else b.mercury.detail}\n"
            f"\n{gpu_line}"
        )
        self.query_one("#health-summary", Static).update(body)

    def _highlighted_service(self) -> str | None:
        try:
            table = self.query_one("#services-table", DataTable)
            row = table.cursor_row
            if row is None or row < 0:
                return None
            return table.get_row_at(row)[0]
        except Exception:  # noqa: BLE001
            return None

    # -- Actions (key bindings) --------------------------------------------

    async def action_restart_one(self) -> None:
        svc = self._highlighted_service()
        if not svc:
            return
        self.notify(f"restarting {svc}...", timeout=2)
        loop = asyncio.get_running_loop()
        ok, msg = await loop.run_in_executor(None, self.controller.restart, svc)
        self.notify(f"{svc}: {msg}", severity="information" if ok else "error")

    async def action_restart_all(self) -> None:
        self.notify("restarting all (cloudflared -> cortex -> mercury)...", timeout=3)
        loop = asyncio.get_running_loop()
        for svc in SERVICES:
            ok, msg = await loop.run_in_executor(None, self.controller.restart, svc)
            self.notify(f"{svc}: {msg}", severity="information" if ok else "error")

    async def action_stop_one(self) -> None:
        svc = self._highlighted_service()
        if not svc:
            return
        self.notify(f"stopping {svc}...", timeout=2)
        loop = asyncio.get_running_loop()
        ok, msg = await loop.run_in_executor(None, self.controller.stop, svc)
        self.notify(f"{svc}: {msg}", severity="information" if ok else "error")

    def action_cycle_log(self) -> None:
        svc = self._highlighted_service()
        if not svc:
            return
        current = self._current_log_stream.get(svc, "out")
        if LOG_PATHS[svc].err is None:
            return  # only one log stream
        self._current_log_stream[svc] = "err" if current == "out" else "out"
        self.notify(f"{svc}: showing {self._current_log_stream[svc]} log")

    def action_toggle_test(self) -> None:
        panel = self.query_one("#test-panel", TestPanel)
        panel.toggle_class("-visible")
        if panel.has_class("-visible"):
            self.query_one("#test-input", Input).focus()

    # -- Test panel input handler ------------------------------------------

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "test-input":
            return
        prompt = event.value.strip()
        if not prompt:
            return
        await self.query_one("#test-panel", TestPanel).submit(prompt)
        event.input.value = ""

    def on_key(self, event) -> None:  # noqa: ANN001 — Textual key event type
        # Tab inside the test panel input cycles target
        if event.key == "tab":
            panel = self.query_one("#test-panel", TestPanel)
            if panel.has_class("-visible"):
                panel.cycle_target()
                event.stop()

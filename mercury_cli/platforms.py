"""
Shared platform registry for Mercury Agent.

Single source of truth for platform metadata consumed by both
skills_config (label display) and tools_config (default toolset
resolution).  Import ``PLATFORMS`` from here instead of maintaining
duplicate dicts in each module.
"""

from collections import OrderedDict
from typing import NamedTuple


class PlatformInfo(NamedTuple):
    """Metadata for a single platform entry."""
    label: str
    default_toolset: str


# Ordered so that TUI menus are deterministic.
PLATFORMS: OrderedDict[str, PlatformInfo] = OrderedDict([
    ("cli",            PlatformInfo(label="🖥️  CLI",            default_toolset="mercury-cli")),
    ("telegram",       PlatformInfo(label="📱 Telegram",        default_toolset="mercury-telegram")),
    ("discord",        PlatformInfo(label="💬 Discord",         default_toolset="mercury-discord")),
    ("slack",          PlatformInfo(label="💼 Slack",           default_toolset="mercury-slack")),
    ("whatsapp",       PlatformInfo(label="📱 WhatsApp",        default_toolset="mercury-whatsapp")),
    ("signal",         PlatformInfo(label="📡 Signal",          default_toolset="mercury-signal")),
    ("bluebubbles",    PlatformInfo(label="💙 BlueBubbles",     default_toolset="mercury-bluebubbles")),
    ("email",          PlatformInfo(label="📧 Email",           default_toolset="mercury-email")),
    ("homeassistant",  PlatformInfo(label="🏠 Home Assistant",  default_toolset="mercury-homeassistant")),
    ("mattermost",     PlatformInfo(label="💬 Mattermost",      default_toolset="mercury-mattermost")),
    ("matrix",         PlatformInfo(label="💬 Matrix",          default_toolset="mercury-matrix")),
    ("dingtalk",       PlatformInfo(label="💬 DingTalk",        default_toolset="mercury-dingtalk")),
    ("feishu",         PlatformInfo(label="🪽 Feishu",          default_toolset="mercury-feishu")),
    ("wecom",          PlatformInfo(label="💬 WeCom",           default_toolset="mercury-wecom")),
    ("wecom_callback", PlatformInfo(label="💬 WeCom Callback",  default_toolset="mercury-wecom-callback")),
    ("weixin",         PlatformInfo(label="💬 Weixin",          default_toolset="mercury-weixin")),
    ("qqbot",          PlatformInfo(label="💬 QQBot",           default_toolset="mercury-qqbot")),
    ("webhook",        PlatformInfo(label="🔗 Webhook",         default_toolset="mercury-webhook")),
    ("api_server",     PlatformInfo(label="🌐 API Server",      default_toolset="mercury-api-server")),
    ("cron",           PlatformInfo(label="⏰ Cron",            default_toolset="mercury-cron")),
])


def platform_label(key: str, default: str = "") -> str:
    """Return the display label for a platform key, or *default*."""
    info = PLATFORMS.get(key)
    return info.label if info is not None else default

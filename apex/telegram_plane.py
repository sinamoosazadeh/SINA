"""Telegram control plane with MarkdownV2-safe rendering and server-side auth."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable


MDV2_SPECIALS = r"_*[]()~`>#+-=|{}.!\\"


def escape_mdv2(text: str) -> str:
    out = []
    for ch in str(text):
        if ch in MDV2_SPECIALS:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def render_message(template: str, **fields: object) -> str:
    safe = {k: escape_mdv2(v) for k, v in fields.items()}
    return template.format(**safe)


@dataclass
class TelegramState:
    screen: str = "HOME"
    busy: bool = False


class TelegramControlPlane:
    SCREENS = {"HOME", "STATUS", "POSITIONS", "ORDERS", "HEALTH", "REPORTS", "SETTINGS", "RISK", "PROTECTIVE", "ERROR", "RECOVERY"}

    def __init__(self, authorized_user_ids: list[int], get_status: Callable[[], dict]):
        self.authorized = set(authorized_user_ids)
        self.get_status = get_status
        self.state = TelegramState()
        self.seen_callbacks: set[str] = set()
        self.rate: dict[int, int] = {}

    def authorize(self, user_id: int) -> bool:
        return user_id in self.authorized

    def handle_command(self, user_id: int, command: str) -> str:
        if not self.authorize(user_id):
            return render_message("unauthorized user {uid}", uid=str(user_id))
        cmd = command.strip().lower()
        mapping = {
            "/start": "HOME",
            "/home": "HOME",
            "/status": "STATUS",
            "/positions": "POSITIONS",
            "/orders": "ORDERS",
            "/health": "HEALTH",
            "/reports": "REPORTS",
            "/settings": "SETTINGS",
            "/risk": "RISK",
            "/protective": "PROTECTIVE",
        }
        if cmd in mapping:
            self.state.screen = mapping[cmd]
        return self.render_screen()

    def handle_callback(self, user_id: int, callback_id: str, action: str) -> str:
        if not self.authorize(user_id):
            return "unauthorized"
        if callback_id in self.seen_callbacks:
            return render_message("duplicate callback {cid} ignored", cid=callback_id)
        self.seen_callbacks.add(callback_id)
        if action not in self.SCREENS and action not in {"REFRESH", "BACK", "HOME", "KILL", "UNKILL"}:
            return "malformed"
        if action == "BACK" or action == "HOME":
            self.state.screen = "HOME"
        elif action == "REFRESH":
            pass
        elif action in self.SCREENS:
            self.state.screen = action
        elif action in {"KILL", "UNKILL"}:
            self.state.screen = "PROTECTIVE"
        return self.render_screen()

    def render_screen(self) -> str:
        st = self.get_status()
        return render_message(
            "APEX GEN5 {mode}\nhealth={health}\nsymbol={symbol}\nequity={equity}\nkill={kill}\nscreen={screen}",
            mode=st.get("runtime_mode", ""),
            health=st.get("health", ""),
            symbol=st.get("symbol", ""),
            equity=str(st.get("equity", "")),
            kill=str(st.get("kill_switch", "")),
            screen=self.state.screen,
        )

"""
PCBVisor — Pipeline Logger
In-memory structured logger for Streamlit display. No file I/O.
"""

import time


class PipelineLogger:
    """Accumulates log lines in memory for display in the Streamlit UI."""

    def __init__(self) -> None:
        self._entries: list[tuple[float, str, str]] = []  # (timestamp, level, message)

    def info(self, msg: str) -> None:
        self._add("INFO", msg)

    def warning(self, msg: str) -> None:
        self._add("WARNING", msg)

    def error(self, msg: str) -> None:
        self._add("ERROR", msg)

    def debug(self, msg: str) -> None:
        self._add("DEBUG", msg)

    def _add(self, level: str, msg: str) -> None:
        self._entries.append((time.time(), level, msg))

    def get_lines(self) -> list[str]:
        """Return all log lines as formatted strings."""
        return [f"[{lvl}] {msg}" for _, lvl, msg in self._entries]

    def clear(self) -> None:
        self._entries.clear()

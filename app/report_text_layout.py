from __future__ import annotations

from collections.abc import Iterable


REPORT_DIVIDER = "────────────"


def report_header(title: str, lines: Iterable[str] = ()) -> list[str]:
    return [title, REPORT_DIVIDER, *_nonempty_lines(lines)]


def append_report_block(
    output: list[str],
    content: Iterable[str],
    *,
    title: str | None = None,
) -> None:
    block = list(content)
    while block and not block[0]:
        block.pop(0)
    while block and not block[-1]:
        block.pop()
    if not block:
        return
    if output and output[-1] != "":
        output.append("")
    output.append(REPORT_DIVIDER)
    if title:
        output.extend([title, ""])
    output.extend(block)


def report_content_length(text: str) -> int:
    return len("\n".join(line for line in text.splitlines() if line != REPORT_DIVIDER))


def _nonempty_lines(lines: Iterable[str]) -> list[str]:
    return [line for line in lines if line]

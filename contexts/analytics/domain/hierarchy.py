"""Resolve per-section serial numbers into globally-unique hierarchy paths.

Excel cost sheets number rows per section: Chinese-numeral top-level rows
(一 / 二 / 三 …) each restart Arabic child numbering (1, 1.1, 2 …), so the
raw ``hierarchy_code`` stored at parse time is *not* unique across a sheet
("1.1" can appear under several top-level groups) and cannot be grouped by
a naive ``split(".")`` prefix match.

Walking rows in original row order, ``resolve_hierarchy_paths`` rewrites
each code to a full path (e.g. ``"二.2.1"``) and assigns a 1-based depth
``level``:

- level 1 — Chinese-numeral top-level groups (一 项目管理费, 二 建筑工程 …)
- level 2 — plain-segment children inside a group (1 人工费 …),
  or top-level rows when the sheet has no Chinese-numeral groups at all
- level 3 — dotted grandchildren (1.1 基本人工费 …)

Rows without a code (e.g. "其中：…" annotation lines) keep
``hierarchy_code=None`` and get ``level=None``; consumers render them flat.
"""

from __future__ import annotations

import re

# A top-level group marker is a bare Chinese numeral ("一", "十二").
_CN_NUMERAL_RE = re.compile(r"^[一二三四五六七八九十百千万零〇两]+$")

# Segment separators accepted in stored codes (mirrors template separators).
_SEGMENT_SPLIT_RE = re.compile(r"[.．\-－—]")


def _depth(code: str) -> int:
    return len([s for s in _SEGMENT_SPLIT_RE.split(code) if s])


def resolve_hierarchy_paths(items: list[dict]) -> list[dict]:
    """Rewrite ``items[*]["hierarchy_code"]`` to full paths; add ``"level"``.

    ``items`` must be in original row order (the state machine tracks the
    current top-level group positionally). Mutates and returns ``items``.
    """
    current_top: str | None = None
    for item in items:
        code = item.get("hierarchy_code")
        if not code:
            item["level"] = None
            continue
        code = str(code)
        if _CN_NUMERAL_RE.match(code):
            current_top = code
            item["level"] = 1
            continue
        if current_top is not None:
            item["hierarchy_code"] = f"{current_top}.{code}"
            item["level"] = _depth(code) + 1
        else:
            item["level"] = _depth(code)
    return items

from __future__ import annotations

from abc import ABC


class AnalyticsRepository(ABC):
    """Port for the analytics projection and reporting model.

    The projection deliberately has a broad query surface. Keeping the marker
    port here prevents application/interface code from depending on ORM tables.
    """

"""Shared SQLAlchemy metadata and ORM mapper registry.

All table definitions across bounded contexts use this single metadata
instance so that ``metadata.create_all()`` works correctly.  The imperative
mapper registry is also shared — every ``@mapper_registry.mapped`` class
is registered against it.
"""

import sqlalchemy as sa
from sqlalchemy.orm import registry

metadata = sa.MetaData()
mapper_registry = registry(metadata=metadata)


class _OrmBase:
    """Imperative-mapped base.  SA 2.0 mapping is via ``__table__``, not annotations."""
    __allow_unmapped__ = True

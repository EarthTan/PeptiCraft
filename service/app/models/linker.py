"""Linker models.

Two linker tables end up coexisting, and the reason is worth recording. The `linkers` table
created by `12_create_constructs.sql` holds six rows: `GGGGS` and `EAAAK` at three repeat
lengths each. Its own comment calls them a sample — "这里只示例插入最终拼接构造时会用到的
几个；完整 32 库由 linker_gen.py 生成" — and `iGEM-platform-main/src/pipeline/antioxidant/
assemble.py` picks the first row of it as a placeholder. The frontend's `linkers.ts` instead
carries 15 curated entries with per-entry literature provenance.

`constructs.linker_id` points at the six-row table, so that table cannot be rewritten
without changing what an existing foreign key means. The 15 curated entries therefore go
into `linker_library`, and `LinkerView.source_table` records which of the two a given entry
came from. Nothing merges them until the pipeline reassembles constructs against the real
library.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class LinkerUnit(BaseModel):
    unit: str
    count: int
    label: str


class LinkerView(BaseModel):
    """List and embedded shape."""

    id: str
    name: str
    sequence: str
    length: int
    rigidity: str = Field(
        description="`Flexible` / `Mostly Flexible` / `Balanced` / `Mostly Rigid` / `Rigid`."
    )
    source_table: str = Field(description="`linkers` or `linker_library`.")
    unit_composition: list[LinkerUnit] = Field(default_factory=list)
    description: str | None = None
    reference: str | None = None


class LinkerDetail(LinkerView):
    flexible_count: int | None = None
    rigid_count: int | None = None
    rigidity_index: float | None = Field(
        default=None,
        description="Stored as 0.0 for fully flexible and 1.0 for fully rigid in the "
        "sample table. It is a coarse two-value convention, not a measured property, and "
        "the frontend's five-band `rigidity` label is a presentation choice layered on top.",
    )
    priority_reason: str | None = None

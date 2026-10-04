"""Linker endpoints.

Two tables are exposed, and `source_table` on each row says which one it came from.
`linkers` holds the six sample rows the assembly script drew from, and every stored
construct's `linker_id` resolves there. `linker_library` holds the fifteen curated entries
with their literature provenance. They are not merged, because merging would erase the fact
that a construct's recorded linker was chosen by "take the first available row" rather than
by design.

The Builder enumerates the curated library, and this is the endpoint it reads. The
parameter that includes the sample rows exists so that the difference stays inspectable
rather than invisible.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.linker import LinkerDetail, LinkerView
from ..repositories import linkers as repo
from ..services import linkers as service

router = APIRouter(prefix="/linkers", tags=["linkers"])


@router.get("", response_model=list[LinkerView])
def list_linkers(
    include_placeholder: bool = Query(
        default=False,
        description="Include the six sample rows from the `linkers` table alongside the "
        "curated library. Off by default so a linker listing does not mix a sample with the "
        "library it stands in for.",
    ),
) -> list[LinkerView]:
    return service.list_views(include_placeholder=include_placeholder)


@router.get("/{linker_id}", response_model=LinkerDetail)
def get_linker(linker_id: str) -> LinkerDetail:
    row = repo.get_linker(linker_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"linker {linker_id!r} not found")
    return service.to_detail(row)

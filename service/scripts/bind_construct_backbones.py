#!/usr/bin/env python3
"""Bind the stored constructs to real scaffolds, and mirror those scaffolds to where the
constructs can reach them.

Two gaps are closed here, and they are closed together because neither is useful alone.

The first is an identifier gap. `constructs.backbone_id` is a foreign key to
`backbone_proteins`; the curated scaffolds live in `scaffold_library`, keyed by a text slug.
Two tables, two key types, and no overlap in naming — the placeholder table carries silk and
elastin abbreviations, the curated library carries eight patent clusters. Every construct
therefore points at `backbone_proteins.id = 1`, whose sequence column holds the marker string
`PLACEHOLDER_4RepCT`. This script writes the eight curated clusters into `backbone_proteins`
with their real representative sequence, which is what lets a construct reference one.

The second is a selection rule. Nothing in the curated material connects a functional
direction to a scaffold; what it does carry is an application tag per cluster, and what the
constructs carry is a `scenario`. The route is the one key both sides speak, so it is the key
used here, in two steps that already exist elsewhere in the project and are not duplicated:

  * scenario -> route, from `SCENARIO_ROUTE_HINT` in `app/services/constructs.py`;
  * route -> scaffold, from `scaffold_library.route_ids`, produced by the tag vocabulary in
    `import_scaffold_library.TAG_COLUMNS`.

A route admits several scaffolds, so one has to be the default. The default is the route's
highest evidence grade; ties go to the scaffold tagged for fewer routes, on the reading that a
cluster admitted by one application is more specific to it than one admitted by three; a
remaining tie goes to the short name, so the choice is deterministic and reproducible. The
rule is a platform convention — the material states none — so `ROUTE_DEFAULT_OVERRIDE` exists
to pin any route by hand without touching the rule, and a pin is reported in the output so it
cannot be mistaken for the rule's own answer.

The binding this writes is a platform default, not a pipeline output: no record exists of the
pipeline having paired these peptides with these scaffolds. The service already separates the
two cases in its own vocabulary — a stored binding is reported as `verified` and a request-time
choice as `inferred` — and a backfilled row lands in the first group, whose note claims only
that the pairing is recorded against the construct.

Statements address scaffolds by name rather than by id, so the script needs no database to
plan a run and the plan is identical whichever way the clusters were read.

    python3 service/scripts/bind_construct_backbones.py --dry-run
    python3 service/scripts/bind_construct_backbones.py --emit-sql /tmp/bind.sql
    python3 service/scripts/bind_construct_backbones.py

Idempotent: the mirror is guarded by a name test and the rebind only touches rows still
pointing at a placeholder row, so a second run reports nothing to do.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_scaffold_library as scaffold_source  # noqa: E402
from app.services.constructs import SCENARIO_ROUTE_HINT  # noqa: E402
from app.services.reference import ROUTES_BY_ID  # noqa: E402

EVIDENCE_ORDER = {"E5": 5, "E4": 4, "E3": 3, "E2": 2, "E1": 1}

# Route id -> the scaffold it defaults to, named by `scaffold_library.id` or by `short_name`.
#
# The two entries below are pinned rather than computed, and for one reason. Both routes have
# two clusters at the same evidence grade, so the rule falls through to the short-name
# tiebreak, which lands on `Jinbo COL3A1x16`. That cluster is the 30-aa COL3A1 domain repeated
# sixteen times, and the team's material states twice — in its label dictionary and in its
# merge record — that repeat constructs do not inherit the parent protein's tags. If that
# statement is applied, the cluster carries no application tag and is not a candidate for
# either route at all. The pinned choice is the cluster that is tagged under both readings, so
# the default does not depend on how that question is settled. Removing a pin restores the
# computed answer, which is printed in the run's output either way.
ROUTE_DEFAULT_OVERRIDE: dict[str, str] = {
    "mask-patch": "Jinbo HC8/HC16",
    "injectable-filler": "Jinbo HC8/HC16",
}

# A row is a placeholder when its name or sequence carries the marker, or when its length is
# zero. The test is the same shape the service uses, so the two cannot disagree about which
# rows a rebind is meant to touch. `{a}` is the alias of the `backbone_proteins` row being
# tested against, so the guard reads the same whether it is inspecting the row a construct
# currently points at or the row it is about to.
PLACEHOLDER = (
    "(UPPER(COALESCE({a}.name, '')) LIKE '%PLACEHOLDER%'"
    " OR UPPER(COALESCE({a}.sequence, '')) LIKE '%PLACEHOLDER%'"
    " OR COALESCE({a}.length, 0) = 0)"
)

MIRROR_COLUMNS = ("type", "sequence", "length", "species", "common_name", "patent",
                  "applications", "reference")


# ---------------------------------------------------------------------------
# Scaffold side
# ---------------------------------------------------------------------------

def scaffolds_from_source() -> list[dict[str, Any]]:
    """The eight clusters as the import script builds them, without touching a database.

    Going through the import module rather than reading the table keeps the tag vocabulary in
    one place: a route `TAG_COLUMNS` does not produce cannot appear here either.
    """
    clusters, _rows = scaffold_source.read_source()
    library_rows, _sequences = scaffold_source.build_rows(clusters)
    return library_rows


def scaffolds_from_db() -> list[dict[str, Any]]:
    import psycopg
    from psycopg.rows import dict_row

    from app.config import get_settings

    with psycopg.connect(get_settings().dsn, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT id, name, short_name, category, applicant, patent_family, species,
                   length_aa, aa_sequence, route_ids, max_evidence
              FROM scaffold_library
             ORDER BY id
            """
        ).fetchall()
    return list(rows)


def routes_on(scaffold: dict[str, Any]) -> list[str]:
    return list(scaffold.get("route_ids") or [])


def choose_route_defaults(
    scaffolds: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """`(route -> chosen scaffold, route -> every scaffold that admits it)`."""
    by_route: dict[str, list[dict[str, Any]]] = {}
    for scaffold in scaffolds:
        for route in routes_on(scaffold):
            by_route.setdefault(route, []).append(scaffold)

    chosen: dict[str, dict[str, Any]] = {}
    for route, members in by_route.items():
        pinned = ROUTE_DEFAULT_OVERRIDE.get(route)
        if pinned:
            match = next(
                (m for m in members if m["id"] == pinned or m["short_name"] == pinned), None
            )
            if match is None:
                raise RuntimeError(
                    f"route {route!r} is pinned to {pinned!r}, which admits no scaffold; "
                    f"the route admits {[m['short_name'] for m in members]}"
                )
            chosen[route] = match
            continue
        chosen[route] = sorted(
            members,
            key=lambda m: (
                -EVIDENCE_ORDER.get(m.get("max_evidence") or "", 0),
                len(routes_on(m)),
                m["short_name"],
            ),
        )[0]
    return chosen, by_route


def scenario_routes(route_defaults: dict[str, dict[str, Any]]) -> dict[str, str]:
    """`scenario -> route`, keeping only routes that hold a scaffold.

    `SCENARIO_ROUTE_HINT` is ordered by preference, so the first admitted route is the one a
    construct falls back to. A scenario whose every route is empty is left out, and the rows
    it covers keep pointing at the placeholder.
    """
    out: dict[str, str] = {}
    for scenario, routes in SCENARIO_ROUTE_HINT.items():
        for route in routes:
            if route in route_defaults:
                out[scenario] = route
                break
    return out


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------

def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def mirror_statements(scaffold: dict[str, Any]) -> list[str]:
    """The two statements that put one curated cluster into `backbone_proteins`.

    An insert guarded by a name test plus an unconditional update, rather than an upsert:
    `backbone_proteins` carries no unique constraint on `name`, and adding one to a table the
    project's own tooling created is not this script's call to make.
    """
    name = scaffold["short_name"]
    values: dict[str, Any] = {
        "type": "modified",
        "sequence": scaffold["aa_sequence"],
        "length": len(scaffold["aa_sequence"]),
        "species": scaffold.get("species"),
        "common_name": scaffold.get("name"),
        "patent": scaffold.get("patent_family"),
        "applications": ", ".join(
            ROUTES_BY_ID[r].name for r in routes_on(scaffold) if r in ROUTES_BY_ID
        ) or None,
        # Where the row came from, so a construct's binding can be traced back to the curated
        # cluster rather than only to a name that happens to match.
        "reference": f"scaffold_library:{scaffold['id']}",
    }
    insert_columns = ", ".join(("name", *MIRROR_COLUMNS))
    insert_values = ", ".join(
        [sql_literal(name), *(sql_literal(values[c]) for c in MIRROR_COLUMNS)]
    )
    assignments = ", ".join(f"{c} = {sql_literal(values[c])}" for c in MIRROR_COLUMNS)
    return [
        f"INSERT INTO backbone_proteins ({insert_columns})\n"
        f"     SELECT {insert_values}\n"
        f"      WHERE NOT EXISTS (SELECT 1 FROM backbone_proteins WHERE name = {sql_literal(name)});",
        f"UPDATE backbone_proteins SET {assignments} WHERE name = {sql_literal(name)};",
    ]


def rebind_statement(scenario_backbone: dict[str, str]) -> str:
    """One statement rebinding every placeholder row, keyed on the scaffold's name.

    Addressing the scaffold by name rather than by a resolved id is what lets the plan be
    produced without a database, and it keeps the statement valid whether or not the mirror
    has run yet — inside the same transaction the names are already visible.

    The shape is deliberate. Postgres will not let a statement reference the table it is
    updating from inside the FROM clause's join conditions, so every correlation to `constructs`
    sits in the SET list or the WHERE, and the linker — which may be NULL and therefore needs
    an outer join, not an inner one — is read through a scalar subquery rather than joined.
    """
    mapping = ",\n    ".join(
        f"({sql_literal(scenario)}, {sql_literal(short_name)})"
        for scenario, short_name in scenario_backbone.items()
    )
    still_placeholder = PLACEHOLDER.format(a="pb")
    return f"""UPDATE constructs c
   SET backbone_id   = b.id,
       full_sequence = b.sequence
                       || COALESCE((SELECT lk.sequence FROM linkers lk
                                     WHERE lk.id = c.linker_id), '')
                       || p.sequence
  FROM (VALUES
    {mapping}
  ) AS m(scenario, backbone_name),
       backbone_proteins b,
       peptides p,
       backbone_proteins pb
 WHERE m.scenario   = c.scenario
   AND b.name       = m.backbone_name
   AND p.id         = c.peptide_id
   AND pb.id        = c.backbone_id
   AND {still_placeholder};"""


def sequence_guard() -> str:
    """Bring `backbone_proteins`' id sequence up to its highest existing row.

    A row can be written with its id named explicitly, which leaves the sequence behind it:
    the table's own seed script does exactly that for the placeholder rows. Without this the
    first mirrored insert asks for an id already in use and the whole migration aborts on a
    primary-key collision. Setting a sequence to a value it already holds is a no-op, so this
    is safe to run every time.
    """
    return (
        "SELECT setval(pg_get_serial_sequence('backbone_proteins', 'id'),\n"
        "              COALESCE((SELECT MAX(id) FROM backbone_proteins), 1),\n"
        "              (SELECT COUNT(*) FROM backbone_proteins) > 0);"
    )


def build_plan(scaffolds: list[dict[str, Any]]) -> tuple[list[str], dict[str, str]]:
    route_defaults, _by_route = choose_route_defaults(scaffolds)
    scenario_map = scenario_routes(route_defaults)
    statements = [
        "BEGIN;",
        "",
        "-- 1. the curated clusters, where the constructs can reach them",
        sequence_guard(),
    ]
    for scaffold in scaffolds:
        statements.extend(mirror_statements(scaffold))
    statements += ["", "-- 2. every construct still on a placeholder, rebound by route"]
    statements.append(rebind_statement({s: route_defaults[r]["short_name"] for s, r in scenario_map.items()}))
    statements += ["", "COMMIT;"]
    return statements, scenario_map


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def report(scaffolds: list[dict[str, Any]]) -> None:
    route_defaults, by_route = choose_route_defaults(scaffolds)
    scenario_map = scenario_routes(route_defaults)

    print(f"scaffolds: {len(scaffolds)} clusters")
    print()
    print("route             evidence  routes  scaffold")
    print("-" * 76)
    for route in sorted(by_route):
        pick = route_defaults[route]
        for scaffold in sorted(
            by_route[route],
            key=lambda m: (-EVIDENCE_ORDER.get(m.get("max_evidence") or "", 0), m["short_name"]),
        ):
            mark = "  <-- default" if scaffold is pick else ""
            print(
                f"{route:17s} {scaffold.get('max_evidence') or '-':>4s}"
                f"{len(routes_on(scaffold)):>8d}  {scaffold['short_name']}{mark}"
            )
    print()
    print("scenario -> route -> scaffold")
    print("-" * 76)
    for scenario, route in scenario_map.items():
        print(f"  {scenario:16s} -> {route:17s} -> {route_defaults[route]['short_name']}")
    for scenario in SCENARIO_ROUTE_HINT:
        if scenario not in scenario_map:
            print(f"  {scenario:16s} -> no route holds a scaffold; rows keep the placeholder")
    print()
    empty = [r for r in ROUTES_BY_ID if r not in by_route]
    for route in empty:
        print(f"  route holding no scaffold: {route} ({ROUTES_BY_ID[route].name})")
    if ROUTE_DEFAULT_OVERRIDE:
        print(f"  pinned by override: {ROUTE_DEFAULT_OVERRIDE}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report the plan and print the statements; open no connection")
    parser.add_argument("--emit-sql", metavar="PATH", help="write the statements to PATH")
    parser.add_argument("--from-db", action="store_true",
                        help="read the clusters from scaffold_library instead of the source table")
    args = parser.parse_args()

    scaffolds = scaffolds_from_db() if args.from_db else scaffolds_from_source()
    report(scaffolds)

    statements, scenario_map = build_plan(scaffolds)
    if not scenario_map:
        print("no scenario resolves to a route that holds a scaffold; nothing to bind")
        return 1

    if args.dry_run:
        print("\n".join(statements))
        print("\ndry run; nothing written")
    else:
        import psycopg

        from app.config import get_settings

        with psycopg.connect(get_settings().dsn) as conn:
            for statement in statements:
                if statement.strip() in {"BEGIN;", "COMMIT;"}:
                    continue
                if statement.strip().startswith("--") or not statement.strip():
                    continue
                cur = conn.execute(statement)
                if cur.description is None and cur.rowcount >= 0:
                    if "UPDATE constructs" in statement:
                        print(f"rebound {cur.rowcount} constructs")
            conn.commit()
            rows = conn.execute(
                """
                SELECT c.direction, b.name AS backbone, count(*) AS n
                  FROM constructs c
                  LEFT JOIN backbone_proteins b ON b.id = c.backbone_id
                 GROUP BY c.direction, b.name
                 ORDER BY c.direction
                """
            ).fetchall()
        print()
        for direction, backbone, n in rows:
            print(f"  {direction:18s} {backbone}  {n}")

    if args.emit_sql:
        Path(args.emit_sql).write_text("\n".join(statements) + "\n", encoding="utf-8")
        print(f"wrote {args.emit_sql}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

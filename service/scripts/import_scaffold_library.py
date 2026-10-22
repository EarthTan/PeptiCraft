#!/usr/bin/env python3
"""Import the curated scaffold table into `scaffold_library` / `scaffold_library_sequences`.

Source: resouces/scaffold_database_2026-09-06/scaffold_sequence_database.tsv — 16 sequence
rows covering 8 protein clusters, 35 columns, written in Chinese because it is the primary
research record. (`resouces/` is where the reference material lives; the directory was named
`data/` until it was renamed, and the spelling of the new name is not a typo.)

Columns 31-35 are the expression-system recommendation, one set per sequence record: the host,
the vector the patent or paper actually records, the vector the source recommends, the basis
for that recommendation, and its URL. They are stored verbatim on the sequence row and, for the
cluster row, copied from the representative sequence — the longest one, which is the sequence
assembly actually uses. `expression_sequence_id` on the cluster row names which record that
copy came from, so the two grains never have to be guessed at.

Two layers go into the two tables:

  * Traceable-from-source. Every column that the TSV itself carries — the FASTA name, the
    sequence, its SHA-256, the applicant, product/use, potential uses, regulatory status,
    safety summary, evidence label, the experiment prose, both URLs and the confidence
    limits — is read from the TSV and never restated here. The Chinese applicant string
    stays as it is in `scaffold_library_sequences`; the cluster row carries the English
    rendering alongside it in `applicant`.
  * Curated at cluster level. The English name, short name, species phrasing, material
    forms, the consolidated product/use and evidence-limit prose, the registration
    numbers and the description are editorial and exist in no source column. They live in
    `CLUSTER_META` below.

`CLUSTER_META` used to be imported from `scripts/gen_backbones.py`. That module was the
generator for the old mock data layer and has since been deleted with it, which left this
script unable to start at all: it failed on `load_gen_backbones()` before reaching the
database. The metadata is inlined here so the import path no longer depends on a module
the project has retired.

    python3 service/scripts/import_scaffold_library.py --dry-run
    python3 service/scripts/import_scaffold_library.py
    python3 service/scripts/import_scaffold_library.py --target sqlite

Idempotent: every write is an upsert keyed on the natural key.

`--target sqlite` writes the same two tables into the local fixture database rather than the
remote instance, which is what makes the curated library visible on a machine that cannot
reach the project database. That copy is a development stand-in and reads the SQLite-shaped
tables: the schema there has no `updated_at`, and the list-valued columns hold JSON text
rather than arrays. Everything else is identical, and the parse is the same one both targets
share — so the two can never disagree about a sequence.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import OrderedDict
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parent
sys.path.insert(0, str(SERVICE_ROOT))

from app.config import get_settings  # noqa: E402

# --- source layout ----------------------------------------------------------
TSV_PATH = (
    REPO_ROOT / "resouces" / "scaffold_database_2026-09-06" / "scaffold_sequence_database.tsv"
)
SOURCE_VERSION = "2026-09-06"  # snapshot date of the scaffold dataset
EXPECTED_HEADER_LEN = 35
EXPECTED_SEQUENCE_ROWS = 16
EXPECTED_CLUSTER_ROWS = 8

# 0-based TSV column positions, used directly by the reader below.
C_RECORD_NO = 0
C_FASTA_NAME = 1
C_SEQ_ID = 2
C_LENGTH = 3
C_LENGTH_CHECK = 4
C_SHA256 = 5
C_SEQUENCE = 6
C_PATENT = 7
C_APPLICANT = 8
C_CLUSTER = 9
C_PRODUCT_USE = 10
C_POTENTIAL_USES_CN = 11
C_REGULATORY_STATUS = 17
C_SAFETY_SUMMARY = 18
C_EVIDENCE = 19
C_EXPERIMENT_GROUP = 20
C_EXPERIMENT_LEVEL = 21
C_SPECIFIC_EXPERIMENTS = 22
C_PRINCIPAL_RESULT = 23
C_RESULT_LOCATION = 24
C_EVIDENCE_LIMITATIONS = 25
C_FASTA_PATH = 26
C_PATENT_URL = 27
C_REGULATORY_URL = 28
C_CONFIDENCE_LIMITATIONS = 29
# Expression-system recommendation, columns 31-35 of the sheet (1-based), all populated for
# all sixteen records. Read verbatim: the wording carries its own scope limits.
C_EXPRESSION_SYSTEM = 30
C_EXPRESSION_VECTOR_RECORDED = 31
C_EXPRESSION_VECTOR_RECOMMENDED = 32
C_EXPRESSION_RATIONALE = 33
C_EXPRESSION_SOURCE_URL = 34

# The five column names as the sheet spells them, used only to verify the header still lines
# up with the positions above. A silently shifted column would put a vector in the host field.
EXPRESSION_HEADER = {
    C_EXPRESSION_SYSTEM: "推荐表达系统（依据来源）",
    C_EXPRESSION_VECTOR_RECORDED: "来源记载的表达载体/质粒",
    C_EXPRESSION_VECTOR_RECOMMENDED: "推荐表达载体/质粒",
    C_EXPRESSION_RATIONALE: "推荐依据与适用范围",
    C_EXPRESSION_SOURCE_URL: "表达系统/载体来源URL",
}

# The tag columns the source table carries, in column order, each paired with the route id it
# maps to. This is the only place the tag vocabulary is translated; `app/services/reference.py`
# declares the matching routes and reads `application_tag` back off them.
#
# The team's label dictionary declares four application tags and states that the old scene,
# subtype and delivery tags have been deleted. Hair care is not among the four. Its marking
# column is nevertheless still present in the table and still populated, so the column is read
# — the header check below covers all five positions — and deliberately mapped to no route.
# The consequence is that `route_ids` never contains `hair-coating`, which leaves that route
# holding no scaffold: the two clusters tagged Hair care were the only ones it had. The route
# itself stays declared in `reference.py`, so the interface shows it with an empty scaffold
# list rather than dropping it.
TAG_COLUMNS: list[tuple[int, str, str | None]] = [
    (12, "Topical appliance", "topical-film"),
    (13, "Mask patch", "mask-patch"),
    (14, "Hair care", None),
    (15, "Wound dressing", "wound-dressing"),
    (16, "Injectable filler", "injectable-filler"),
]

TAG_TO_ROUTE = OrderedDict(
    (tag, route) for _pos, tag, route in TAG_COLUMNS if route is not None
)

# Cluster-level editorial metadata, keyed by the first sequence record id of the cluster.
# Values are the English renderings the interface displays; the Chinese originals remain in
# `construct_cn` and in the sequence rows, so the two never have to be reconciled by hand.
CLUSTER_META: dict[str, dict[str, object]] = {
    "JINBO_HC8_CN103122027B_257aa": {
        "id": "jinbo-hc8-hc16",
        "name": "Recombinant humanised type III collagen (HC8 / HC16)",
        "shortName": "Jinbo HC8/HC16",
        "category": "recombinant-collagen",
        "applicant": "Shanxi Jinbo Biomedical Co., Ltd.",
        "species": "Tandem multimer of functional fragments from Homo sapiens COL3A1",
        "materialForms": ["lyophilized", "injectable-gel", "solution"],
        "productUse": (
            "Related platform products include recombinant type III humanised collagen "
            "lyophilised fibre, injectable gel and repair-class devices."
        ),
        "potentialUses": (
            "Platform-related applications: injectable lyophilised-fibre dermal filler for "
            "facial wrinkles, injectable gel for mid-face volume and contour correction, and "
            "wound and skin repair solutions or dressings. The correspondence between the "
            "sixteen-repeat construct and specific products has not been publicly confirmed."
        ),
        "evidenceLimits": (
            "Jinbo HC8/HC16 and the 16x repeat construct: in-patent data; the PDB entry is a "
            "related short functional domain, not a complete 480-501 aa model. | Jinbo "
            "HC8/HC16 and the 16x repeat construct: paper materials were supplied by the "
            "company and cannot substitute for clinical evaluation of a specific finished "
            "product. | Jinbo-related medical devices: public abstracts do not include the "
            "full registration testing and clinical reports; request them from NMPA or the "
            "company."
        ),
        "registrations": [
            "NMPA registration no. 20213130488 — recombinant type III humanised collagen "
            "lyophilised fibre, approved 2021",
            "NMPA registration no. 20253130751 — injectable gel, approved 2025 for mid-face "
            "volume and contour correction",
        ],
        "registrationNote": (
            "The registration numbers belong to this platform and its related material, not "
            "to the patent itself having been approved. Public abstracts do not include the "
            "full registration testing and clinical reports; those must be requested from "
            "NMPA or from the company."
        ),
        "blurb": (
            "Recombinant humanised type III collagen built from tandem repeats of a COL3A1 "
            "functional domain; the construct family behind two NMPA-registered collagen "
            "devices."
        ),
    },
    "JINBO_rhCollagenIII_16x_repeat_SEQID4_480aa": {
        "id": "jinbo-col3a1-16x",
        "name": "Recombinant humanised type III collagen, 30-aa COL3A1 domain x16",
        "shortName": "Jinbo COL3A1x16",
        "category": "recombinant-collagen",
        "applicant": "Shanxi Jinbo Biomedical Co., Ltd.",
        "species": "Sixteen tandem repeats of the Homo sapiens COL3A1 functional domain",
        "materialForms": ["lyophilized", "injectable-gel", "solution"],
        "productUse": (
            "Related platform products include recombinant type III humanised collagen "
            "lyophilised fibre, injectable gel and repair-class devices."
        ),
        "potentialUses": (
            "Platform-related applications: injectable lyophilised-fibre dermal filler for "
            "facial wrinkles, injectable gel for mid-face volume and contour correction, and "
            "wound and skin repair solutions or dressings. The correspondence between the "
            "sixteen-repeat construct and specific products has not been publicly confirmed."
        ),
        "evidenceLimits": (
            "Jinbo HC8/HC16 and the 16x repeat construct: in-patent data; the PDB entry is a "
            "related short functional domain, not a complete 480–501 aa model. | Jinbo "
            "HC8/HC16 and the 16x repeat construct: paper materials were supplied by the "
            "company and cannot substitute for clinical evaluation of a specific finished "
            "product. | Jinbo-related medical devices: public abstracts do not include the "
            "full registration testing and clinical reports; request them from NMPA or the "
            "company."
        ),
        "registrations": [
            "NMPA registration no. 20213130488 — recombinant type III humanised collagen "
            "lyophilised fibre, approved 2021",
            "NMPA registration no. 20253130751 — injectable gel, approved 2025 for mid-face "
            "volume and contour correction",
        ],
        "registrationNote": (
            "The registration numbers belong to the related platform and product. Whether the "
            "commercial product sequence is exactly the variant listed here requires "
            "confirmation from the company's batch records."
        ),
        "blurb": (
            "The same COL3A1 functional domain repeated sixteen times; the longer construct "
            "behind the platform's injectable gel."
        ),
    },
    "COLLAGEN_WUHAN_TRHCIII_1_SEQID1_225aa": {
        "id": "wuhan-trhciii-1",
        "name": "TRHCIII-1, triple-helix-like recombinant human collagen III",
        "shortName": "Wuhan TRHCIII-1",
        "category": "recombinant-collagen",
        "applicant": "Collagen (Wuhan) Biotechnology Co., Ltd.",
        "species": "Triple-helix-like fragment of recombinant human type III collagen (225 aa)",
        "materialForms": ["self-assembled-hydrogel"],
        "productUse": (
            "Self-assembling collagen fibre and hydrogel candidate for wound and "
            "tissue-engineering materials; no finished-product registration number explicitly "
            "tied to this sequence could be verified."
        ),
        "potentialUses": (
            "The patent proposes self-assembling collagen fibres or hydrogels for wound "
            "dressings, tissue repair and tissue-engineering scaffolds; no sequence-specific "
            "commercial product has been verified."
        ),
        "evidenceLimits": "Wuhan TRHCIII-1: in-patent only, with no independent atomic-level confirmation.",
        "registrations": [],
        "registrationNote": (
            "No finished-product registration number explicitly tied to this sequence could "
            "be verified."
        ),
        "blurb": (
            "A 225 aa triple-helix-like recombinant human type III collagen fragment that "
            "self-assembles into fibres or hydrogels."
        ),
    },
    "TRAUTEC_COL17_170801_SEQID2_233aa": {
        "id": "trautec-col17",
        "name": "Recombinant human type XVII collagen fragments 170801 / 170802",
        "shortName": "Trautec COL17",
        "category": "recombinant-collagen",
        "applicant": "Jiangsu Trautec Medical Technology Co., Ltd.",
        "species": "Homo sapiens COL17 fragments (not full-length transmembrane COL17)",
        "materialForms": ["lyophilized"],
        "productUse": (
            "Recombinant collagen lyophilised fibre (Kefuyan; models including CJ-XVII) for "
            "non-chronic wounds and post-procedure wound care."
        ),
        "potentialUses": (
            "The patent proposes scar and wound healing, dermal tissue repair, hair follicle "
            "repair and hair-growth or scalp care products; the related marketed platform "
            "includes sterile lyophilised fibre for post-procedure wound care. The "
            "correspondence between the constructs and specific products has not been "
            "confirmed."
        ),
        "evidenceLimits": (
            "Trautec COL17 170801/170802: in-patent; the fragments are not full-length "
            "transmembrane COL17. | Trautec Kefuyan: company-published registration "
            "information; the full technical review report is not public."
        ),
        "registrations": [
            "Jiangsu provincial registration no. 20232141168 — recombinant collagen "
            "lyophilised fibre (Kefuyan, models including CJ-XVII), class II medical device, "
            "for non-chronic wounds and post-procedure wound care",
        ],
        "registrationNote": (
            "The registered indication is wound care, not hair care. How the registered "
            "product formulation maps to each patent sequence version is not disclosed item "
            "by item on public pages."
        ),
        "blurb": (
            "Recombinant human type XVII collagen fragments; the construct family behind a "
            "provincial-registered wound-care dressing."
        ),
    },
    "YUSONG_SF4_SEQID1_62aa": {
        "id": "yusong-sf4-sf10",
        "name": "Short recombinant silk fibroin SF-4 / SF-10",
        "shortName": "Yusong SF-4/SF-10",
        "category": "silkworm-silk",
        "applicant": "Shanghai Yusong Biotechnology Co., Ltd.",
        "species": "GAGAGS-type silk fibroin repeat units (short constructs, 38 / 62 aa)",
        "materialForms": ["solution"],
        "productUse": "Candidate cosmetic ingredient and skin-care formulation.",
        "potentialUses": (
            "Topical cosmetics proposed in the patent: anti-ageing and anti-wrinkle products, "
            "skin repair including acne scars, sunburn or post-procedure repair, and "
            "anti-inflammatory or sensitive-skin products; also usable in wound-healing and "
            "tissue-repair materials."
        ),
        "evidenceLimits": (
            "The remaining E1/E2 patents only: where the full raw data is not public, the "
            "evidence label must not be upgraded."
        ),
        "registrations": [],
        "registrationNote": (
            "The application is published but not granted. No regulatory number explicitly "
            "matching these two sequences could be verified, and cosmetic filing is not "
            "equivalent to drug or device approval."
        ),
        "blurb": (
            "Short GAGAGS-repeat silk fibroin constructs (38 / 62 aa) proposed as cosmetic and "
            "skin-repair ingredients."
        ),
    },
    "BOLT_18B_repeat_SEQID2_315aa": {
        "id": "bolt-18b",
        "name": "Recombinant spider silk protein 18B",
        "shortName": "Bolt 18B",
        "category": "spider-silk",
        "applicant": "Bolt Threads, Inc.",
        "species": "Engineered spider silk repeat sequence (Bolt Threads)",
        "materialForms": ["film", "solution"],
        "productUse": (
            "Personal-care powders and film-forming or barrier-type skin-care formulations."
        ),
        "potentialUses": (
            "Proposed in the patent or already formulated: powder or gel cleansers and "
            "exfoliants, oil-control or purifying powders, topical creams and lotions, "
            "colour-cosmetic pigment carriers, and film-forming skin-barrier or anti-ageing "
            "creams."
        ),
        "evidenceLimits": (
            "Bolt 18B: not a registered drug or device with controlled clinical trials; sample "
            "sizes and blinding need to be checked against the original text."
        ),
        "registrations": [],
        "registrationNote": (
            "The patent application is published but not granted; no drug or device approval "
            "number could be verified. Ordinary US cosmetics usually carry no FDA premarket "
            "approval number."
        ),
        "blurb": (
            "A recombinant spider silk protein engineered for powder and film-forming "
            "personal-care formulations."
        ),
    },
    "eADF4_C16_repeat_unit_35aa": {
        "id": "amsilk-eadf4-c16",
        "name": "Engineered spider silk protein eADF4(C16)",
        "shortName": "AMSilk eADF4(C16)",
        "category": "spider-silk",
        "applicant": "AMSilk / entities related to Evolved By Nature",
        "species": "Engineered spider silk protein containing 16 C-module repeats",
        "materialForms": ["film", "fiber"],
        "productUse": (
            "Engineered silk protein material, subsequently used in hair-care and cosmetic "
            "formulations."
        ),
        "potentialUses": (
            "Platform-level and related silk protein compositions: shampoos, conditioners, "
            "leave-in hair products, styling gels, sprays and foams, hair oils, creams and "
            "serums, and anti-frizz or cuticle-coating products. The exact correspondence "
            "between eADF4(C16) and the end products has not been established."
        ),
        "evidenceLimits": "eADF4(C16): mainly cell-free and ex vivo evidence.",
        "registrations": [],
        "registrationNote": (
            "No drug or device approval number could be verified; ordinary cosmetics usually "
            "carry no FDA premarket approval."
        ),
        "blurb": (
            "Engineered spider silk protein with sixteen C-module repeats, developed for "
            "hair-care and cosmetic formulations."
        ),
    },
    "FHLC_SEQ_ID_NO_1": {
        "id": "juzi-fhlc",
        "name": "Human-like collagen FHLC, 1071 aa",
        "shortName": "Giant Biogene FHLC",
        "category": "recombinant-collagen",
        "applicant": "Platform related to Shaanxi Giant Biogene Biotechnology Co., Ltd.",
        "species": "Recombinant human-like collagen (full-length 1071 aa construct)",
        "materialForms": ["sheet", "solution"],
        "productUse": (
            "Recombinant collagen skin-repair products including the Kefumei human-like "
            "collagen dressing."
        ),
        "potentialUses": (
            "Marketed platform-level applications: recombinant collagen medical dressings and "
            "masks, liquid dressings, post-procedure or skin-repair products, and single-use "
            "topical repair essences and serums. The exact correspondence between the 1071 aa "
            "FHLC sequence and current products has not been confirmed."
        ),
        "evidenceLimits": (
            "Giant Biogene FHLC: whether the specific 1071 aa sequence matches current product "
            "batches has not been publicly confirmed batch by batch."
        ),
        "registrations": [
            "Shaanxi provincial registration no. 20152140026 — Kefumei human-like collagen "
            "dressing, class II medical device (this dressing platform has held class II device "
            "registration since 2011)",
        ],
        "registrationNote": (
            "Whether the specific 1071 aa sequence matches current product batches has not "
            "been publicly confirmed batch by batch."
        ),
        "blurb": (
            "A full-length 1071 aa human-like collagen; the platform behind a class II "
            "recombinant-collagen dressing."
        ),
    },
}


def read_source() -> tuple[OrderedDict, list[list[str]]]:
    """Read the TSV and group rows into clusters keyed by the cluster label in the table."""
    with open(TSV_PATH, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh, delimiter="\t"))
    header, data = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]

    if len(header) != EXPECTED_HEADER_LEN:
        raise RuntimeError(
            f"header has {len(header)} columns, expected {EXPECTED_HEADER_LEN}; the source "
            f"table changed shape and the column positions above need revisiting"
        )
    if header[C_SEQ_ID] != "序列记录ID" or header[C_SEQUENCE] != "氨基酸序列":
        raise RuntimeError(
            f"column {C_SEQ_ID} is {header[C_SEQ_ID]!r} and column {C_SEQUENCE} is "
            f"{header[C_SEQUENCE]!r}; expected the sequence id and sequence columns"
        )
    for pos, tag, _route in TAG_COLUMNS:
        if header[pos] != tag:
            raise RuntimeError(f"column {pos} is {header[pos]!r}, expected tag {tag!r}")
    for pos, name in EXPRESSION_HEADER.items():
        if header[pos] != name:
            raise RuntimeError(
                f"column {pos} is {header[pos]!r}, expected {name!r}; the expression "
                f"recommendation columns moved and the reader needs revisiting"
            )
    if len(data) != EXPECTED_SEQUENCE_ROWS:
        raise RuntimeError(f"expected {EXPECTED_SEQUENCE_ROWS} sequence rows, found {len(data)}")

    clusters: OrderedDict[str, list[list[str]]] = OrderedDict()
    for r in data:
        clusters.setdefault(r[C_CLUSTER], []).append(r)
    if len(clusters) != EXPECTED_CLUSTER_ROWS:
        raise RuntimeError(f"expected {EXPECTED_CLUSTER_ROWS} clusters, found {len(clusters)}")
    return clusters, data


def build_rows(clusters):
    """Produce the two row sets to upsert."""
    library_rows = []
    sequence_rows = []

    for label, recs in clusters.items():
        first = recs[0]
        key = first[C_SEQ_ID]
        meta = CLUSTER_META.get(key)
        if meta is None:
            raise RuntimeError(
                f"cluster {key!r} ({label}) has no entry in CLUSTER_META; add its English "
                f"name, applicant and curated prose there rather than inventing a name in "
                f"the database by hand"
            )

        tags = [tag for pos, tag, route in TAG_COLUMNS if route and first[pos].strip()]
        routes = [TAG_TO_ROUTE[t] for t in tags]
        evidence = first[C_EVIDENCE].strip()
        if not evidence:
            raise RuntimeError(f"cluster {label} carries no evidence label")

        members = []
        for r in recs:
            seq = r[C_SEQUENCE].strip()
            declared = int(r[C_LENGTH])
            if len(seq) != declared:
                raise RuntimeError(
                    f"{r[C_SEQ_ID]}: sheet length {declared} disagrees with the sequence "
                    f"length {len(seq)}"
                )
            if r[C_LENGTH_CHECK].strip() != "一致":
                raise RuntimeError(
                    f"{r[C_SEQ_ID]}: the sheet's own length check column reads "
                    f"{r[C_LENGTH_CHECK]!r}, not 一致"
                )
            members.append((r, seq))

        # Representative = the longest member, so the cluster row stores the sequence that
        # spans every functional element the shorter variants each cover only in part. It is
        # also the sequence assembly uses, which is why the cluster-level expression
        # recommendation is the representative's rather than a second editorial judgement.
        rep_row, rep_seq = max(members, key=lambda m: len(m[1]))

        if not rep_row[C_EXPRESSION_SYSTEM].strip():
            raise RuntimeError(
                f"cluster {label} carries no expression system on its representative sequence; "
                f"the sheet is expected to fill all five expression columns for every record"
            )

        library_rows.append({
            "id": meta["id"],
            "name": meta["name"],
            "short_name": meta["shortName"],
            "category": meta["category"],
            "construct_cn": label.strip(),
            "applicant": meta["applicant"],
            "patent_family": first[C_PATENT].strip() or None,
            "species": meta["species"],
            "length_aa": len(rep_seq),
            "aa_sequence": rep_seq,
            "sequence_count": len(members),
            "application_tags": tags,
            "route_ids": routes,
            "material_forms": list(meta["materialForms"]),
            "max_evidence": evidence,
            "product_use": meta["productUse"],
            "potential_uses": meta["potentialUses"],
            "evidence_limits": meta["evidenceLimits"],
            "registrations": list(meta["registrations"]),
            "registration_note": meta["registrationNote"],
            "description": meta["blurb"],
            "patent_source_url": (rep_row[C_PATENT_URL].strip() or None),
            "regulatory_evidence_url": (rep_row[C_REGULATORY_URL].strip() or None),
            "expression_system": rep_row[C_EXPRESSION_SYSTEM].strip() or None,
            "expression_vector_recorded": rep_row[C_EXPRESSION_VECTOR_RECORDED].strip() or None,
            "expression_vector_recommended": (
                rep_row[C_EXPRESSION_VECTOR_RECOMMENDED].strip() or None
            ),
            "expression_rationale": rep_row[C_EXPRESSION_RATIONALE].strip() or None,
            "expression_source_url": rep_row[C_EXPRESSION_SOURCE_URL].strip() or None,
            "expression_sequence_id": rep_row[C_SEQ_ID].strip() or None,
            "source_version": SOURCE_VERSION,
        })

        for r, seq in members:
            sequence_rows.append({
                "sequence_id": r[C_SEQ_ID],
                "scaffold_id": meta["id"],
                "fasta_filename": r[C_FASTA_NAME].strip() or None,
                "length_aa": len(seq),
                "aa_sequence": seq,
                "sha256": (r[C_SHA256].strip() or None),
                "product_use": r[C_PRODUCT_USE].strip() or None,
                "potential_uses": r[C_POTENTIAL_USES_CN].strip() or None,
                "regulatory_status": r[C_REGULATORY_STATUS].strip() or None,
                "safety_testing_summary": r[C_SAFETY_SUMMARY].strip() or None,
                "evidence_level": r[C_EVIDENCE].strip() or None,
                "experiment_group": r[C_EXPERIMENT_GROUP].strip() or None,
                "experiment_level": r[C_EXPERIMENT_LEVEL].strip() or None,
                "specific_experiments": r[C_SPECIFIC_EXPERIMENTS].strip() or None,
                "principal_result": r[C_PRINCIPAL_RESULT].strip() or None,
                "result_location": r[C_RESULT_LOCATION].strip() or None,
                "evidence_limitations": r[C_EVIDENCE_LIMITATIONS].strip() or None,
                "patent_source_url": r[C_PATENT_URL].strip() or None,
                "regulatory_evidence_url": r[C_REGULATORY_URL].strip() or None,
                "confidence_limitations": r[C_CONFIDENCE_LIMITATIONS].strip() or None,
                "expression_system": r[C_EXPRESSION_SYSTEM].strip() or None,
                "expression_vector_recorded": r[C_EXPRESSION_VECTOR_RECORDED].strip() or None,
                "expression_vector_recommended": (
                    r[C_EXPRESSION_VECTOR_RECOMMENDED].strip() or None
                ),
                "expression_rationale": r[C_EXPRESSION_RATIONALE].strip() or None,
                "expression_source_url": r[C_EXPRESSION_SOURCE_URL].strip() or None,
                "source_version": SOURCE_VERSION,
            })

    return library_rows, sequence_rows


LIBRARY_SQL = """
INSERT INTO scaffold_library (
    id, name, short_name, category, construct_cn, applicant, patent_family, species,
    length_aa, aa_sequence, sequence_count, application_tags, route_ids, material_forms,
    max_evidence, product_use, potential_uses, evidence_limits, registrations,
    registration_note, description, patent_source_url, regulatory_evidence_url,
    expression_system, expression_vector_recorded, expression_vector_recommended,
    expression_rationale, expression_source_url, expression_sequence_id,
    source_version, updated_at
) VALUES (
    %(id)s, %(name)s, %(short_name)s, %(category)s, %(construct_cn)s, %(applicant)s,
    %(patent_family)s, %(species)s, %(length_aa)s, %(aa_sequence)s, %(sequence_count)s,
    %(application_tags)s, %(route_ids)s, %(material_forms)s, %(max_evidence)s,
    %(product_use)s, %(potential_uses)s, %(evidence_limits)s, %(registrations)s,
    %(registration_note)s, %(description)s, %(patent_source_url)s,
    %(regulatory_evidence_url)s, %(expression_system)s, %(expression_vector_recorded)s,
    %(expression_vector_recommended)s, %(expression_rationale)s, %(expression_source_url)s,
    %(expression_sequence_id)s, %(source_version)s, now()
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    short_name = EXCLUDED.short_name,
    category = EXCLUDED.category,
    construct_cn = EXCLUDED.construct_cn,
    applicant = EXCLUDED.applicant,
    patent_family = EXCLUDED.patent_family,
    species = EXCLUDED.species,
    length_aa = EXCLUDED.length_aa,
    aa_sequence = EXCLUDED.aa_sequence,
    sequence_count = EXCLUDED.sequence_count,
    application_tags = EXCLUDED.application_tags,
    route_ids = EXCLUDED.route_ids,
    material_forms = EXCLUDED.material_forms,
    max_evidence = EXCLUDED.max_evidence,
    product_use = EXCLUDED.product_use,
    potential_uses = EXCLUDED.potential_uses,
    evidence_limits = EXCLUDED.evidence_limits,
    registrations = EXCLUDED.registrations,
    registration_note = EXCLUDED.registration_note,
    description = EXCLUDED.description,
    patent_source_url = EXCLUDED.patent_source_url,
    regulatory_evidence_url = EXCLUDED.regulatory_evidence_url,
    expression_system = EXCLUDED.expression_system,
    expression_vector_recorded = EXCLUDED.expression_vector_recorded,
    expression_vector_recommended = EXCLUDED.expression_vector_recommended,
    expression_rationale = EXCLUDED.expression_rationale,
    expression_source_url = EXCLUDED.expression_source_url,
    expression_sequence_id = EXCLUDED.expression_sequence_id,
    source_version = EXCLUDED.source_version,
    updated_at = now()
"""

SEQUENCE_SQL = """
INSERT INTO scaffold_library_sequences (
    sequence_id, scaffold_id, fasta_filename, length_aa, aa_sequence, sha256,
    product_use, potential_uses, regulatory_status, safety_testing_summary, evidence_level,
    experiment_group, experiment_level, specific_experiments, principal_result,
    result_location, evidence_limitations, patent_source_url, regulatory_evidence_url,
    confidence_limitations, expression_system, expression_vector_recorded,
    expression_vector_recommended, expression_rationale, expression_source_url,
    source_version, updated_at
) VALUES (
    %(sequence_id)s, %(scaffold_id)s, %(fasta_filename)s, %(length_aa)s, %(aa_sequence)s,
    %(sha256)s, %(product_use)s, %(potential_uses)s, %(regulatory_status)s,
    %(safety_testing_summary)s, %(evidence_level)s, %(experiment_group)s,
    %(experiment_level)s, %(specific_experiments)s, %(principal_result)s,
    %(result_location)s, %(evidence_limitations)s, %(patent_source_url)s,
    %(regulatory_evidence_url)s, %(confidence_limitations)s, %(expression_system)s,
    %(expression_vector_recorded)s, %(expression_vector_recommended)s,
    %(expression_rationale)s, %(expression_source_url)s, %(source_version)s, now()
)
ON CONFLICT (sequence_id) DO UPDATE SET
    scaffold_id = EXCLUDED.scaffold_id,
    fasta_filename = EXCLUDED.fasta_filename,
    length_aa = EXCLUDED.length_aa,
    aa_sequence = EXCLUDED.aa_sequence,
    sha256 = EXCLUDED.sha256,
    product_use = EXCLUDED.product_use,
    potential_uses = EXCLUDED.potential_uses,
    regulatory_status = EXCLUDED.regulatory_status,
    safety_testing_summary = EXCLUDED.safety_testing_summary,
    evidence_level = EXCLUDED.evidence_level,
    experiment_group = EXCLUDED.experiment_group,
    experiment_level = EXCLUDED.experiment_level,
    specific_experiments = EXCLUDED.specific_experiments,
    principal_result = EXCLUDED.principal_result,
    result_location = EXCLUDED.result_location,
    evidence_limitations = EXCLUDED.evidence_limitations,
    patent_source_url = EXCLUDED.patent_source_url,
    regulatory_evidence_url = EXCLUDED.regulatory_evidence_url,
    confidence_limitations = EXCLUDED.confidence_limitations,
    expression_system = EXCLUDED.expression_system,
    expression_vector_recorded = EXCLUDED.expression_vector_recorded,
    expression_vector_recommended = EXCLUDED.expression_vector_recommended,
    expression_rationale = EXCLUDED.expression_rationale,
    expression_source_url = EXCLUDED.expression_source_url,
    source_version = EXCLUDED.source_version,
    updated_at = now()
"""


# --- local SQLite target ----------------------------------------------------
#
# The two statements above are Postgres: `%(name)s` parameters, `now()`, and a `text[]` column
# taking a Python list through psycopg's adapter. None of that runs on the fixture, so the
# same write is expressed once more for that dialect. The column list is taken from the rows
# themselves rather than restated, so a column added to `build_rows` cannot end up in one
# statement and not the other.

LIBRARY_KEY = "id"
SEQUENCE_KEY = "sequence_id"

# Stored as JSON text in the fixture, the counterpart of the Postgres array columns.
JSON_FIELDS = frozenset({"application_tags", "route_ids", "material_forms", "registrations"})


def upsert_sql(table: str, columns: tuple[str, ...], key: str) -> str:
    """An upsert on `key` for the fixture tables, which carry no `updated_at`."""
    values = ", ".join(f":{c}" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != key)
    return (
        f"INSERT INTO {table} (\n    {', '.join(columns)}\n)\n"
        f"VALUES (\n    {values}\n)\n"
        f"ON CONFLICT ({key}) DO UPDATE SET\n    {updates}\n"
    )


def as_sqlite_rows(rows: list[dict]) -> list[dict]:
    """Copy the rows with the list-valued columns serialised, leaving the originals alone."""
    return [
        {
            k: (json.dumps(v, ensure_ascii=False) if k in JSON_FIELDS else v)
            for k, v in row.items()
        }
        for row in rows
    ]


def write_sqlite(path: str, library_rows: list[dict], sequence_rows: list[dict]) -> tuple[int, int]:
    """Upsert both row sets into the local fixture. Returns the two table counts."""
    library_sql = upsert_sql("scaffold_library", tuple(library_rows[0]), LIBRARY_KEY)
    sequence_sql = upsert_sql(
        "scaffold_library_sequences", tuple(sequence_rows[0]), SEQUENCE_KEY
    )
    with sqlite3.connect(path) as conn:
        conn.executemany(library_sql, as_sqlite_rows(library_rows))
        conn.executemany(sequence_sql, as_sqlite_rows(sequence_rows))
        conn.commit()
        lib_count = conn.execute("SELECT count(*) FROM scaffold_library").fetchone()[0]
        seq_count = conn.execute("SELECT count(*) FROM scaffold_library_sequences").fetchone()[0]
    return lib_count, seq_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dump", metavar="PATH", help="also write the parsed rows as JSON")
    parser.add_argument(
        "--target",
        choices=("postgres", "sqlite"),
        default="postgres",
        help="which database to write; sqlite is the local fixture stand-in",
    )
    parser.add_argument(
        "--sqlite-path",
        default=None,
        help="SQLite file to write, when --target is sqlite (default: the configured fixture)",
    )
    args = parser.parse_args()

    clusters, data = read_source()
    library_rows, sequence_rows = build_rows(clusters)

    print(f"source: {TSV_PATH.name}")
    print(f"  rows {len(data)} -> clusters {len(library_rows)} + sequences {len(sequence_rows)}")
    for lib in library_rows:
        print(
            f"  {lib['id']:22s} {lib['sequence_count']} seq  "
            f"{lib['max_evidence'] or '-':3s} {' / '.join(lib['route_ids'])}"
        )

    if args.dump:
        Path(args.dump).write_text(
            json.dumps({"library": library_rows, "sequences": sequence_rows},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"  dumped {args.dump}")

    if args.dry_run:
        print("dry run; nothing written")
        return 0

    settings = get_settings()

    if args.target == "sqlite":
        target = (
            Path(args.sqlite_path).expanduser() if args.sqlite_path else settings.sqlite_file
        )
        if not target.exists():
            print(
                f"{target} does not exist; build it first with scripts/build_local_db.py",
                file=sys.stderr,
            )
            return 1
        lib_count, seq_count = write_sqlite(str(target), library_rows, sequence_rows)
        print(
            f"committed to {target}: scaffold_library={lib_count} rows, "
            f"scaffold_library_sequences={seq_count} rows"
        )
        return 0

    # Imported here rather than at module level: the dry run, the JSON dump and the SQLite
    # target all work on a machine that has no Postgres driver and no database to talk to.
    import psycopg

    with psycopg.connect(settings.dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(LIBRARY_SQL, library_rows)
            cur.executemany(SEQUENCE_SQL, sequence_rows)
        conn.commit()
        lib_count = conn.execute("SELECT count(*) FROM scaffold_library").fetchone()[0]
        seq_count = conn.execute("SELECT count(*) FROM scaffold_library_sequences").fetchone()[0]
    print(f"committed: scaffold_library={lib_count} rows, "
          f"scaffold_library_sequences={seq_count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

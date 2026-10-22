# Recombinant Structural Protein Patent Data Pack — Database Import Handoff Instructions

> This package is used to import the patent sequence data in `patent_sequence_reorganized_2026-08-05/` into a relational database.
> Target database: **PostgreSQL** (adaptation to other databases is covered at the end of this document).
> Chinese version: [中文版](README-Import-Guide.cn.md)

---

## 1. Package contents

```
patent_db_handoff/
├── README-Import-Guide.md              ← this file
├── patent_db_schema.sql              ← table-creation DDL (includes DROP TABLE IF EXISTS; re-runnable)
├── group_record_mapping.csv          ← mapping of the 27 records ↔ 11 experiment groups (includes synthetic primary keys for rows without FASTA)
├── import_patent_db.py               ← one-step import script (reads TSV + FASTA, writes to the database)
└── source_data/                      ← original data package (copied as-is; do not modify)
    ├── README.md
    ├── scaffold_patents_sequence_guide.tsv        ← master table (27 rows)
    ├── scaffold_patents_experiment_details.tsv    ← experiment detail table (12 rows)
    ├── scaffold_patents_evidence_workbook.xlsx    ← human-readable edition (same source as the TSVs)
    └── fasta_downloads/                           ← 16 protein FASTA files
```

---

## 2. Prerequisites

1. An empty PostgreSQL database (or one that may accept being wiped).
2. Python 3.8+, with the driver installed:
   ```bash
   pip install psycopg2-binary      # or install psycopg (psycopg3)
   ```

---

## 3. Import steps (a single command)

```bash
python import_patent_db.py \
    --db "postgresql://user:password@host:5432/dbname" \
    --apply-schema
```

- Without `--apply-schema`, the script **only imports data**, assuming the tables already exist (run `patent_db_schema.sql` manually first if desired).
- With `--apply-schema`, the script **creates the tables and then imports the data** (it DROPs existing tables of the same name; back up first).
- The connection string can also be passed through an environment variable: `export DATABASE_URL="postgresql://..."`, followed directly by `python import_patent_db.py --apply-schema`.
- All path parameters have defaults pointing at locations relative to this package, so the script can be run directly from the package root.

When the script finishes it prints a **verification result**; confirm that it matches the "expected" values below before handing over.

---

## 4. Database design (how many tables?)

**Conclusion: two core tables plus one optional `groups` dimension table.**

| Table | Rows | Grain | Description |
|---|---|---|---|
| `patent_records` | 27 | 1 row = 1 sequence record or 1 patent/product record without a sequence | Master information; includes the `aa_sequence` text column. |
| `experiments` | 12 | 1 row = 1 (experiment group, evidence grade) entry | Experiment detail; the same group may have multiple rows (E1/E2/E4). |
| `groups` (optional) | 11 | 1 row = 1 experiment group | Dimension table, serving as the join hub between `patent_records` and `experiments`. |

**Why split into two tables rather than one?** The two TSVs have different grains: one experiment group (such as "Jinbo HC8/HC16 and 16-repeat constructs") corresponds to **5 sequence records + 2 experiment rows**. Merging them into a single table would either duplicate sequence information or lose the level-by-level E1/E2/E3/E4 experiment detail. Splitting the tables is the standard approach.

The two tables are linked through `group_key` (a short slug such as `jinbo_constructs` or `eadf4_c16`).

---

## 5. Four pitfalls to know about (already handled in the new script/mapping; for awareness only)

1. **The `Sequence record ID` of the 11 records without FASTA is empty** → they have no natural primary key. For these 11 rows the script takes a **synthetic primary key** from `group_record_mapping.csv` by `(applicant, patent_family)` (for example `BLOOMAGE_CN114805551A`), and assigns a `group_key`. Matching is normalized (commas removed, spaces collapsed, lower-cased) to tolerate variation.
2. **Yusong's 2 records (with FASTA, E2) are not among the 12 experiment groups** → their `group_key` is set to `NULL` (marked `unmapped` in the mapping table), and they take no part in group association.
3. **2 experiment groups have no corresponding sequence records**: `jinbo_devices` (a marketed medical device) and `trautec_kefuyan` (the finished product Kefuyan). They appear only in the `experiments` / `groups` tables, for the group-name-to-group-key mapping.
4. **The FASTA header of `FHLC_SEQ_ID_NO_1.fasta` carries pipe-separated metadata** (`>FHLC_SEQ_ID_NO_1|protein=...|length=...`); the prefix `FHLC_SEQ_ID_NO_1` is correct, and the script takes the ID as the first segment after `>`, so no special handling is required.

---

## 6. Expected verification results after import

```
patent_records total rows          : 27  (expected 27)
  of which contain aa_sequence    : 16  (expected 16, i.e. the 16 records with FASTA)
  of which group_key is NULL      : 2  (expected 2, i.e. Yusong)
experiments total rows             : 12  (expected 12)
groups total rows                  : 11  (expected 11)
dangling foreign keys (records.group_key with no matching groups): 0  (expected 0)
```

---

## 7. Adapting to other databases (non-PostgreSQL)

- **MySQL**: change `BIGSERIAL` in `patent_db_schema.sql` to `BIGINT AUTO_INCREMENT`, keep `TEXT`, and remove `GENERATED ALWAYS AS IDENTITY`; the `%s` placeholders in the script apply equally to MySQL (the placeholders are the same when psycopg is replaced by `pymysql`).
- **SQLite**: `INTEGER PRIMARY KEY AUTOINCREMENT`; the `%s` placeholders are the same; `CHECK` constraints are ignored by default in SQLite (which does not affect the import). `import_patent_db.py` currently connects only to the PostgreSQL driver, so switching databases requires changing the import in `get_conn`.

---

## 8. Troubleshooting

- `缺少 PostgreSQL 驱动` → see section 2 for installing psycopg2-binary.
- `实验组名未在映射表找到 group_key` → check whether "Patent / product group" in `source_data/scaffold_patents_experiment_details.tsv` exactly matches `group_name` in `group_record_mapping.csv` (it should already be aligned).
- `无 FASTA 记录未能在映射表精确匹配` → this indicates that the applicant/patent family of a record without a sequence does not match the mapping table; add a row to the CSV using the (applicant, patent) pair shown in the message.
- To re-run: simply execute the command with `--apply-schema` once more (it DROPs the tables and creates them again first).

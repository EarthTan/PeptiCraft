# Curated data

Reference data that belongs in version control, kept as files. It is the material the pipeline
and the reference libraries were built from, plus the curated results of that work.

This directory is not the peptide library. The 20,248,885 scored peptides, the 496 constructs and
the enrichment table live in the `igem_peptides` PostgreSQL instance and are read from there by
`../service/`. What is here is the part that has to survive as a file: sequences with their
provenance, evidence and application tags, and the scenario/delivery matrix the builder is
organised around.

## Scaffold sequence database

`scaffold_database_2026-09-06/` is the curated scaffold library: 16 sequences covering 8 proteins
— recombinant humanised type III collagen and its 16× repeat construct (Jinbo), a triple-helix
mimetic collagen III (Wuhan), recombinant type XVII collagen fragments (Trautec), short
recombinant silk proteins SF-4 and SF-10 (Yusong), recombinant spider silk 18B (Bolt Threads),
engineered spider silk eADF4(C16), and a human-like collagen FHLC (Giant Biogene).

The workbook carries the sequence, patent, applicant, construct, product use, potential
application, application tags, delivery tags, regulatory status, experimental results, evidence
limitations, source URL and full amino-acid sequence for each row, with the sequence's SHA-256
recorded so a later revision can be checked against it. Sixteen FASTA files sit beside it, one
per sequence, and every one was verified against the length declared in the table.

The 16 records are the rows `../service/scripts/import_scaffold_library.py` reads to populate
`scaffold_library` and `scaffold_library_sequences`. `scaffold_database_2026-09-06/README.md`
holds the deduplication decisions, the FASTA whitelist, and the per-cluster tag counts.

## Patent source packs

`patent_sequence_reorganized_2026-08-05/` holds the patent material the scaffold database was
assembled from: the individually split FASTA files, an evidence workbook, a sequence guide, an
experiment-detail table, and a self-contained import bundle (`patent_db_handoff/`) carrying its own
schema, importer and mapping file.

Each record is graded on how far its evidence actually goes, on a five-level scale that runs from
cell-free physicochemical work (E1) through cell assays (E2), animal studies (E3) and human or
controlled clinical use (E4) to regulatory review and post-market data (E5). The label on a row
is the highest level that could be verified, not a claim that every lower or higher stage was
carried out, and a patent's own statement of effect is not treated as independent validation.
Regulatory status was checked through 2026-08-05, and "not verified" is not evidence of absence.

`patent_sequence_reorganized_2026-08-05/README.md` describes the pack. One discrepancy is worth
recording: that README's file list names a `scaffold_patents_sequence_master.tsv` which is not
present in the folder — the workbook and the two TSVs are what the pack actually contains.

## Scenario and delivery matrix

`scaffold_scenario_driven_table.csv` pairs each using scenario with a delivery method, 14 rows
over four columns: using scenario, scenario subtype, delivery, and delivery subtype. It is the
index the construct builder follows when it narrows scaffolds by application route. The five
application routes the service exposes come from `../service/app/services/reference.py`; where the
two disagree, the service is authoritative.

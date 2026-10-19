# Curated data

Reference data that must be retained under version control, kept as files. It is both the build material for the pipeline and the reference libraries, and the organized outcome of that work.

This directory is not the peptide library. The 20,248,885 scored peptides, the 496 constructs, and the score tables all live in the `igem_peptides` PostgreSQL instance, from which `../service/` reads them. What remains here is the part that must persist as files: sequences with their provenance, evidence, and application tags, and the scenario/delivery matrix by which the builder organizes them.

## Scaffold sequence library

`scaffold_database_2026-09-06/` is the curated scaffold library: 16 sequences covering 8 proteins—recombinant humanized type III collagen and its 16-repeat construct (Jinbo), triple-helix collagen III mimetic (Wuhan), recombinant type XVII collagen fragments (Trautec), short recombinant silk fibroin proteins SF-4 and SF-10 (Yusong), recombinant spider silk 18B (Bolt Threads), engineered spider silk eADF4(C16), and human-like collagen FHLC (Giant Biogene).

The workbook preserves, for each row, the sequence, patent, applicant, construct, product use, potential application, application tag, delivery tag, regulatory status, experimental results, evidence limitations, source link, and full amino acid sequence, and records the sequence's SHA-256 so that later revisions can be checked. Beside it sit 16 FASTA files, one per sequence, each verified against the length declared in the table.

These 16 records are exactly the rows that `../service/scripts/import_scaffold_library.py` reads and writes into `scaffold_library` and `scaffold_library_sequences`. `scaffold_database_2026-09-06/README.md` preserves the deduplication decisions, the FASTA whitelist, and the tag counts for each cluster.

## Patent source data pack

`patent_sequence_reorganized_2026-08-05/` holds the patent material from which the scaffold database was assembled: individually split FASTA files, an evidence workbook, a sequence guide, an experiment detail table, and a self-contained import package (`patent_db_handoff/`) that carries its own schema script, import script, and mapping file.

Each record is graded by the highest level the evidence actually reaches, on a five-level scale: from cell-free physicochemical work (E1), through cell experiments (E2), animal experiments (E3), human use or controlled clinical studies (E4), to regulatory review and post-market data (E5). The label on a row is the highest level that could be verified, and does not mean that every lower or higher level was performed; effects stated in the patents themselves also do not count as independent validation. Regulatory status was verified through 2026-08-05, and "not verified" does not mean that no such record exists.

`patent_sequence_reorganized_2026-08-05/README.md` describes this package. One discrepancy is worth recording: that README's file list includes a `scaffold_patents_sequence_master.tsv`, but no such file is in the directory—what the package actually contains is the workbook and two TSVs.

## Scenario and delivery matrix

`scaffold_scenario_driven_table.csv` pairs each use scenario with one delivery method, in four columns and 14 rows: use scenario, scenario subclass, delivery method, delivery subclass. This index is what the builder relies on when narrowing scaffolds by application route. The five application routes that the service exposes come from `../service/app/services/reference.py`; where the two disagree, the service prevails.

# Protein Scaffold Patent and Sequence Database

> Chinese version: [中文版](README.cn.md)

This directory is the deduplicated version curated from five existing data tables and FASTA files. The database contains only the specified 16 sequences, covering 8 proteins in total.

1.	Jinbo — recombinant humanized type III collagen
2.	Jinbo — recombinant humanized type III collagen with 16 repeats of the 30-aa COL3A1 functional domain;
3.	Wuhan — TRHCIII-1, a 225 aa triple-helix-like recombinant human collagen III;
4.	Trautec — recombinant human type XVII collagen fragments 170801/170802;
5. 	Yusong — short recombinant silk fibroin proteins SF-4/SF-10;
6. 	Bolt Threads, Inc. — recombinant spider silk protein 18B;
7. 	AMSilk / Evolved By Nature-related entities — eADF4(C16) engineered spider silk protein;
8. 	Giant Biogene — human-like collagen FHLC, 1071 aa)

Each construct occupies one row in the master table.

## File structure

- `scaffold_sequence_database.xlsx`&`scaffold_sequence_database.tsv`: the merged master workbook.
- `fasta/`: 16 whitelisted FASTA files.

The workbook contains the following sheets:

- `主数据库`: sequence, patent, applicant, construct, product use, potential application, scenario tag, delivery tag, regulatory status, experimental results, evidence limitations, source URL, and full amino acid sequence.
- `实验证据`: the experiment groups related to the selected sequences and the locations of their results; excludes the Bellafill and BOTOX comparison items.
- `标签字典`: definitions of the V3 use-scenario and delivery tags.
- `证据分级`: E1–E5 and the grading rules.
- `来源与去重`: use of the five source files and the deduplication decisions.

## Main improvements
- The former scenario, subclass, delivery method, and delivery subclass tags have all been removed.
- They are replaced by four filterable application columns: film-forming coating, Mask patch, Wound dressing, Injectable filler.
- The tag dictionary has also been reduced to these four items.
Current tag counts:
- Film-forming coating: 2 entries
- Mask patch: 3 entries
- Wound dressing: 4 entries
- Injectable filler: 1 entry
Repeat units, purified-tag versions, and constructs lacking application evidence are left blank and do not inherit the tags of the parent protein.
## FASTA whitelist

1. `JINBO_HC8_CN103122027B_257aa.fasta`
2. `JINBO_HC16_CN103122027B_501aa.fasta`
3. `JINBO_rhCollagenIII_16x_repeat_SEQID4_480aa.fasta`
4. `JINBO_TEV_rhCollagenIII_16x_486aa.fasta`
5. `JINBO_rhCollagenIII_16x_plus_tail_490aa.fasta`
6. `COLLAGEN_WUHAN_TRHCIII_1_SEQID1_225aa.fasta`
7. `TRAUTEC_COL17_170801_SEQID2_233aa.fasta`
8. `TRAUTEC_COL17_170802_SEQID3_466aa.fasta`
9. `TRAUTEC_COL17_STREP_170801_HIS6_SEQID4_249aa.fasta`
10. `YUSONG_SF4_SEQID1_62aa.fasta`
11. `YUSONG_SF10_SEQID2_38aa.fasta`
12. `BOLT_18B_repeat_SEQID2_315aa.fasta`
13. `BOLT_18B_SEQID1_945aa.fasta`
14. `eADF4_C16_repeat_unit_35aa.fasta`
15. `eADF4_C16_560aa.fasta`
16. `FHLC_SEQ_ID_NO_1.fasta`

All sequences have been checked by comparing the actual residue count in the FASTA with the length in the table, and all 16 agree. The master table also stores the full amino acid sequence and the sequence SHA-256, to facilitate later version verification.

## Merge and deduplication principles

- `Scaffold V3` in `scaffold_application_tags_v3.xlsx` is taken as the latest Chinese master data.
- `scaffold_patents+sequence+delivery+scenario_v3.tsv` matches the V3 master table cell by cell, so it was not imported again.
- The experiment details and evidence grading are retained from `scaffold_patents_evidence_workbook.xlsx`. Its `序列主表` is an old copy and does not overwrite V3.
- The duplicated Chinese and English fields of `scaffold_patents_sequence_guide.tsv` are not retained; the only `Potential application` information in it has been translated into Chinese and merged into the master table's `潜在应用（中文整合）`.
- `scaffold_patents_experiment_details.tsv` is an English copy of the experiments, and its quotation and tab structure is corrupted, so it was not imported directly; the corresponding information is provided by the Chinese experiment table in the evidence workbook.
- Records without a reliable FASTA, mixtures, comparison items, and records not on the whitelist did not enter the new database.

## PDB/CIF note

This directory contains no PDB or CIF files, so the master database has no `PDB/CIF accession` column, and structure entries are not treated as locally available files.

Historical sources recorded 6A0A and 6A0C, which are trimeric structures of approximately 30 aa functional domains related to the Jinbo constructs, not atomic models of the complete HC8, HC16, or 480–501 aa constructs. Where these identifiers appear in the experiment notes, they indicate only a location in the source literature or database.

## Usage limitations

- The original verification date for regulatory information is 2026-08-05; "not verified" does not mean that it does not exist.
- Where the correspondence between a patent sequence and a commercial product or specific lot has not been publicly confirmed, the qualifiers of the original material are retained.
- E1–E5 indicates the highest evidence level that can be verified, and does not mean that all experiments below or above it have been completed.
- The English labels in the tag dictionary are controlled-vocabulary names, not a translated copy standing alongside the Chinese master table.

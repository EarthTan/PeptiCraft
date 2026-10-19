# Recombinant Structural Protein Patent Data Pack

This folder summarizes sequence, product, regulatory-status, and experimental-evidence information for patents involving recombinant collagen, silk, elastin, and related structural proteins.

## File Structure

- `scaffold_patents_sequence_master.tsv`  
  Main information table. Each row represents a FASTA sequence or a patent/product for which no unique sequence was available. The first column is the FASTA filename. The table also includes patents, products, regulatory identifiers, experiments, evidence levels, and PDB/CIF accessions.

- `scaffold_patents_experiment_details.tsv`  
  Experiment-detail table describing the tests performed, principal findings, where the results can be found, and important limitations.

- `scaffold_patents_evidence_workbook.xlsx`  
  Human-readable Excel workbook containing three sheets: sequence master table, experiment/result locations, and evidence-level guidance.

- `fasta_downloads/`  
  Individually separated protein FASTA files. No FASTA is generated for records lacking a reliable unique sequence, representing complex mixtures, or unsuitable for distribution.

- `preview_*.png`  
  Layout previews of the Excel sheets, used only for quality assurance.

## Experimental Evidence Levels

- **E1: purified-protein, physicochemical, or cell-free experiments**, such as purity, mass spectrometry, circular dichroism, thermal stability, self-assembly, or material testing.

- **E2: cell-based experiments**, such as cytotoxicity, adhesion, proliferation, migration, or gene-expression assays.

- **E3: animal experiments**, including toxicology, safety, tissue repair, degradation, or efficacy studies in animal models.

- **E4: human use or controlled clinical studies**, including volunteer-use studies or controlled trials, without necessarily implying regulatory approval.

- **E5: regulatory review, controlled clinical evidence, and post-market safety data**, indicating formal regulatory evaluation or approval and associated clinical or post-market evidence.

The assigned label represents the highest evidence level that could be verified. It does not mean that every lower or higher evidence stage has been completed. Patent claims should not automatically be treated as independently validated results.

Regulatory information checked through **2026-08-05**. “Not verified” does not prove that no corresponding record exists.

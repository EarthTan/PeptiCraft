# PeptiCraft 1.x — Silk-Fibroin Fusion Protein Design
## Master Reference Document

---

## About this document

This is the base document for the work contained in the `iGEM-silk` repository, which covers versions 1.1 through 1.4 of the PeptiCraft design pipeline. It is written to be the single most complete account of that work, so that every other submission document — wiki pages, parts descriptions, video scripts, presentation material, judge-facing summaries — can be produced by excising, condensing or re-pointing the material assembled here rather than by returning to the source code.

The document is organised so that any section can be read on its own. Terms are defined where they first appear rather than collected into a glossary, on the assumption that a reader works through the material linearly. Quantitative claims are stated with the version and the round they belong to, because the four versions operate on different data at different scales and a number quoted without that context will usually be wrong somewhere else.

Where an internal record and a later record disagree, the later and more specific record is used and the disagreement is stated rather than silently resolved. A short list of open items at the end collects the questions that no version of the pipeline has settled.

---

## 1. The problem

### 1.1 Scientific objective

A short peptide with a desirable biological activity is not, by itself, a product. Its activity is real but its physical behaviour is poor: a free peptide of ten to thirty residues has essentially no structural stability, is degraded quickly by proteases in any biological fluid, cannot be spun, cast or gelled into a material, and diffuses away from the site where it is needed.

The working hypothesis of this project is that a functional peptide can be rescued by fusing it to a structural protein. The fusion protein inherits the mechanical and material behaviour of the scaffold — film formation, fibre formation, gelation, mechanical strength — and the peptide is carried along with it. The two halves are joined by gene fusion, which means the product is a single recombinant polypeptide that can be expressed, purified and processed as one molecule rather than as a peptide loaded into a carrier.

The target application is topical and cosmetic-material use: functional skincare and dressing products in which the antioxidant or anti-melanogenic activity of the peptide is delivered by a silk-based material that stays where it is applied. The project deliberately restricts itself to non-systemic delivery.

### 1.2 Why silk fibroin

Silk fibroin was chosen as the scaffold for four reasons that operate at different levels.

Its mechanical behaviour comes from sequence rather than from a folded globular structure. The protein is built from short repeating units — principally glycine-alanine-glycine-alanine segments that stack into crystalline β-sheet, alternating with glycine-glycine-any-residue segments that form an amorphous, extensible matrix. That alternation gives silk its unusual combination of tensile strength and toughness. It also means the material properties survive a great deal of sequence editing, because the property comes from the statistical pattern of the repeats rather than from a single fragile fold.

It is biocompatible and degrades through ordinary proteolytic routes, so a silk-based implant or dressing does not leave a persistent foreign body.

It has an established recombinant expression route. Silk fibroin and silk-like proteins have been expressed in *Escherichia coli* in the published literature, which makes the wet-lab half of the project tractable rather than speculative.

It self-assembles. Silk fibroin forms films and fibres under mild solvent conditions, which is what allows a liquid formulation to become a coating or a membrane without a chemical cross-linking step.

The scaffold sequence actually used throughout versions 1.2 and 1.4 is the recombinant silk protein `FibLNT8-10xRep-FibHCT`, 372 residues as synthesised: the N-terminal domain of *Bombyx mori* fibroin, ten glycine-rich repeats characteristic of the silk C-terminal region, and a C-terminal segment that itself carries a histidine tag. The scaffold's own C-terminal tag is removed during construct assembly so that it does not duplicate the purification tag added at the end of every construct, leaving a 364-residue scaffold used without exception by all 250 final constructs of version 1.4.

### 1.3 The three-part construct

Every construct built by any version of this pipeline is one assembly of three sequence elements, followed by a purification tag.

**The functional peptide** carries the activity. The project works in the 3-to-30-residue window. The upper bound is not a biological choice but a hard constraint imposed by the prediction models: several of the tools used, including the cell-penetration predictors, cannot accept a longer sequence, and the preprocessing step therefore discards everything outside the window before any scoring happens. Choosing short peptides over full-length functional proteins has four consequences, all of them favourable: solid-phase chemical synthesis is cheap at this length; small peptides penetrate tissue and cell membranes far better than large proteins, which matters for any application that must reach a cell; short peptides are generally less immunogenic; and a short peptide can be introduced by gene fusion with no chemical coupling step. The cost is that the peptide alone has neither stability nor material behaviour, which is the whole reason a scaffold is needed.

**The scaffold protein** supplies the material behaviour and determines what physical form the product can take — solution, gel, sponge, fibre or film. This is why the scaffold is treated as a decision made by the application rather than a free parameter: the choice of product form and the choice of scaffold are the same decision seen from two sides.

**The linker** is a short sequence joining the two, whose only job is spatial. Without it, a peptide placed directly against the scaffold surface risks one of two failures: the peptide is buried by a scaffold domain and its active site cannot reach its substrate, or the peptide interferes with the folding of the scaffold and degrades the mechanical behaviour that was the point of the scaffold in the first place. Two linker chemistries are used. A flexible linker is a repeat of glycine-glycine-glycine-glycine-serine (`GGGGS`): glycine has no side chain and is the most conformationally free residue, serine is small and polar and keeps the chain soluble, and the net effect is to leave both ends free to move. A rigid linker is based on the repeat glutamic acid-alanine-alanine-alanine-lysine (`EAAAK`), in which the negative glutamate and the positive lysine form a salt bridge that locks the segment into an α-helix and fixes the distance between the two ends. The two are not interchangeable; choosing the wrong one destroys the property the linker was added for.

The three parts are coupled, which is what makes the design problem hard rather than merely tedious. Changing the peptide changes the hydrophobicity and charge distribution of the whole fusion protein and therefore its tendency to aggregate. Changing the scaffold changes the chemical environment the peptide sits in and therefore its apparent activity. Changing the linker changes the relative orientation of the two ends. This is a joint selection problem over a combinatorial space, not three independent optimisations, and the pipeline's structure — enumerate linkers exhaustively, rank peptides by prediction, narrow scaffolds by application — is a way of decomposing an intractable space into three tractable ones.

### 1.4 Position in the PeptiCraft lineage

The work in this repository is the first of three stages of the same project, and the numbering used here is the lineage's own.

**Version 1.x (this repository)** established that the funnel works. It began as a pipeline for one function — antioxidant activity — on silk fibroin, and it converged over four iterations on a screening architecture that the later platform inherited wholesale. Its deliverables are a working screening pipeline and a ranked set of candidate constructs. There is no user interface and no consideration of being used by anyone other than the team.

**Version 2.0 (the PeptiCraft platform)** abstracted that architecture into a reusable platform: the search space widened to roughly twenty million peptides, the functional directions widened from one to four, the scaffold library widened from a single silk construct to eight protein clusters, and the whole thing was given a browser interface. Version 2.0 produces no new predictions; it organises the results of the pipeline stage into a guided application.

Two further repositories belong to the project but not to the 1.x lineage. One holds the pipeline run at platform scale, together with the schema, import scripts and result archives behind the 2.0 database. The other holds the evidence base: for each of the eighteen predictive tools evaluated, its provenance, training data, reproduction record and applicable range, and the tool-by-tool conclusions that determined which tools could serve as hard gates, which as ranking signals and which only as advisory reports.

The single most important continuity between 1.x and 2.0 is methodological, and it was decided here. Three rules set in version 1.4 were carried forward without modification: safety attributes are hard vetoes and never enter a weighted average; each metric is used in exactly one place in the pipeline; and composite weights are computed from the data rather than configured by hand. The second half of that list — the platform's route-derived weighting, its veto-gate semantics and its refusal to present `null` as zero — is a direct consequence of decisions taken in this repository.

---

## 2. The four versions at a glance

| | **1.1** (`stages`) | **1.2** (`stages2`) | **1.3** (`stages3`) | **1.4** (`stages4`) |
|---|---|---|---|---|
| Input | 1,843 antioxidant peptides | 1,081,772 sequences | 849,416,450 sequences | 19,890,021 candidates |
| Output | 107 peptides surviving hard filters | 150 constructs (90 Top + 60 Bottom) | 19,890,021 candidates in DuckDB | 250 constructs (Top 150 + Bottom 100) |
| Rounds | 6 phases | 8 rounds (0–7) | 6 stages planned, 1 executed | 8 rounds (0–7) + AlphaFold3 round 8 |
| State | CSV hand-off, per-stage directories | CSV hand-off, `common.py` utilities | DuckDB, 15 tables, checkpoint/resume | DuckDB, 30+ tables, checkpoint/resume |
| Selection logic | Threshold, then rank, then weighted average | Fixed hand-assigned weights throughout | Variance-aware weighting introduced | Hierarchical: one criterion per round |
| Safety handling | Hard filter at stage one | Hard filter at stage one, but weighted into the composite later | Hard filter | Hard veto, never weighted |
| Antioxidant score | One of several weighted terms | Reused across rounds 1–7 | Round 1 split only | Round 1 split only |
| Structure prediction | ESMFold (planned), AlphaFold3 (planned) | OmegaFold only | OmegaFold planned | OmegaFold (250) + AlphaFold3 (20) |
| Status | Code written, partially run | Complete | Stage 0 complete, stage 1 ready, superseded | Complete |
| Wall-clock | seconds to minutes | ~6.5 h | 98.7 min for stage 0 alone | ~65 h |

The four versions are not four attempts at the same thing. Versions 1.1 and 1.2 are attempts to make a funnel run at all. Version 1.3 is an attempt to make the funnel scale to the billion-sequence range, and it is the version that introduced the measurement apparatus — variance-aware weighting, DuckDB state, on-demand service startup — without itself reaching the end of the funnel. Version 1.4 is the version that fixed the two design errors version 1.2 had exposed, and it is the only version whose full output is treated as a result.

---

## 3. Version 1.1 — the first pipeline

### 3.1 What it was

The first pipeline was scoped to a single question: from a pool of a few thousand peptides already annotated as antioxidant, which ones are safe enough and promising enough to justify building a fusion construct around. The input was 1,843 antioxidant peptides assembled from two source tables. The pipeline was written as six orchestrated phases and seven stage scripts.

### 3.2 The design

The phase structure followed one governing rule, which every later version inherited: **put the cheap work first.** The reasoning is arithmetic rather than aesthetic. A tool that processes two thousand sequences per second and a tool that processes twenty-five per second differ by a factor of eighty; on twenty-five thousand sequences that is the difference between under a minute and several hours. Ordering by throughput rather than by conceptual importance is therefore not a stylistic preference but the main determinant of whether a run finishes.

Phase one applied the three hard filters. Two of them are effectively free — toxicity prediction and allergenicity prediction are CPU-bound, millisecond-scale operations on one- and two-megabyte models — and the third, haemolysis prediction, requires loading a fine-tuned language model of about 1.5 GB but is otherwise cheap. Running them first costs seconds and removes a large fraction of the pool before anything expensive touches it.

Phase two scored the survivors on several properties in parallel and combined them into a weighted total, using hand-assigned weights. The design document assigned 0.50 to antioxidant prediction, 0.20 to B-cell epitope prediction, 0.15 to cell-penetration prediction, 0.10 to immunogenicity in the inverse direction, and 0.05 to the graph-based cell-penetration predictor. Thermal stability was left unweighted and therefore, on the arithmetic, excluded from the ranking.

Phase three optionally added thermal stability on the surviving top flight. Phases four through six enumerated constructs, predicted their three-dimensional structure, and evaluated the structures for surface exposure and aggregation propensity.

The phase design also carried the project's first explicit treatment of GPU memory as a scheduling constraint. A single card was available, so the plan was to load services in successive batches, each batch sized to stay under the card's capacity, and to stop every other GPU service before a structure prediction run, because the structure predictors lock the device rather than merely occupying memory on it.

### 3.3 The engineering decisions worth carrying forward

Three decisions made at this stage survived into the final version and are stated here because they explain why the later pipeline is shaped the way it is.

**Scripts are independent and file state is the memory.** Each stage is a standalone runnable module with its own input, output and parameters, and each writes a report describing what it did and why. The reason is that the work is executed across many sessions by an agent with a bounded context, so state has to live on disk rather than in a conversation. The convention it produced — a status pointer at a fixed path, per-stage directories, a passed list and a failed list with the elimination reason recorded per row, and a timestamped snapshot of the status file at every change — is the ancestor of the checkpoint tables in versions 1.3 and 1.4.

**Every elimination is recorded with its cause.** Discarded candidates are written out, not dropped, with the tool and the score that removed them. This is what makes the funnel auditable after the fact and is the reason the later versions can state a rejection rate per round rather than only an overall one.

**Structure prediction is treated as the ceiling.** Even in version 1.1 the plan identified three-dimensional structure generation as the step that determines the total cost of a run, and chose the cheapest predictor that could do the job while reserving a high-accuracy predictor for a handful of final candidates. The reasoning held: the tool that would have been used for the bulk of the work had to handle sequences of several hundred residues, and the highest-accuracy tool at the time could not do so at any acceptable rate.

### 3.4 What it produced

The phase-one hard filters ran on the 1,843-peptide input and produced 107 survivors: 656 peptides were removed for predicted toxicity, 1,077 for predicted allergenicity, and 3 for predicted haemolysis. That single result is the clearest possible illustration of the funnel's premise — more than 94% of an already-curated antioxidant peptide set fails a safety criterion.

The remaining phases were written but not all executed, because the project moved on to a scaled-up pipeline rather than completing a run whose ceiling was a few hundred constructs. Version 1.1's contribution is its design: the funnel order, the cost model, the GPU-memory discipline, the file-as-memory convention and the recorded-elimination rule.

---

## 4. Version 1.2 — the production pipeline

### 4.1 What it was

Version 1.2 was the first pipeline to run end to end on real data. It took 1,081,772 candidate sequences through eight rounds and produced 150 assembled constructs, in about six and a half hours of wall-clock time. It introduced a shared utilities module so that the four rounds' worth of duplicated client code and file handling collapsed into one implementation, and it introduced a checkpoint file so that a run interrupted by a service failure could resume rather than restart.

### 4.2 Round structure

| Round | Function | Input → output | Time |
|---|---|---|---|
| 0 | Integration, length filter, deduplication | 1,081,772 → 1,055,116 | ~30 s |
| 1 | Lightweight scoring: antioxidant + allergenicity | 1,055,116 fully scored | ~15 min |
| 2 | Dual-channel split and safety scoring | 1,055,116 → 50,000 (25,000 top + 25,000 bottom) | ~63 min |
| 3 | Heavy scoring and selection | 50,000 → Top 80 + Bottom 10 peptides | ~65 min |
| 4 | Construct enumeration and construct-level rescoring | → 150 constructs | ~13 min |
| 5 | Three-dimensional structure prediction | 150 → 150 PDB files | ~210 min |
| 6 | Structure evaluation | 150 structures scored | ~6 min |
| 7 | Final dual-channel ranking | → 90 Top + 60 Bottom | ~1 min |
| | **Total** | **1,081,772 → 150 constructs, 99.986% rejected** | **~6.5 h** |

### 4.3 The decisions, and why each was taken

**Toxicity prediction was moved out of the first round.** The original plan ran it on the full 1,055,116 sequences. The predictor is a single-threaded, CPU-bound tree ensemble, and the estimate for that workload was roughly 22 hours against a total budget of a few hours. Moving it to round 2, on a 50,000-sequence subset, brought it to about 48 minutes with no effect on the final result, because every sequence that reaches round 2 has already been selected on antioxidant activity.

**The dual-channel split uses the raw antioxidant score, not a weighted total.** An earlier arrangement ranked on a weighted composite and this was judged wrong for a specific reason: the components have incompatible units and incompatible degrees of separation, so blending them before selection hides the quality of the thing being selected for. Ranking on the single directly-measured quantity and deferring the blending to a later round preserves the interpretation of the split.

**The dual channel exists to make the result falsifiable.** Both a top channel and a bottom channel run through the entire pipeline. The bottom channel is not a by-product; it is a set of candidates predicted to be poor, carried forward under identical processing so that they provide a matched baseline. If the high-activity channel and the low-activity channel behave the same way in a wet-lab assay, the pipeline's central assumption is refuted. This is the reason the project can describe its own output as falsifiable, and it is a design property rather than a claim.

**Structure prediction used one tool rather than two.** The plan had been to run a fast predictor and a slower one in parallel. On this class of sequence the fast predictor returned confidence below 0.30, which is below the level at which the downstream surface-exposure and aggregation measurements carry any information. It also consumed most of the available GPU memory and contended with the other predictor even when it produced nothing usable. Removing it and running the remaining predictor serially was both faster and more stable, and cut GPU time by roughly half.

**A construct-level composite score was removed from the final ranking.** An intermediate score, built from the peptide-level composite plus construct-level solubility and epitope terms, had been assigned half the final weight. Inspection of the top ninety showed that this quantity was nearly constant across them — the spread between the 25th and 75th percentile was 0.011 — so at half weight it was effectively deciding the ordering on noise and diluting the two quantities that did discriminate. It was removed and the final ranking was rebuilt on three structural terms at weights 0.40, 0.40 and 0.20.

**The three-term final ranking is the ancestor of the platform's composite score.** The formula is stated in section 12. Its important property, from the point of view of everything that followed, is what it leaves out: it contains no functional term. Antioxidant prediction is used once, to assign a channel, and never again. The consequence — visible in version 1.4 and in the platform — is that the structurally best constructs can come from the negative-control channel, which is a property of the score rather than a defect of the run.

### 4.4 Results

The run produced 90 top-channel and 60 bottom-channel constructs from 150 enumerated. Structural confidence averaged 0.41, mean peptide surface exposure 0.70, and mean aggregation propensity 0.35.

The five highest-ranked constructs by the final score:

| Rank | Construct | Functional peptide | Final score | SASA | Aggrescan3D | pLDDT |
|---|---|---|---|---|---|---|
| 1 | `con_0215` | `ERELPYYPGAHPMHPPK` | 0.7794 | 0.8143 | 0.3515 | 0.4522 |
| 2 | `con_0199` | `GTHWHPEHF` | 0.7684 | 0.7996 | 0.3291 | 0.4460 |
| 3 | `con_0226` | `EPTMYGEILSPNYPQAYPSEV` | 0.7345 | 0.7697 | 0.3488 | 0.4398 |
| 4 | `con_0201` | `GTHWHPEHF` (both ends) | 0.7224 | 0.7633 | 0.3564 | 0.4369 |
| 5 | `con_0095` | `PAFELHYPHMVER` | 0.7142 | 0.7212 | 0.3318 | 0.4364 |

### 4.5 The two design errors this version exposed

Version 1.2 worked, and its output is coherent, but reviewing it produced two findings that determined the shape of everything after it. Both are errors of composition rather than of execution, and both were detected by inspecting the arithmetic rather than by a failure of the run.

**Safety attributes could be outvoted.** The composite score in rounds 2 and 3 combined antioxidant activity, toxicity, allergenicity, haemolysis, immunogenicity, epitope propensity and thermal stability into a single weighted total, with the safety terms carrying small coefficients — haemolysis at 0.09, immunogenicity at 0.05, toxicity at 0.13. In that arrangement a peptide with a severe haemolysis signal but a very strong antioxidant score can still finish near the top, because the haemolysis penalty is smaller than the antioxidant advantage. Safety had been implemented as a score, and a score can be compensated. The correct treatment is a threshold: pass or eliminated, with no participation in any average.

**The antioxidant signal leaked past the split.** Although the channel assignment correctly used the raw antioxidant score, the composite used for ranking in rounds 3 through 7 also contained an antioxidant term, at the largest coefficient in the table. The bottom channel therefore continued to be ranked partly on the property that defined it as the bottom channel, which means the two arms were not independent and the comparison the design was built to enable was weakened.

Both findings were verified against the arithmetic of the stored results rather than inferred from the design documents, and both were addressed in version 1.4 by changing the pipeline's structure rather than by adjusting coefficients.

---

## 5. Version 1.3 — the billion-scale pipeline

### 5.1 What it was, and what it was not

Version 1.3 was an attempt to move the funnel's entrance from a million sequences to the billion-sequence range, and it changed the pipeline's substrate rather than its logic. Its first stage ran to completion; its later stages were written and then superseded before they were executed, because version 1.4 was designed against the same candidate pool and solved the problem differently.

The source material was the two largest public protein sequence resources. UniProt contributed 225,619,586 sequences; a metagenomic protein-cluster resource contributed 623,796,864. Together, 849,416,450 sequences.

### 5.2 Stage 0: what the scaling actually costs

Stage 0 streamed both files, retained only sequences of 3 to 30 residues composed of the twenty standard amino acids, and wrote the survivors into a columnar analytical database. It ran in 5,924 seconds — 98.7 minutes — and produced 19,890,021 candidates in a 2.6 GB database file. Scanned throughput was roughly 143,000 sequences per second.

The two sources behaved completely differently, and the reason is worth recording because it determines the composition of every downstream result.

| Source | Sequences scanned | Length-passing | Written after residue filter | Pass rate |
|---|---|---|---|---|
| UniProt | 225,619,586 | 744,565 | 733,573 | 0.33% |
| Metagenomic clusters | 623,796,864 | 19,156,521 | 19,156,448 | 3.07% |

UniProt is a catalogue of full-length proteins; almost all of its entries are far longer than thirty residues and are removed by the length filter before anything else touches them. The metagenomic resource is a catalogue of predicted small proteins and short open reading frames, which is exactly the size range the filter keeps. The result is that 96.3% of the surviving candidate pool is metagenomic and only 3.7% is annotated. This ratio is not a design choice; it is a consequence of applying a thirty-residue ceiling to two databases with different length distributions.

The filter had two consequences that shaped the length distribution of everything downstream. Both sources have a hard floor at three residues and a hard ceiling at thirty. Within that window the distribution is not smooth: lengths 20 through 30 carry the bulk, because that is where most predicted small proteins and short open reading frames happen to fall. The mean length of a metagenomic survivor is 25.4 residues, and of a UniProt survivor 22.5.

One planned reduction step was tested and abandoned. Sequence clustering at 90% identity, applied to remove near-duplicate peptides, achieved between 0.2% and 5% reduction on these sequences — short peptides are too diverse for identity clustering to have much to remove — and the time cost was not justified. The step was dropped and the pool was left unclustered.

### 5.3 The apparatus this version introduced

Version 1.3's lasting contribution is its measurement and recovery machinery, all of which were carried into version 1.4.

**Variance-aware weighting.** This is the origin of the rule that weights are computed rather than configured. Each component is normalised within the candidate pool, oriented so that larger is better everywhere, and then weighted by its winsorised standard deviation — the standard deviation computed after truncating extreme values to the 5th and 95th percentiles, so a single outlier cannot dominate a component's weight. The weights are then normalised to sum to one. The effect is that a component with real spread in this pool is automatically up-weighted and a component that is nearly constant is automatically driven toward zero. A component whose values all sit near 0.4 across the pool has no discriminating power, its standard deviation approaches zero, and its weight follows — which is preferable to an arrangement in which someone assigns it 0.2 and thereby spends a fifth of the composite on a quantity that cannot separate anything.

**Database-backed state with checkpoint and resume.** Moving state from CSV files into a database made three things possible at once: intermediate results can be queried rather than read sequentially, a run that fails after fourteen hours can resume from the last completed unit, and a later stage can read a consistent snapshot while an earlier stage is still writing. The last of these required an explicit workaround, because the database engine in use admits only one writing connection at a time; the solution is to copy the database file and read the copy, so that a long blocking stage does not lock out a parallel pre-computation.

**On-demand service startup.** Running every microservice continuously leaves a GPU context allocated per service, which accumulates until the card is full. The fix is to declare, per stage, which services that stage actually requires, and start only those. In practice this reduces a round to between two and five live services out of the sixteen available, and it removes GPU contention entirely rather than managing it.

**Idempotent writes.** Every result write is an upsert keyed on the candidate identifier, so a batch can be re-run without producing duplicates and different rounds can write different columns of the same row without overwriting each other. This is the foundation of both pre-computation and crash recovery.

**Progressive persistence.** Batches are written as they complete rather than accumulated in memory for a single final write. The rule is stated as an assumption about failure: a pipeline that takes fourteen hours will fail somewhere, and the only question is how much work is lost when it does. Batch size is therefore chosen as the amount of work one is willing to recompute, not as a performance parameter.

### 5.4 Why stage 1 was not completed

The remaining stages were designed in detail, including the full round-by-round structure that version 1.4 later implemented. They were not executed because version 1.4 was designed against the same 19.9-million-candidate pool and incorporated the corrections to version 1.2's two design errors. Version 1.3's stage 1 code — batch scoring of the whole pool for antioxidant activity and allergenicity — was written and ready but never run to completion. Its candidate database, however, is the input to version 1.4, and version 1.4's stage 0 is a re-import of that same pool.

---

## 6. Version 1.4 — hierarchical filtering

### 6.1 What changed, and why

Version 1.4 is the project's final pipeline and the one whose output is used as a result. It takes the 19,890,021-candidate pool produced in version 1.3 and converges it on 250 constructs in about 65 hours of wall-clock time. Its design is a direct response to the two errors version 1.2 exposed, and it replaces blending with sequencing.

**Principle A — hierarchical filtering, never cross-attribute averaging.** Each round applies a single criterion. A round either sorts and takes a percentile, or it applies a threshold and eliminates. No round mixes different properties into one number. The reasoning is that a blend is only meaningful when the components share a unit and a direction, and attributes as different as antioxidant activity and haemolysis risk share neither.

**Principle B — safety is a hard threshold.** Toxicity, haemolysis, allergenicity and immunogenicity receive only a pass-or-eliminate decision. They are not scored, not weighted, and not compensable.

**Principle C — the functional score is used once.** Predicted antioxidant activity is used in round 1 and nowhere else, so that the two channels remain independent and so that selecting for the property being studied does not quietly continue into the ranking of the molecules that carry it.

**Principle D — the pipeline has exactly one weighted average, and its weights come from the data.** Round 3 is the only place where different attributes are combined, and its weights are proportional to each attribute's winsorised standard deviation, with an optional manual coefficient that must be recorded together with a stated reason. A manual weight adjustment is invalid without a recorded justification, which is a rule against tuning the weights after seeing which constructs won.

**Principle E — order by cost.** Cheap, high-throughput work runs first; the most expensive work runs last on the smallest set. The same rule as version 1.1, applied to a pool two thousand times larger.

### 6.2 The rounds

| Round | Criterion | Method | Services | Time |
|---|---|---|---|---|
| 0 | Length and residue type | Import from version 1.3's candidate pool | — | ~15 min |
| 1 | Antioxidant activity, plus allergenicity as a hard filter | Sort on raw score; top 10% → Top channel, bottom 1% → Bottom channel; allergenicity ≥ 0.30 eliminated | antioxidant predictor, allergenicity predictor | ~30 min |
| 2 | Safety | Three independent hard thresholds: toxicity < 0.38, haemolysis < 0.55, immunogenicity < 0.50; any failure eliminates | toxicity, haemolysis, immunogenicity predictors | ~24 h |
| 3 | Developability | Four properties scored, then combined by winsorised-standard-deviation weights — the pipeline's only weighted average | epitope, thermal stability, solubility, cell penetration, and a graph-based penetration model | ~5 h |
| 4 | Construct assembly | Enumerate position × linker; rescore solubility and thermal stability on the assembled full-length protein | solubility, thermal stability, epitope | ~6.5 h |
| 5 | Structure | Predict the three-dimensional structure of every surviving construct | OmegaFold, serialised | ~6.1 h |
| 6 | Structure evaluation | Surface exposure and aggregation propensity | solvent-accessible surface area, aggregation predictor | ~5.4 min |
| 7 | Final ranking | Combine the three structural terms; rank each channel independently | — | < 1 s |
| 8 | Cross-validation | Re-predict the top ten from each channel with a second, independent structure model | AlphaFold3 | ~22.5 h |
| | | **Total** | | **~65 h** |

### 6.3 What each round actually does

**Round 1** is the only place antioxidant prediction influences anything. Every candidate is scored, allergenicity is applied as a hard threshold at 0.30, and the survivors are sorted on the antioxidant score alone. The top ten percent go into the Top channel and the bottom one percent into the Bottom channel. The asymmetry is deliberate: the Top channel is a candidate pool and can afford to be generous, while the Bottom channel only has to be large enough to provide a matched negative control, and roughly 199,000 sequences is already far more than that.

**Round 2** is the pipeline's bottleneck and the clearest expression of the design's position on safety. Three checks run independently, each with its own threshold, each able to eliminate on its own, and none of them contributing a term to any later calculation. The toxicity check accounts for almost all of the round's duration: the model is a single-threaded CPU tree ensemble, and processing the survivors takes on the order of a day. The check runs a second time as a pre-screen inside round 3, where it eliminates a further 16,982 peptides — 16.4% of what had reached that point — which is a useful reminder that the first pass and the second pass operate on different populations.

**Round 3** scores the survivors for B-cell epitope propensity, thermal stability, solubility and cell-penetration propensity, adds a second, graph-based penetration score, computes each property's winsorised standard deviation across the pool, and forms the weighted composite that determines which peptides advance. Solubility carries the largest computed weight, followed by epitope propensity, then thermal stability; the two penetration scores come out low because neither separates the candidates much in this pool. The result is reported with the full weight configuration — base weight, manual coefficient, final weight and stated reason — so that any ranking can be reconstructed and any later change in convention can be evaluated against results already stored.

**Round 4** converts peptides into molecules. The highest-ranked peptides are each assembled in all six combinations of insertion position and linker, and the solubility and thermal-stability predictions are then re-run on the complete fusion protein rather than on the free peptide. This second scoring is the reason the round exists as a separate step: a peptide that is stable and soluble on its own need not behave the same way once attached to a 364-residue scaffold, and only the assembled molecule is what would actually be made. Ten percent of the assembled constructs advance, and a further pass adds epitope prediction at the full-construct level.

**Rounds 5 and 6** predict structure and then measure on that structure. Structure prediction is serialised rather than parallelised, because the predictor's inference call blocks the event loop of the service hosting it; a concurrency of one is not a performance choice but the only arrangement in which requests complete reliably. All 250 surviving constructs produced a usable structure.

**Round 7** combines surface exposure, aggregation propensity and normalised structural confidence into the final score and ranks each channel independently. **Round 8** re-predicts the top ten of each channel with a second structure model as an independent check. Mean confidence across the twenty re-predicted constructs was 0.52 against 0.42 for the primary model, with the same trend and the same ordering at the top, which is the evidence that the ranking is not an artefact of one predictor.

### 6.4 The final score

```
round7_score = 0.40 × SASA + 0.40 × (1 − Aggrescan3D) + 0.20 × pLDDT_norm
```

The three terms measure different things and are weighted on a stated rationale.

**Surface exposure (SASA)** is the relative solvent-accessible surface area of the functional peptide within the folded construct. A spherical probe of radius 1.4 Å is rolled over the structure, the accessible area of each residue is measured, and each residue's raw area is divided by the maximum area that residue type can expose. The score is the mean relative accessibility across the peptide region only. The reasoning is functional: a peptide buried in the scaffold's core cannot reach the species it is meant to react with, while one on the surface can. Higher is better.

**Aggregation propensity** estimates how strongly the protein tends to clump. Lower is better, because an aggregating protein expresses poorly and purifies badly, so the term enters as one minus the risk index.

**Structural confidence (pLDDT)** is the predictor's per-residue confidence, averaged over the chain and min–max normalised across the 250 constructs. It enters at half the weight of the other two, on the reasoning that confidence should temper the other terms rather than drive them: a predicted structure is evidence about a construct, not the construct itself.

Surface exposure and aggregation propensity carry equal weight because they bear directly on whether the expressed protein behaves as designed; confidence carries half of that because it qualifies the other two rather than measuring a property of the molecule.

The most important property of this score is what it does not contain. There is no functional term of any kind. It is a statement about physical quality — will this fold, will it stay soluble, will the peptide be reachable — and no statement about antioxidant strength can be read off it.

### 6.5 The funnel, and the final results

| Stage | Count |
|---|---|
| Candidate pool | 19,890,021 |
| Round 1: allergenicity filter and channel split | top 10% and bottom 1% retained |
| Round 2: safety veto | survivors of three independent thresholds |
| Round 3: developability composite | top percentile retained |
| Round 4: assembly | 4,324 peptides × 6 position/linker combinations = 25,944 constructs → top 10% = 2,594 |
| Rounds 5–6: structure and evaluation | 250 with complete structural scores |
| Round 7: final ranking | Top 150 + Bottom 100 |
| Round 8: cross-validation | 20 re-predicted with a second model |
| **Overall rejection rate** | **19,890,021 → 250 = 99.9987%** |

Note that the internal funnel figures are recorded inconsistently between the run review and the later field guide. The review lists approximate intermediate counts of 86,000 after round 1, 65,000 after round 2 and 700 after round 3, while the field guide gives the round 4 inputs precisely as 4,324 peptides, 116 from the Top channel and 4,208 from the Bottom. The primary quantities — the candidate pool, the assembly count of 25,944, the final 250 and the channel split — agree across both records and are the ones to quote.

The five highest-scoring constructs overall:

| Global rank | Channel | Construct | SASA | Aggrescan3D | pLDDT | Final score |
|---|---|---|---|---|---|---|
| 1 | bottom | `con_5489` | 0.6873 | 0.2925 | 0.4950 | 0.7579 |
| 2 | bottom | `con_3275` | 0.6861 | 0.2927 | 0.4857 | 0.7420 |
| 3 | bottom | `con_1415` | 0.7055 | 0.3301 | 0.4854 | 0.7342 |
| 4 | bottom | `con_15869` | 0.8229 | 0.2753 | 0.4410 | 0.7296 |
| 5 | bottom | `con_1103` | 0.6777 | 0.2946 | 0.4743 | 0.7189 |

The five highest-scoring constructs within the Top channel:

| Global rank | Channel rank | Construct | Position | Linker | SASA | Aggrescan3D | pLDDT | Final score |
|---|---|---|---|---|---|---|---|---|
| 9 | 1 | `con_0418` | C | `Flex_GGGGSx2` | 0.8104 | 0.3219 | 0.4420 | 0.7076 |
| 13 | 2 | `con_0417` | C | `Flex_GGGGSx1` | 0.7844 | 0.3557 | 0.4514 | 0.6993 |
| 17 | 3 | `con_0317` | Both | `Flex_GGGGSx1` | 0.8228 | 0.3598 | 0.4386 | 0.6918 |
| 19 | 4 | `con_0850` | C | `Flex_GGGGSx2` | 0.7972 | 0.3345 | 0.4372 | 0.6893 |
| 37 | 5 | `con_0558` | Both | `Flex_GGGGSx2` | 0.8158 | 0.3259 | 0.4203 | 0.6723 |

Across all 250 constructs the final score spans 0.4800 to 0.7579 with a mean of 0.6327; within the Top 10 it spans 0.7076 down to 0.6642, a spread of only 0.043.

### 6.6 The counterintuitive ordering, and why it is not an error

The eight highest-scoring constructs in the entire run all belong to the Bottom channel, and the best of them outscores the best Top-channel construct. This is a direct consequence of the score containing no functional term, and it is worth stating prominently because it looks like a mistake to anyone reading the table without the explanation.

The Bottom channel peptides were selected for the lowest predicted antioxidant activity. They then passed the same safety vetoes and were ranked by the same structural terms as the Top channel. Structurally, they are at least as good: the Bottom channel is ahead on confidence, solubility, thermal stability and the composite score, and the gap is large enough to be robust across the final set. The reason is that antioxidant prediction and structural quality are simply not correlated in this pool, and the bottom-channel population is not different from the top in any way that structure prediction can see.

The practical conclusion is stated as a wet-lab instruction rather than as a caveat: candidates should be drawn from both channels, and a plan that draws only from the top ten of the Top channel is testing the wrong population.

### 6.7 Two qualifications that must travel with any external description

**Structural confidence is low across the whole dataset, and that is expected.** Mean confidence is 0.42 and the maximum is 0.50, on a scale where 0.50 marks the edge of meaningful confidence; the independent second model returns 0.52. This is not a failure of the constructs but a property of silk fibroin: the scaffold is built from glycine-alanine repeats that adopt a disordered, partly amorphous fold with no natural structural template for a folding predictor to work from. The consequence is that the structures underpinning the final score are low-confidence models, and the score is properly described as a consistent way to rank imperfectly modelled structures rather than as a precise physical measurement.

**The top two constructs in the Top channel carry a sequence that is not a functional peptide.** The peptide `MNRPWITGHHHHHHHRRRRRRRRRR`, carried by `con_0418` and `con_0417`, is twenty-five residues of a short serine-rich leader followed by six histidines and nine arginines. That composition is characteristic of a purification or cloning handle, not of a bioactive antioxidant peptide. It entered the pool because preprocessing filters on length and residue type only, and this sequence satisfies both; it survived round 1 on a middling-to-high antioxidant prediction; and it reached the top of the structural ranking because structural ranking never examines what a peptide does. The two entries are the same peptide at the same position, differing only in linker length, which is why they occupy channel ranks 1 and 2 with near-identical scores. Any external document quoting the top of that table carries an obligation to flag this entry explicitly or to quote it with the qualification attached; presenting it as the project's lead candidate without that context misdescribes what it is. A stronger pair of candidates for wet-lab work is `con_0850`, the highest on the independent structure validation at 0.56, and `con_0418`'s structural quality is at least matched by `con_0317` among constructs that carry a plausible peptide.

---

## 7. Cross-version comparison

| Dimension | 1.1 | 1.2 | 1.3 | 1.4 |
|---|---|---|---|---|
| Input scale | 1.8 × 10³ | 1.1 × 10⁶ | 8.5 × 10⁸ scanned | 2.0 × 10⁷ |
| Output | 107 peptides | 150 constructs | candidate database | 250 constructs |
| Rounds | 6 phases | 8 | 6 planned | 9 |
| Weighting | manual, fixed | manual, fixed | winsorised standard deviation | winsorised standard deviation, one position |
| Safety | hard filter, then weighted | hard filter, then weighted | hard filter | hard veto, never weighted |
| Functional score reuse | once, in the weighted total | four times | once | once |
| State | CSV + status files | CSV + checkpoint file | DuckDB, 15 tables | DuckDB, 30+ tables |
| Recovery | manual, per stage | checkpoint file | checkpoint + resume, snapshot for parallel readers | checkpoint + resume, progressive writes |
| Service lifecycle | batched start, stop before structure work | on demand | on demand, declared per stage | on demand, declared per stage |
| Structure predictor | planned | one predictor, serial | planned | one predictor serial + independent validation |
| Channels | none | Top + Bottom | Top + Bottom | Top + Bottom, independent rankings |
| Output channel sizes | — | 90 + 60 | — | 150 + 100 |

The trajectory across the four versions is a shift from questions of speed to questions of correctness. Version 1.1 asked how to order work so a run finishes. Version 1.2 asked how to make a run survive interruption. Version 1.3 asked how to make the same run survive two orders of magnitude more input. Version 1.4 asked what the pipeline should be computing at all, and answered by removing blending from every position except one and by making the weights a property of the data.

---

## 8. The microservice layer

### 8.1 Three templates

All sixteen predictive services conform to one of three interface templates, and the client exposes one call pattern per template.

| Template | Input | Output | Client method |
|---|---|---|---|
| Sequence scoring | amino-acid sequence | a score | `predict_single()`, `predict_batch()` |
| Structure prediction | amino-acid sequence | a structure file | asynchronous submission and polling |
| Structure scoring | structure file and sequence | a score | `predict_pdb_single()`, `predict_pdb_batch()` |

Every service belongs to exactly one template, and the template is recorded in the service registry rather than inferred at the call site. Batch calling is the default, with one exception: the toxicity predictor's underlying tree ensemble is not thread-safe and must be called one sequence at a time.

Concurrency is declared explicitly per service as a semaphore, and the value is determined by two constraints rather than by a general preference. GPU services are limited by the memory a single loaded model occupies, so their semaphore bounds queued requests rather than memory; CPU services whose underlying libraries use non-thread-safe C extensions are limited to one or two regardless of throughput. Where a service is both slow and thread-unsafe, the throughput limit is broken by running several container instances and dividing the candidate list across them, since separate processes are physically isolated in a way that separate threads are not.

### 8.2 Service inventory

**Sequence-scoring services**

| Service | Port | Function | Environment | Model |
|---|---|---|---|---|
| AnOxPePred | 8001 | Antioxidant activity (radical scavenging plus metal-chelating branch) | GPU/CPU | CNN, 1.3 MB, in repository |
| BepiPred-3.0 | 8002 | B-cell epitope propensity | GPU/CPU | ESM-2 650M + DenseNet, 2.5 GB, first-run download |
| ToxinPred3 | 8003 | Toxicity | CPU | Extra Trees over composition features, 2 MB, pip |
| HemoPI2 | 8004 | Haemolysis, and haemolytic concentration as a second task | GPU/CPU | fine-tuned ESM-2 t6, 30 MB, pip |
| MHCflurry | 8005 | MHC class I binding affinity | GPU/CPU | ensemble, 100 MB, first-run download |
| pLM4CPPs | 8006 | Cell-penetration propensity | GPU/CPU | ESM-2 embedding + 1D CNN, 30 MB |
| TIPred | 8007 | Tyrosinase-inhibition (anti-melanogenic) propensity | CPU | trained at start-up |
| AlgPred2 | 8008 | Allergenicity | CPU | random forest, 1 MB, pip |
| GraphCPP | 8009 | Cell-penetration propensity, graph neural network | GPU/CPU | GraphSAGE checkpoint, 200 KB |
| TemStaPro | 8010 | Thermal stability across a temperature ladder | GPU/CPU | ProtT5-XL plus 30 classifiers, 2.3 GB |
| SoDoPE | 8012 | Solubility | CPU | table lookup and arithmetic, no model |

**Structure-scoring services**

| Service | Port | Function | Environment |
|---|---|---|---|
| SASA | 8101 | Solvent-accessible surface area | CPU |
| Aggrescan3D | 8102 | Aggregation propensity on a structure | CPU, container |

**Structure-prediction services**

| Service | Port | Function | Environment |
|---|---|---|---|
| AlphaFold3 | 8201 | High-accuracy structure prediction | GPU, container only |
| PEP-FOLD4 | 8202 | De-novo peptide structure, 5–40 residues | CPU, container |
| ESMFold | 8203 | Fast structure prediction | GPU |
| OmegaFold | 8204 | Language-model and geometry-transformer structure prediction | GPU/CPU |
| Waveflow | 8205 | Remote proxy to a commercial structure-prediction service | CPU, no local model |

Three of these are auxiliary rather than predictive in the ordinary sense: the remote proxy forwards to an external service and needs no local model, and the two structure-scoring services consume a structure produced elsewhere rather than a sequence.

The largest models in the inventory — the protein language models backing epitope prediction, thermal-stability prediction and fast structure prediction — are held in a shared cache directory and downloaded once, because more than one service uses each.

### 8.3 Model sourcing and the environment

Models reach the services by one of five routes, and the route is recorded per service: tracked in the repository if under about 50 MB; downloaded automatically on first use if larger; installed as part of a pip package; produced at start-up by a training step; or baked into a container image.

The production environment is a Linux host with a single high-memory GPU; the development environment is a modern macOS machine. Every service that can use a GPU also detects whether one is present and falls back to CPU, and the services that require a GPU report a clear error rather than silently degrading. In production, every service runs in a container. The reason is not packaging convenience but reproducibility: running a service directly on the host produced environment drift, missing models and debugging time that the container removes.

Two operational consequences of the container topology are recorded because both caused failures that took hours to diagnose. First, containers are addressed by their bridge network address rather than through the host's port mapping; the port mapping forwards through a proxy that intermittently hangs on long-running requests, so a request that the service is actively processing never reaches the client. Second, the order in which services are started and stopped matters more than the resources they claim, because a GPU context is not released when the process is asked to stop politely; only forceful termination frees the memory, which is the operational justification for starting services on demand rather than leaving them resident.

---

## 9. Pipeline engineering principles

Version 1.4's implementation obeys a set of rules that are stated here because they are the difference between a pipeline that produces a result and one that produces a partial result and dies. When two rules conflict, a stated priority applies: data safety over speed, idempotence over special-case optimisation, explicit configuration over implicit assumption, and simple correctness over complex efficiency.

**State is never accumulated only in memory.** Every completed batch is written to durable storage immediately. A run that takes a day will be interrupted; the only question is how much work is lost. Batch size is therefore the amount of work one is willing to recompute.

**Writes are idempotent.** Every result write is an upsert keyed on the candidate identifier, so re-running a batch produces no duplicates and different rounds can write different columns of a row without overwriting one another. This single property makes pre-computation, checkpointing and crash recovery possible.

**Fast results are persisted first.** When two services of very different duration run concurrently, the fast one writes before the slow one is allowed to hold anything. If the slow service then fails, the fast service's output survives.

**Completion is recorded, and checked before work begins.** Each stage writes a checkpoint recording the round, the step and the number of items processed, and the script consults it on start-up. Two resume granularities are supported: skip a whole service that already finished, or continue from the last processed candidate. Checkpoints also allow work to be skipped conditionally in response to a step that is known to be broken.

**Shared resources are accessed through a copy rather than contended for.** Where a single-writer database would be held open by a long stage, a snapshot is taken and the parallel work reads the snapshot while writing to a separate file, which is then merged.

**A single request failure does not stop the run.** Batch results are collected with exception capture enabled, so that one failed call produces a recorded gap rather than cancelling the batch. The gap is written as a missing value and can be retried after the bulk work completes.

**Dependency readiness is checked before work starts.** Every scoring step begins by confirming that the services it needs are answering, and aborts if they are not. This is a cheap check that prevents the specific disaster of discovering a dead service an hour into a round.

---

## 10. Safety

### 10.1 The four checks

Safety rests on four independent checks. Each has its own threshold, each can eliminate a candidate on its own, and none of the four contributes a term to any average. Strong performance elsewhere can never compensate for a safety failure, and this is the project's most substantive methodological commitment.

| Check | Tool | Threshold | Direction | Basis | Model |
|---|---|---|---|---|---|
| Toxicity | ToxinPred3 | 0.38 | score ≥ threshold eliminated | Extra Trees over amino-acid and dipeptide composition | 2 MB |
| Haemolysis | HemoPI2 | 0.55 | score ≥ threshold eliminated | fine-tuned ESM-2 t6 | 30 MB |
| Allergenicity | AlgPred2 | 0.30 | score ≥ threshold eliminated | random forest over composition features | 1 MB |
| Immunogenicity | MHCflurry | 0.50 | score ≥ threshold eliminated | neural ensemble over MHC class I binding | 100 MB |

The immunogenicity check needs one further explanation of its scale. The tool's raw output is a binding concentration in nanomolar, and the service layer maps that onto a zero-to-one risk score: below 50 nM is a strong binder and scores 0.5 to 1.0, 50 to 500 nM is a weak binder and scores 0.25 to 0.5, and above 500 nM is a non-binder and scores 0 to 0.25.

Allergenicity is the only one of the four executed in round 1 alongside the channel split, because it is cheap and because removing allergenic candidates before the split keeps them out of both channels. Toxicity is executed twice, once as the round 2 threshold and once as a pre-screen in round 3; the second pass eliminates 16,982 peptides, 16.4% of what reached it.

The four safety attributes are treated in the exact mirror image of the functional attributes. Functional attributes are ranked by a weighted composite whose weights are derived from the data. Safety attributes receive a binary decision and nothing else. That asymmetry is the design. A weighted average permits a high value on one axis to offset a low value on another, which is a defensible convention for properties that trade off against each other and an indefensible one for a property that is a precondition for use.

### 10.2 The three thresholds

Of the four thresholds, three require explanation because they are not simply inherited from the tools.

**Toxicity at 0.38** is the project's own calibration. The tool's default threshold admits a set of candidates this pool does not support; the full library was scored, the distribution inspected, and 0.38 chosen as the value that suppresses both false negatives and false positives on this distribution. This is the one threshold in the system that is a project decision rather than a tool recommendation, and it is written into the predictor's own detail record so that it travels with the data.

**Haemolysis at 0.55** is the tool's own value, with a caveat worth recording: the tool's median on this library is 0.518, which means the decision boundary falls inside the tool's densest region and the grey zone between roughly 0.4 and 0.6 is genuinely unstable. The threshold is retained because it is the tool's, not because the boundary is sharp.

**Immunogenicity at 0.50** is a convention rather than a measured boundary, and it applies only to peptides within the tool's accepted length range. This is the origin of the two-pathway treatment of immunogenicity in the platform: MHC class I presentation and MHC class II presentation measure different biology, and neither substitutes for the other.

### 10.3 Two limitations that must be stated rather than implied

**The immunogenicity check does not operate on the final constructs.** The tool accepts peptides of 5 to 15 residues. Among the 250 final functional peptides, exactly one is 8 residues; every other is at least 18. The service returns a score of zero for out-of-range input and labels it as an invalid length, and the acceptance condition is a score below 0.50, so all such inputs are passed silently and nothing is eliminated on this basis. Of the four checks, three genuinely execute on the final products. The honest statement is that the final constructs did not trigger a toxicity, haemolysis or allergenicity veto, not that they passed four checks. Two remedies are possible: state the limitation as it stands, or replace the check for this length range with a long-peptide immunogenicity method or a prediction over the presented core fragment.

**A safety check whose service is unavailable is treated as passing.** The elimination condition is "the metric has a score and the score exceeds the threshold", so an empty score yields a pass. Over a nineteen-million-candidate run this permissive policy is what allows the pipeline to finish at all, and its cost is that an individual unchecked candidate can advance. The accurate external formulation is therefore that candidates triggering no safety veto were retained, not that every candidate passed every check.

---

## 11. Results and data assets

### 11.1 What the pipeline produced

| Asset | Version | Scale | Notes |
|---|---|---|---|
| Candidate pool | 1.3, 1.4 | 19,890,021 sequences | 96.3% metagenomic, 3.7% annotated |
| Per-round score tables | 1.4 | 30+ tables | full provenance per round per candidate |
| Assembled constructs | 1.4 | 250 | Top 150 + Bottom 100 |
| Predicted structures | 1.4 | 253 PDB files | 250 primary plus three test entries |
| Independent structure validation | 1.4 | 20 | top ten of each channel |
| Final ranking tables | 1.4 | `top10.csv`, `bottom10.csv` | ten highest per channel |
| Per-construct records | 1.4 | 250 JSON files | every score, every rank, source accession, full sequence |
| Round reports | 1.4 | 6 reports | including a channel comparison |
| Constructs | 1.2 | 150 | earlier run on a smaller pool |

### 11.2 Construct composition

Every construct is a scaffold, a linker and a functional peptide, with one purification tag at the end.

```
N    peptide + linker + scaffold + LEHHHHHH
C    scaffold + linker + peptide  + LEHHHHHH
Both peptide + linker + scaffold + linker + peptide + LEHHHHHH
```

The scaffold is the 364-residue silk construct described in section 1.2. The tag is the eight-residue sequence `LEHHHHHH`, present exactly once in every construct, serving as the affinity-chromatography handle and as a spacer that holds the terminal hexahistidine away from the protein body. Ten linker designs were evaluated; two were carried into assembly, the five-residue `GGGGS` and the ten-residue `GGGGSGGGGS`. Three insertion positions were enumerated: N-terminal, C-terminal, and both ends.

`con_0418`, the highest-ranked construct in the Top channel, follows the C-terminal pattern with the longer linker: the 364-residue scaffold, then `GGGGSGGGGS`, then the 25-residue peptide, then the tag, giving a 407-residue product. `con_0317`, at channel rank 3, follows the both-ends pattern with the shorter linker for a 426-residue product. Five of the top ten use the C-terminal position and five use both ends; the N-terminal position does not appear. That is consistent with the wider set, where the both-ends pattern dominates, because a doubled peptide scores better on both the solubility and the thermal-stability predictions that the assembly round ranks on.

### 11.3 Source provenance

Each candidate sequence carries the database it was drawn from and that database's own identifier, and the identifier is preserved through every round. This is what makes the output traceable and what allows the platform to report a candidate's origin.

| Source | Identifier form | Character | Share of the 250 constructs |
|---|---|---|---|
| Metagenomic protein clusters | `MGYP` plus twelve digits | real sequence, no functional annotation | 244 |
| UniProt | accession such as `A0A5K0UWX3` | real sequence with curated annotation | 6 |

The imbalance follows directly from the length filter. UniProt is overwhelmingly a catalogue of full-length proteins, almost all of which are longer than thirty residues; the metagenomic resource is a catalogue of predicted short proteins, which is the filter's target range. The practical consequence is that a metagenomic accession means the sequence is real and its fold is computationally predicted but nobody has measured what the peptide does, while a UniProt accession is the only one of the two that arrives with prior biological evidence. Against a pool in which 96.3% of survivors are unannotated, the annotated minority is disproportionately valuable, which is why one UniProt-sourced construct remains in the top ten of the Top channel despite the source contributing under 4% of the pool.

---

## 12. Metrics and definitions

| Term | Definition |
|---|---|
| **pLDDT** | Per-residue confidence reported by a structure predictor, on a 0-to-1 scale. Above 0.90 indicates a well-resolved region; below 0.50 indicates a segment the model considers essentially disordered. The construct-level value is the mean over the chain. In this dataset the mean is 0.42 and the maximum 0.50 — low throughout, because silk's glycine-alanine repeats are intrinsically disordered. |
| **SASA** | Solvent-accessible surface area. Computed by rolling a probe of radius 1.4 Å over the structure and measuring how much of each residue the probe can reach, then dividing by the maximum area the residue type can expose. Reported here as the mean relative accessibility across the functional peptide region only. Higher is better. |
| **Aggrescan3D** | A structure-level aggregation-propensity index. Originally a per-residue contribution derived from burial depth, side-chain hydrophobicity relative to neighbours, and pairwise interaction energy between contacting residues; the recorded value is a rescaled risk index between 0 and 1 built from the fraction of positive residues, their mean positive contribution, and the largest hot spot. Lower is better. |
| **HC50** | The peptide concentration at which 50% of red blood cells are lysed. Used by the haemolysis tool as a quantitative second output alongside the probabilistic score. A common convention treats HC50 at or below 100 µM as haemolytic. |
| **Winsorised standard deviation** | The standard deviation computed after truncating extreme values to the 5th and 95th percentiles. Used as the weighting basis because it prevents one outlier from dominating a component's weight. |
| **Channel** | One of two parallel arms of the funnel. The Top channel holds the highest-scoring candidates by the function of interest; the Bottom channel holds the lowest, and serves as a matched negative control rather than as a candidate pool. |
| **Construct** | One assembled molecule: scaffold, linker, functional peptide, purification tag. Distinct from a peptide, which is only the functional segment. |
| **Pool** | The set of candidates a composite score is computed over. Because weights derive from the pool's spread, a score is only comparable to another score from the same pool. |

---

## 13. Engineering record

The following are the failures that cost the most time, recorded because each produced a rule that is now enforced rather than a fix that was applied once.

**Concurrent requests hang a non-thread-safe model.** The toxicity predictor's tree ensemble uses a C extension that is not safe under concurrent access and cannot be interrupted by the asynchronous framework's timeout, because the timeout operates above the native code rather than inside it. The fixes are a batch size small enough to bound each call's duration and a socket-level timeout, which operates below the point where the native code can block.

**Synchronous inference blocks the service's event loop.** The structure predictor's inference call is a synchronous GPU operation executed inside an asynchronous request handler, so it blocks every other request to that service for its full duration. No amount of client-side concurrency helps. The fix is a client-side semaphore of one, which serialises requests; the model was never slow, it was blocking.

**A port mapping hangs on long requests.** Requests issued through the host's container port mapping intermittently never return, even though the service is actively processing them. The fix is to address the container by its bridge address and bypass the mapping entirely. The symptom is particularly misleading because a request made from inside the container works normally.

**GPU memory is not released on process exit.** A language-model service's GPU context can consume tens of gigabytes and survives a polite stop signal. Only forceful termination or full container teardown releases it. This is the reason services are started on demand and stopped when a stage finishes, rather than left resident for convenience.

**An unhandled exception in one task cancels the batch.** Collecting concurrent results without capturing exceptions means a single failure aborts every sibling task. With exception capture enabled and per-task handling, one failure produces one gap.

**The wrong length in a declared reference table corrupts downstream arithmetic.** Where a fixture or reference row declares a length inconsistent with the sequence beside it, every arithmetic assertion built on it fails for a reason that looks like a code defect. Declared lengths and sequences must agree.

**A ranking query with the wrong ordering silently returns the wrong subset.** A query that orders by one column and limits to twenty does not return ten from each of two groups; the two must be selected separately and combined. The failure is invisible because the result has the right shape.

**The wrong model file was silently used for a build stage.** A deprecated environment produces a build that appears to succeed while using an unintended interpreter, which surfaced as a data-handling anomaly in an unrelated part of the pipeline. The rule that came out of it is that operational scripts check their own preconditions rather than assuming the environment they are invoked in.

---

## 14. AI ethics

The project uses machine-learning predictors extensively and generative models not at all for scientific output. The following are implemented practices rather than intentions, and they are the material available for an ethics or responsible-research section.

**Every prediction comes from its original authors' published code and model.** The project's stated tool-design principle is to use the original implementation faithfully, and the avoidance of AI hallucination and of work that substitutes assertion for method is written into the tool documentation as the explicit motivation. No scientific conclusion in this pipeline was produced by a generative model, and every score is traceable to a peer-reviewed model with a stated publication. There is consequently no point in the chain where a model's output is taken as evidence without an independent method behind it.

**A falsifiable negative control was built and retained.** One hundred of the 250 final constructs come from the channel selected for the lowest predicted activity. They were carried through the same safety vetoes, the same assembly, the same structure prediction and the same ranking. If the assay results show no difference between the two channels, the pipeline's central hypothesis is refuted. Retaining a deliberately unpromising set is not standard practice in a computational screen, and its presence is a commitment to the result being testable rather than presented.

**Safety attributes cannot be compensated.** Safety is defined methodologically as a non-negotiable condition. A peptide that performs well on every other axis is removed with no further consideration if it triggers any of the four checks. This removes the dilution that a composite score applies to any property with a small coefficient.

**The chain is traceable end to end.** Every peptide retains its original source identifier through all rounds. Every safety score, every round's ranking, every weight configuration and every final score is persisted per item. Any construct's derivation can be reproduced and audited by a third party from the stored record alone.

**Weight configuration is auditable and manual intervention must be justified.** The composite weights are computed from the data. The one place where human judgement can enter is an explicit coefficient, and any adjustment is only valid once its reason has been recorded alongside it. The rule exists to prevent weights from being revised after the results are known in order to improve the ordering.

**No conclusion rests on a single model.** All 250 structures were predicted with one tool, and the top ten of each channel were independently re-predicted with a second. The two agree on the ordering at the top, which is the evidence that the ranking is not an artefact of the primary predictor.

**Data unfavourable to the project is disclosed.** The reports record that epitope prediction has almost no discriminating power at the construct level, with a standard deviation of about 0.005, because roughly ninety percent of a full-length construct is scaffold shared by every construct; and that structural confidence is low throughout for a reason intrinsic to the material. Stating these rather than reporting only the favourable metrics is the practical form of research integrity here.

**The scope is restricted and prediction is not presented as evidence of function.** The work is confined to non-systemic delivery routes, avoiding the systemic-exposure question. Every functional quantity in the pipeline is a prediction from a model trained on other data. The outputs are candidates for wet-lab testing and the project's own documents say so.

One factual statement belongs with the above and is not a claim of approval: all input is protein sequence from public databases and patent records, with no patient data, no human-subject data and no personal information, so informed-consent and data-privacy procedures do not arise. The project has not undergone any formal ethics review, and external material should not imply that it has.

---

## 15. Open items

**The functional peptides were never independently validated.** Every construct's peptide was selected by prediction. The wet-lab work that would test the pipeline's central hypothesis has not been performed, and until it is, the pipeline's output is a ranked candidate list and nothing more.

**Immunogenicity is not assessed on the final products.** Stated in section 10.3. Whether to disclose the gap or to replace the method is a decision that has not been taken.

**Two of the four functional directions remain unsigned.** In the platform's wider work, the anti-inflammatory and anti-melanogenic directions have data but no pipeline sign-off, because their models' benchmarks are known to be defective. That work sits outside this repository but it bears on how the 1.x lineage's method is described.

**The structural track has a genuine ceiling on this material.** Confidence cannot be raised by using a better tool, because the limit is the disorder of the silk repeats rather than the quality of the predictor. Any future work on structure-based scoring for this scaffold has to accept that the measurements are approximate.

**The relationship between the two channels and wet-lab strategy is stated but not tested.** The pipeline's own analysis concludes that candidates must be drawn from both channels, because the structural ranking is uncorrelated with the functional selection. That conclusion is sound as far as the computational evidence goes, and it is unverified experimentally.

**Where the candidate pool's imbalance should be corrected is unresolved.** After the length filter, 96.3% of candidates are unannotated metagenomic fragments. Whether to rebalance toward annotated sources, and at what cost to pool size, is a design question with no answer yet.

---

## 16. Reusable reference tables

### 16.1 Threshold summary

| Attribute | Tool | Threshold | Direction | Type |
|---|---|---|---|---|
| Toxicity | ToxinPred3 | 0.38 | lower is better | hard veto |
| Haemolysis | HemoPI2 | 0.55 | lower is better | hard veto |
| Allergenicity | AlgPred2 | 0.30 | lower is better | hard veto |
| Immunogenicity | MHCflurry | 0.50 | lower is better | hard veto |
| B-cell epitope | BepiPred-3.0 | 0.1512 | lower is better | reported only |
| Cell penetration | pLM4CPPs | 0.15 | higher is better | reported only |

### 16.2 Version-to-directory map

| Version | Pipeline directory | Output directory |
|---|---|---|
| 1.1 | `main/stages/` | archived |
| 1.2 | `main/stages2/` | `output2/` |
| 1.3 | `main/stages3/` | `output3/` |
| 1.4 | `main/stages4/` | `output4/` |

### 16.3 Key quantities

| Quantity | Value | Source version |
|---|---|---|
| Sequences scanned in stage 0 | 849,416,450 | 1.3 |
| Candidate pool after preprocessing | 19,890,021 | 1.3 |
| Metagenomic share of the pool | 96.3% | 1.3 |
| Stage 0 duration | 98.7 min (5,924 s) | 1.3 |
| Candidate database size | 2.6 GB | 1.3 |
| Peptides entering assembly | 4,324 | 1.4 |
| Enumerated constructs | 25,944 | 1.4 |
| Final constructs | 250 (Top 150 + Bottom 100) | 1.4 |
| Total pipeline duration | ~65 h | 1.4 |
| Overall rejection rate | 99.9987% | 1.4 |
| Mean structural confidence | 0.42 (0.52 by independent validation) | 1.4 |
| Mean surface exposure | 0.72 | 1.4 |
| Mean aggregation propensity | 0.33 | 1.4 |
| Final score range | 0.4800 – 0.7579, mean 0.6327 | 1.4 |

---

*This document covers the `iGEM-silk` repository: PeptiCraft versions 1.1 through 1.4, the microservice layer those versions depend on, and the methodological commitments they established. The platform built on top of this work is described in the PeptiCraft 2.0 master reference in the `iGEM-website` repository.*

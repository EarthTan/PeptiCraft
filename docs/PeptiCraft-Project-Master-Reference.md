# PeptiCraft — Project Reference
## From a Single-Function Screening Pipeline to a Recombinant Protein Design Platform

---

## About this document

This document is the whole-project reference. It covers the work in one continuous account, from the original dry-lab question through four iterations of the screening pipeline, the evidence review that redirected the project, the four platform-scale pipeline runs, and the browser platform built on top of their output.

It sits above two version-level documents, which remain the detailed sources for their own repositories:

| Subject | Document | Repository |
|---|---|---|
| PeptiCraft 1.1 – 1.4, the screening pipeline | `docs/PeptiCraft-1.x-Master-Reference.md` | `iGEM-silk` |
| PeptiCraft 2.0, the platform | `docs/PeptiCraft-2.0-Master-Reference.md` | `iGEM-website` |

The three are designed to be used together. This document carries the arc — what the project set out to answer, what each stage changed, what each stage produced — and states the facts that belong to the project as a whole. Where a subject needs its full treatment, the section points to the version-level document rather than repeating it. Any submission document can be produced by excerpting from these three without returning to the source code.

Two conventions are observed throughout. Quantitative claims are stated with the stage and the run they belong to, because the stages operate on different data at different scales and a number quoted without that context will usually be wrong somewhere else. And where the project has a limitation, the limitation is stated with the number attached to it, in the same voice as the results, because a limitation that is described only as a concern cannot be judged.

---

## 1. The problem

### 1.1 A functional peptide is not a product

A short peptide with a desirable biological activity is not, by itself, a product. Its activity is real but its physical behaviour is not: a free peptide of ten to thirty residues has essentially no structural stability, is degraded quickly by proteases in any biological fluid, cannot be spun, cast or gelled into a material, and diffuses away from the site where it is needed.

The project's working hypothesis is that a functional peptide can be rescued by fusing it to a structural protein. The fusion protein inherits the mechanical and material behaviour of the scaffold — film formation, fibre formation, gelation, mechanical strength — and the peptide is carried along with it. The two halves are joined by gene fusion, so the product is a single recombinant polypeptide that can be expressed, purified and processed as one molecule, rather than a peptide loaded into a carrier.

The target is topical and cosmetic-material use: skincare and dressing products in which the antioxidant, antibacterial, anti-inflammatory or anti-melanogenic activity of the peptide is delivered by a protein material that stays where it is applied.

### 1.2 The three-part construct and why each part exists

Every construct in this project is one assembly of three sequence elements followed by a purification tag, and the reason there are three rather than two is worth stating, because it is the source of most of the design difficulty.

**The functional peptide** carries the activity. **The scaffold protein** supplies the material behaviour and determines what physical form the product can take — solution, gel, sponge, fibre or film. **The linker** is a short sequence joining them whose only job is spatial: without it, a peptide placed directly against the scaffold surface risks either being buried by a scaffold domain so that its active site cannot reach its substrate, or interfering with the scaffold's folding and destroying the material behaviour that was the point of the scaffold.

The three are coupled, which is what makes the design problem hard rather than merely tedious. Changing the peptide changes the hydrophobicity and charge distribution of the whole fusion protein and therefore its aggregation tendency; changing the scaffold changes the chemical environment the peptide sits in and therefore its apparent activity; changing the linker changes the relative orientation of the two ends. This is a joint selection problem over a combinatorial space, not three independent optimisations.

### 1.3 Three constraints fixed at the start

Three decisions were taken before any screening code existed, and they shaped everything that followed.

**Short peptides, three to thirty residues.** The upper bound is not a biological preference but a hard constraint imposed by the prediction models: several of the tools used cannot accept a longer sequence, and preprocessing therefore discards everything outside the window before any scoring happens. Within the window, short peptides have four favourable properties — solid-phase chemical synthesis is cheap at this length, small molecules penetrate tissue and cell membranes far better than large proteins, short peptides are generally less immunogenic, and a short peptide can be introduced by gene fusion with no chemical coupling step. The cost is that the peptide alone has neither stability nor material behaviour, which is the whole reason a scaffold is needed.

**Silk fibroin as the first scaffold.** Silk fibroin was chosen for four reasons that operate at different levels. Its mechanical behaviour comes from sequence rather than from a folded globular structure — the protein is built from alternating glycine-alanine and glycine-glycine-any-residue repeats, which stack into crystalline β-sheet separated by an amorphous matrix, so the material properties survive a great deal of sequence editing rather than depending on one fragile fold. It is biocompatible and degrades through ordinary proteolytic routes. It has an established recombinant expression route in *Escherichia coli* in the published literature, which makes the wet-lab half tractable rather than speculative. And it self-assembles into films and fibres under mild solvent conditions, which is what allows a liquid formulation to become a coating without a chemical cross-linking step.

**Non-systemic delivery.** The project deliberately restricts itself to routes that do not involve systemic exposure — topical, occlusive, wound-contacting, and hair-surface use — with injection included only as a cosmetic filler. This restriction is what makes the safety question tractable: the immune exposure of a construct depends far more on whether it crosses a barrier than on its sequence alone, and this becomes the organising principle of the platform's route system.

### 1.4 The computational shape of the problem

The screening problem is a hard-constrained multi-objective search over a very large sequence space. Two properties define it.

Almost everything is unsafe. In the first pipeline, more than 94% of an already-curated set of antioxidant peptides failed a safety criterion. Most of the natural and metagenomic short-peptide space is toxic, haemolytic, allergenic or immunogenic, so a search that optimises activity alone will return candidates that cannot be used — and will return them ranked highly, because activity and safety are not correlated.

Almost everything is unannotated. After applying the length filter to the two largest public sequence resources, 96.3% of the surviving candidates carry no functional annotation at all. The dominant contributor is a metagenomic protein-cluster resource, whose entries are predicted small proteins and short open reading frames: the sequence is real and would fold, but nobody has measured what it does. This is not a defect of the sources; it is what the three-to-thirty-residue window selects for when it is applied to a catalogue of full-length proteins on one side and a catalogue of predicted short proteins on the other. It does mean that experimental evidence is scarce and disproportionately valuable, and that the project's output is necessarily a set of predictions rather than a set of findings.

---

## 2. The project in one view

### 2.1 Four stages

The work divides into four stages, each of which changed the question rather than only the answer.

**Stage one — the screening pipeline.** A dry-lab funnel that takes a large pool of short peptide sequences, applies safety and developability criteria in succession, assembles the survivors into fusion constructs, and ranks them. It began scoped to one function on one scaffold and ran through four iterations, designated 1.1 to 1.4. It converged on a screening architecture that the later stages inherited wholesale, and it produced a ranked set of 250 candidate constructs.

**Stage two — the evidence review.** Before widening from one function to four, the project re-read the published evidence for every predictive tool it intended to use, rather than assuming the tools worked as advertised. This review refuted four working assumptions, reclassified the entire tool set by what each tool can actually support, and produced the architecture that the platform-scale runs follow. The review is the point at which the project stopped being a pipeline and became a platform design.

**Stage three — the platform-scale pipeline.** The same funnel, widened to four functional directions and re-run once per direction against the full twenty-million-peptide library, with the safety skeleton shared across directions and the functional funnel specific to each. These four runs produced the 496 constructs that the platform serves.

**Stage four — the platform.** A browser application that turns the pipeline's output into a guided decision process: a user states a product form, the platform derives the scaffold, and the result is a ranked shortlist with an assembled fusion sequence, a per-item safety verdict against that product's thresholds, and an explanation of every number.

### 2.2 Timeline

| Stage | Content | Output | Recorded |
|---|---|---|---|
| 1.1 | First funnel, single function, silk fibroin | 107 peptides surviving the hard filters; the design conventions that survived to the end | — |
| 1.2 | First end-to-end run | 150 constructs from 1,081,772 sequences, ~6.5 h | — |
| 1.3 | Scaling to the billion-sequence range | 849,416,450 sequences scanned, 19,890,021 candidates | — |
| 1.4 | Hierarchical filtering | 250 constructs, ~65 h, 99.9987% overall rejection | — |
| 2 | Evidence review of 18 predictive tools | Tool reclassification; the four-stage architecture; readiness determinations | 2026-09-05 |
| 3a | Platform run, antioxidant | 170 constructs (Top 113 + Bottom 57), all clearing the safety gates | 2026-09-05 |
| 3b | Platform run, antibacterial | 65 constructs (Top 7 + Bottom 58) | 2026-09-12 |
| 3c | Platform run, anti-inflammatory | 154 constructs (Top 87 + Bottom 67), pending signature | 2026-09-13 |
| 3d | Platform run, anti-melanogenic | 107 constructs (Top 83 + Bottom 24), pending signature | 2026-09-13 |
| 4 | Platform build and deployment | Five-surface application, 19 read-only endpoints, live deployment | 2026-09-17 onward |

The two halves of the timeline differ in character. Stage one took roughly sixty-five hours per complete run and was organised around survival. Stage three runs each completed in seconds, because by then the expensive work had been done once for the whole library and stored. That inversion — from a funnel that filters sequences to a pipeline that scores a library once and then slices it — is the single largest engineering change between the two stages.

### 2.3 The repositories

| Repository | Content | Relation to the project |
|---|---|---|
| `iGEM-silk` | Versions 1.1 – 1.4 of the screening pipeline, the microservice layer they call, and the methodological conventions they established | Stage one |
| `iGEM-website` | The PeptiCraft 2.0 platform: frontend, backend service layer, static data layer, deployment configuration and documentation | Stage four |
| `iGEM-website/iGEM-platform-main` | The pipeline run at platform scale: schema, run scripts, per-direction result archives and the evidence-driven multi-pipeline proposal | Stage three |
| `wiki` | The evidence base: for each of the eighteen predictive tools evaluated, its provenance, training data, reproduction record and applicable range | Stage two |

The microservice layer is worth locating precisely, because it is shared and therefore belongs to no single stage. Sixteen predictive services conform to three interface templates — sequence in and a score out, sequence in and a structure out, structure and sequence in and a score out — and every service belongs to exactly one template, recorded in a registry rather than inferred at the call site. The layer was built during stage one and is called by stage three unchanged. The evidence review reclassified what each service can support; it did not replace any of them.

### 2.4 The development process as a sequence of cycles

The project's progress is usually described as four versions and four stages, but the unit that actually produced change is smaller than that: a cycle in which a decision is taken, an artefact is built from it, the artefact is examined and something is found to be wrong or weaker than assumed, and the finding alters the next decision. In the vocabulary normally applied to this kind of work, that is a design–build–test–learn cycle, and the four legs are worth naming separately because they are not equally present in this project.

**Design** is the decision being tested: a round structure, a weighting convention, a deployment form, a binding rule. **Build** is the artefact: a pipeline version, a database, a service layer, an export format. **Test** is the examination. **Learn** is the change to the next design. A dozen such cycles are visible in the record, and their most consistent property is that none was planned as a cycle. Each was entered because a run had already finished or a build had already shipped, and each ended when an examination found something the design had assumed away.

The **test leg is where this project differs from a wet-lab project, and the difference is specific.** Three kinds of examination stood in for an assay. The first is arithmetic: comparing the stored results against what the design intended, which is how both version 1.2 errors were found — a safety term with a coefficient smaller than the activity advantage it was supposed to override, and a functional term still present in the rounds that were supposed to be free of it. Neither was visible in a failure, because neither produced one. The second is independent re-prediction: running the top ten of each channel through a second structure model, which is what establishes that the ranking is not an artefact of one predictor. The third is assertion: verification suites that check the implementation against the contract in three separate layers, which is how the platform's threshold drift and export discrepancies were caught.

All three can refute a design decision, and each did. None can confirm that a peptide has the activity claimed for it. **The leg that has not run is the experimental one**, and because of that the cycles below are design–build–learn cycles with a computational test leg rather than complete four-leg cycles in the experimental sense. That distinction should travel with any description of the project's iteration, because it is the difference between a design that has survived examination and a design that has survived contact with a wet-lab result.

| Cycle | What was designed and built | What the examination found | What changed next |
|---|---|---|---|
| 1.1 | A six-phase funnel over 1,843 curated antioxidant peptides | The hard filters alone removed 94% of the set; the remaining phases had a ceiling of a few hundred constructs | The pool was too small to be worth finishing; the design conventions were carried forward and the run was abandoned |
| 1.2 | An eight-round funnel with a matched control channel; the first end-to-end run | 150 constructs in 6.5 h; the arithmetic of the stored results showed a compensable safety term and a leaking functional term | Both errors were fixed structurally in 1.4, not by adjusting coefficients |
| 1.2, within round | A toxicity check on the full pool; two structure predictors in parallel; a construct-level composite at half the final weight | The estimate was 22 h against a budget of hours; the fast predictor returned confidence below 0.30 and contended for memory; the composite's interquartile spread was 0.011 | Toxicity moved to the reduced pool; one predictor run serially; the composite removed and the ranking rebuilt on three structural terms |
| 1.3 | A streaming import of 849,416,450 sequences into a columnar database | 19,890,021 candidates in 98.7 min; 96.3% of them metagenomic; identity clustering removed at most 5% | The pool was accepted unclustered; variance-aware weighting and database-backed state were introduced and carried into 1.4 |
| 1.4 | Hierarchical filtering: one criterion per round, safety as a veto, one weighted average with data-derived weights | 250 constructs from 19,890,021; the control channel outscored the selected channel; confidence capped at 0.50; one top-ranked peptide turned out to be a purification handle | A candidate-drawing instruction rather than a re-ranking; the structural track's limits stated as intrinsic to the material rather than as tooling quality |
| Evidence review | The tool set re-read against its published evidence rather than its documentation | Four assumptions refuted: that the funnel transplants directly, that a best tool can serve as a gate, that developability predictors hold on short peptides, that the four directions are equally ready | The four-segment architecture; percentile cuts instead of thresholds; two directions marked pending rather than cancelled |
| Antioxidant run | The shared safety skeleton plus a direction-specific funnel, over a 2,024,889-peptide pool | The class II pathway was not yet connected and the epitope table was empty, so the data-driven weighting drove epitope's weight to 0.00 | Recorded as a consequence of which tools were loaded; later runs added the missing gate |
| Antibacterial run | The same architecture with a second functional channel as a cross-check | 47% of the 250 highest-scoring peptides failed a safety gate; the selected channel fell to 7 constructs | The result stands; it is the project's clearest measurement that activity and safety are independent |
| Anti-inflammatory and anti-melanogenic runs | The same architecture, on the only usable functional channel in each direction | The available models answer a weaker question than the direction's name implies | An ordering-only marker written into the data and the interface, and no pass-or-fail badge on those scores |
| Platform cycles one to four | A frontend rendering a hard-coded dataset; thresholds held in the pages; ranking performed in the browser | An audit found three defect classes caused by copied values, including a gate that read as a pass when the route was unspecified | Static data deleted; thresholds centralised in one layer; ranking moved to the server; two inconsistencies given one default |
| Deployment change | Data exported once to static files, with one edge function for conversation | Three defects specific to the new form: a snapshot shadowing the live service, export rows missing the columns search used, and number notation differing between the two languages | A resolution order for the data source; an export contract guarded by test; one shared case table for notation |
| Scaffold binding | A route-keyed binding strategy, generated as executable SQL | The two identifier systems have no overlap and no shared names, so no identifier change could bridge them | The binding became a per-route default labelled as inferred, distinct from a binding the pipeline recorded |

The pattern across all of them is the same, and it is the project's main claim about its own process: **each cycle removed a class of defect by changing where a decision lives, rather than by patching the instance that surfaced.** The safety threshold moved from four pages into one service layer, so it can no longer drift. The composite moved from the browser to the server, so it can no longer depend on which page was open. The weights moved from a configuration table into the pool's own spread, so they can no longer be chosen after seeing the result. A cycle that ends in a changed number is a fix; a cycle that ends in a moved decision is a design change, and the second kind outnumbers the first by a wide margin in this record.

---

## 3. Stage one: the dry-lab pipeline, four iterations

The four versions are not four attempts at the same thing. Versions 1.1 and 1.2 are attempts to make a funnel run at all. Version 1.3 is an attempt to make the funnel scale to the billion-sequence range, and it introduced the measurement apparatus without itself reaching the end of the funnel. Version 1.4 is the version that fixed the two design errors version 1.2 had exposed, and it is the only version whose full output is treated as a result.

### 3.1 Version 1.1 — the first funnel

The first pipeline was scoped to a single question: from 1,843 peptides already annotated as antioxidant, which ones are safe enough and promising enough to justify building a fusion construct around. It was written as six orchestrated phases and seven stage scripts.

Its governing rule, inherited by every later version, is to **put the cheap work first**. The reasoning is arithmetic rather than aesthetic: a tool processing two thousand sequences per second and a tool processing twenty-five per second differ by a factor of eighty, which on twenty-five thousand sequences is the difference between under a minute and several hours. Ordering work by throughput rather than by conceptual importance is therefore the main determinant of whether a run finishes.

Phase one applied the three hard filters — toxicity, allergenicity and haemolysis prediction. The first two are effectively free, being millisecond-scale operations on one- and two-megabyte models; the third requires loading a fine-tuned language model but is otherwise cheap. Running them first costs seconds and removes a large fraction of the pool before anything expensive touches it. Phase two scored the survivors on several properties and combined them with hand-assigned weights. Phases four to six enumerated constructs, predicted their three-dimensional structure and evaluated surface exposure and aggregation on that structure. The remaining phases were written but not executed, because the project moved on to a scaled-up pipeline rather than completing a run whose ceiling was a few hundred constructs.

Three engineering decisions taken at this stage survived to the end and explain why the later pipeline is shaped as it is. **Scripts are independent and file state is the memory** — each stage is a standalone runnable module with its own input, output and report, because the work is executed across many sessions and state has to live on disk rather than in a conversation. **Every elimination is recorded with its cause** — discarded candidates are written out with the tool and score that removed them, which is what makes the funnel auditable afterwards and what allows a rejection rate to be stated per round rather than overall. And **structure prediction is treated as the ceiling** — the step that determines the total cost of a run, with a cheap predictor for the bulk of the work and a high-accuracy predictor reserved for a handful of final candidates.

The one result this version produced is the clearest illustration of the funnel's premise. Of the 1,843 curated antioxidant peptides, 107 survived: 656 were removed for predicted toxicity, 1,077 for predicted allergenicity and 3 for predicted haemolysis. More than 94% of an already-curated antioxidant set fails a safety criterion.

### 3.2 Version 1.2 — the first complete run

Version 1.2 was the first pipeline to run end to end on real data. It took 1,081,772 candidate sequences through eight rounds and produced 150 assembled constructs in about six and a half hours, and it introduced a shared utilities module and a checkpoint file so that a run interrupted by a service failure could resume rather than restart.

| Round | Function | Input → output | Time |
|---|---|---|---|
| 0 | Integration, length filter, deduplication | 1,081,772 → 1,055,116 | ~30 s |
| 1 | Lightweight scoring: antioxidant + allergenicity | 1,055,116 fully scored | ~15 min |
| 2 | Dual-channel split and safety scoring | 1,055,116 → 50,000 (25,000 top + 25,000 bottom) | ~63 min |
| 3 | Heavy scoring and selection | 50,000 → Top 80 + Bottom 10 peptides | ~65 min |
| 4 | Construct enumeration and construct-level rescoring | → 150 constructs | ~13 min |
| 5 | Three-dimensional structure prediction | 150 → 150 structure files | ~210 min |
| 6 | Structure evaluation | 150 structures scored | ~6 min |
| 7 | Final dual-channel ranking | → 90 Top + 60 Bottom | ~1 min |
| | **Total** | **1,081,772 → 150 constructs, 99.986% rejected** | **~6.5 h** |

Five decisions taken here are worth recording because each was a correction rather than a first attempt.

**Toxicity prediction was moved out of the first round.** The original plan ran it on the full 1,055,116 sequences. The predictor is a single-threaded, CPU-bound tree ensemble and the estimate for that workload was roughly twenty-two hours against a total budget of a few hours. Moving it to round 2 on a 50,000-sequence subset brought it to about forty-eight minutes with no effect on the final result, because every sequence reaching round 2 has already been selected on antioxidant activity.

**The dual-channel split used the raw antioxidant score, not a weighted total.** The components have incompatible units and incompatible degrees of separation, so blending them before selection hides the quality of the thing being selected for. Ranking on the single directly measured quantity preserves the interpretation of the split.

**The dual channel exists to make the result falsifiable.** Both a top channel and a bottom channel run through the entire pipeline. The bottom channel is not a by-product; it is a set of candidates predicted to be poor, carried forward under identical processing so that they provide a matched baseline. If the high-activity channel and the low-activity channel behave the same way in a wet-lab assay, the pipeline's central assumption is refuted. This is a design property rather than a claim.

**Structure prediction used one tool rather than two.** On this class of sequence the fast predictor returned confidence below 0.30, below the level at which downstream surface-exposure and aggregation measurements carry any information, while consuming most of the available accelerator memory and contending with the other predictor even when producing nothing usable. Removing it and running the remaining predictor serially was both faster and more stable, and cut accelerator time by roughly half.

**An intermediate construct-level composite was removed from the final ranking.** It had been assigned half the final weight, but inspection of the top ninety showed it was nearly constant across them — a spread of 0.011 between the 25th and 75th percentile — so at half weight it was effectively deciding the ordering on noise and diluting the two quantities that did discriminate. The final ranking was rebuilt on three structural terms at weights 0.40, 0.40 and 0.20.

That three-term ranking is the ancestor of the platform's composite. Its important property is what it leaves out: it contains no functional term. Antioxidant prediction is used once, to assign a channel, and never again.

The run produced 90 top-channel and 60 bottom-channel constructs from 150 enumerated. Structural confidence averaged 0.41, mean peptide surface exposure 0.70, mean aggregation propensity 0.35. The five highest-ranked constructs by the final score were `con_0215` (0.7794), `con_0199` (0.7684), `con_0226` (0.7345), `con_0201` (0.7224) and `con_0095` (0.7142).

### 3.3 Version 1.3 — scaling to the billion-sequence range

Version 1.3 moved the funnel's entrance from a million sequences to the billion-sequence range, and it changed the pipeline's substrate rather than its logic. The source material was the two largest public protein sequence resources: 225,619,586 sequences from a curated reference proteome and 623,796,864 from a metagenomic protein-cluster resource, together 849,416,450 sequences.

Its first stage streamed both files, retained only sequences of three to thirty residues composed of the twenty standard amino acids, and wrote the survivors into a columnar analytical database. It ran in 5,924 seconds — 98.7 minutes — and produced 19,890,021 candidates in a 2.6 GB database file, at roughly 143,000 sequences per second scanned.

The two sources behaved completely differently, and the reason determines the composition of every downstream result.

| Source | Sequences scanned | Length-passing | Written after residue filter | Pass rate |
|---|---|---|---|---|
| Curated reference proteome | 225,619,586 | 744,565 | 733,573 | 0.33% |
| Metagenomic clusters | 623,796,864 | 19,156,521 | 19,156,448 | 3.07% |

A catalogue of full-length proteins loses almost everything to a thirty-residue ceiling, because almost all of its entries are far longer; a catalogue of predicted small proteins and short open reading frames passes almost everything. The result is that 96.3% of the surviving candidate pool is metagenomic and 3.7% is annotated. This ratio is not a design choice; it is a consequence of applying a thirty-residue ceiling to two databases with different length distributions. One planned reduction step — clustering at 90% identity to remove near-duplicates — was tested and abandoned, because short peptides are too diverse for identity clustering to have much to remove, achieving between 0.2% and 5% reduction at a cost the project did not consider justified.

The version's lasting contribution is the measurement and recovery machinery it introduced, all of which was carried into version 1.4.

**Variance-aware weighting.** This is the origin of the rule that weights are computed rather than configured. Each component is normalised within the candidate pool, oriented so that larger is better everywhere, and then weighted by its winsorised standard deviation — the standard deviation computed after truncating extreme values to the 5th and 95th percentiles, so a single outlier cannot dominate a component's weight. The effect is that a component with real spread in a given pool is automatically up-weighted and a component that is nearly constant is driven toward zero. This is preferable to an arrangement in which someone assigns a nearly constant component a weight of 0.2 and thereby spends a fifth of the composite on a quantity that cannot separate anything.

**Database-backed state with checkpoint and resume.** Moving state from files into a database made three things possible at once: intermediate results can be queried rather than read sequentially, a run failing after fourteen hours can resume from the last completed unit, and a later stage can read a consistent snapshot while an earlier stage is still writing. The last required an explicit workaround, because the engine admits only one writing connection at a time; the solution is to copy the database file and read the copy.

**On-demand service startup.** Running every microservice continuously leaves an accelerator context allocated per service, which accumulates until the device is full. The fix is to declare per stage which services that stage requires and start only those, which in practice reduces a round to between two and five live services out of the sixteen available.

**Idempotent writes.** Every result write is an upsert keyed on the candidate identifier, so a batch can be re-run without producing duplicates and different rounds can write different columns of the same row without overwriting each other.

**Progressive persistence.** Batches are written as they complete rather than accumulated in memory for a single final write. The rule is stated as an assumption about failure: a run that takes a day will fail somewhere, and the only question is how much work is lost. Batch size is therefore the amount of work one is willing to recompute.

The later stages of this version were designed in detail but not executed, because version 1.4 was designed against the same 19.9-million-candidate pool and incorporated the corrections to version 1.2's errors. The candidate database produced here is nonetheless the input to version 1.4.

### 3.4 Version 1.4 — hierarchical filtering

Version 1.4 is the project's final pipeline and the one whose output is treated as a result. It takes the 19,890,021-candidate pool and converges it on 250 constructs in about sixty-five hours. Its design is a direct response to the two errors version 1.2 exposed, and it replaces blending with sequencing.

**Version 1.4's five governing principles**

**Hierarchical filtering, never cross-attribute averaging.** Each round applies a single criterion: it either sorts and takes a percentile, or it applies a threshold and eliminates. No round mixes different properties into one number. The reasoning is that a blend is only meaningful when the components share a unit and a direction, and attributes as different as antioxidant activity and haemolysis risk share neither.

**Safety is a hard threshold.** Toxicity, haemolysis, allergenicity and immunogenicity receive only a pass-or-eliminate decision. They are not scored, not weighted and not compensable.

**The functional score is used once.** Predicted antioxidant activity is used in round 1 and nowhere else, so that the two channels remain independent and so that selecting for the property being studied does not quietly continue into the ranking of the molecules that carry it.

**The pipeline has exactly one weighted average, and its weights come from the data.** Round 3 is the only place where different attributes are combined, and its weights are proportional to each attribute's winsorised standard deviation, with an optional manual coefficient that must be recorded together with a stated reason. A manual adjustment is invalid without a recorded justification, which is a rule against tuning the weights after seeing which constructs won.

**Order by cost.** Cheap, high-throughput work runs first; the most expensive work runs last on the smallest set.

**The rounds**

| Round | Criterion | Method | Time |
|---|---|---|---|
| 0 | Length and residue type | Import from version 1.3's candidate pool | ~15 min |
| 1 | Antioxidant activity, plus allergenicity as a hard filter | Sort on the raw score; top 10% → Top channel, bottom 1% → Bottom channel; allergenicity ≥ 0.30 eliminated | ~30 min |
| 2 | Safety | Three independent hard thresholds: toxicity < 0.38, haemolysis < 0.55, immunogenicity < 0.50; any failure eliminates | ~24 h |
| 3 | Developability | Four properties scored, then combined by winsorised-standard-deviation weights — the pipeline's only weighted average | ~5 h |
| 4 | Construct assembly | Enumerate position × linker; rescore solubility and thermal stability on the assembled full-length protein | ~6.5 h |
| 5 | Structure | Predict the three-dimensional structure of every surviving construct | ~6.1 h |
| 6 | Structure evaluation | Surface exposure and aggregation propensity | ~5.4 min |
| 7 | Final ranking | Combine the three structural terms; rank each channel independently | < 1 s |
| 8 | Cross-validation | Re-predict the top ten from each channel with a second, independent structure model | ~22.5 h |
| | | **Total** | **~65 h** |

Three features of this structure carry most of its meaning.

**The channel asymmetry is deliberate.** The top ten percent of round 1 goes into the Top channel and the bottom one percent into the Bottom channel. The Top channel is a candidate pool and can afford to be generous; the Bottom channel only has to be large enough to provide a matched negative control, and roughly 199,000 sequences is already far more than that.

**Round 2 is the bottleneck, and it is also the design's clearest statement on safety.** The toxicity check accounts for almost all of the round's duration, because the model is a single-threaded CPU tree ensemble and processing the survivors takes on the order of a day. The check runs a second time as a pre-screen inside round 3, where it eliminates a further 16,982 peptides — 16.4% of what had reached that point — which is a reminder that the first pass and the second pass operate on different populations.

**Round 4 exists as a separate step because a free peptide is not the molecule that would be made.** The highest-ranked peptides are each assembled in all six combinations of insertion position and linker, and the developability predictions are then re-run on the complete fusion protein rather than on the free peptide. A peptide that is stable and soluble on its own need not behave the same way once attached to a 364-residue scaffold.

**The final score**

```
round7_score = 0.40 × SASA + 0.40 × (1 − Aggrescan3D) + 0.20 × pLDDT_norm
```

Surface exposure is the relative solvent-accessible surface area of the functional peptide within the folded construct, computed by rolling a probe of 1.4 Å over the structure and dividing each residue's accessible area by the maximum that residue type can expose; higher is better, because a peptide buried in the scaffold's core cannot reach the species it is meant to react with. Aggregation propensity estimates how strongly the protein tends to clump; lower is better, because an aggregating protein expresses poorly and purifies badly, so the term enters inverted. Structural confidence enters at half the weight of the other two, on the reasoning that confidence should temper the other terms rather than drive them — a predicted structure is evidence about a construct, not the construct itself.

The most important property of this score is what it does not contain. There is no functional term of any kind. It is a statement about physical quality — will this fold, will it stay soluble, will the peptide be reachable — and no statement about antioxidant strength can be read off it.

**The funnel and the result**

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

Across all 250 constructs the final score spans 0.4800 to 0.7579 with a mean of 0.6327; within the Top 10 it spans 0.7076 down to 0.6642, a spread of 0.043. Round 8's independent re-prediction of the top ten of each channel returned a mean confidence of 0.52 against 0.42 for the primary model, with the same trend and the same ordering at the top, which is the evidence that the ranking is not an artefact of one predictor.

The five highest-scoring constructs overall are `con_5489` (0.7579), `con_3275` (0.7420), `con_1415` (0.7342), `con_15869` (0.7296) and `con_1103` (0.7189). The five highest within the Top channel are `con_0418` (0.7076), `con_0417` (0.6993), `con_0317` (0.6918), `con_0850` (0.6893) and `con_0558` (0.6723).

### 3.5 What the four iterations changed

| Dimension | 1.1 | 1.2 | 1.3 | 1.4 |
|---|---|---|---|---|
| Input scale | 1.8 × 10³ | 1.1 × 10⁶ | 8.5 × 10⁸ scanned | 2.0 × 10⁷ |
| Output | 107 peptides | 150 constructs | candidate database | 250 constructs |
| Rounds | 6 phases | 8 | 6 planned | 9 |
| Weighting | manual, fixed | manual, fixed | winsorised standard deviation | winsorised standard deviation, in one position only |
| Safety handling | hard filter, then weighted | hard filter, then weighted | hard filter | hard veto, never weighted |
| Functional score reuse | once, in the weighted total | four times | once | once |
| State | files and status pointers | files and a checkpoint | database, 15 tables | database, 30+ tables |
| Recovery | manual, per stage | checkpoint file | checkpoint and resume, snapshot for parallel readers | checkpoint and resume, progressive writes |
| Service lifecycle | batched start, stopped before structure work | on demand | on demand, declared per stage | on demand, declared per stage |
| Structure prediction | planned | one predictor, serial | planned | one predictor serial, plus independent validation |

The trajectory is a shift from questions of speed to questions of correctness. Version 1.1 asked how to order work so a run finishes. Version 1.2 asked how to make a run survive interruption. Version 1.3 asked how to make the same run survive two orders of magnitude more input. Version 1.4 asked what the pipeline should be computing at all, and answered by removing blending from every position except one and by making the weights a property of the data.

### 3.6 The two design errors version 1.2 exposed

Both findings are errors of composition rather than of execution, and both were detected by inspecting the arithmetic of the stored results rather than inferred from the design documents.

**Safety attributes could be outvoted.** The composite in rounds 2 and 3 combined antioxidant activity, toxicity, allergenicity, haemolysis, immunogenicity, epitope propensity and thermal stability into a single weighted total, with the safety terms carrying small coefficients — haemolysis at 0.09, immunogenicity at 0.05, toxicity at 0.13. In that arrangement a peptide with a severe haemolysis signal but a very strong antioxidant score can still finish near the top, because the haemolysis penalty is smaller than the antioxidant advantage. Safety had been implemented as a score, and a score can be compensated. The correct treatment is a threshold: pass or eliminated, with no participation in any average.

**The antioxidant signal leaked past the split.** Although the channel assignment correctly used the raw antioxidant score, the composite used for ranking in rounds 3 through 7 also contained an antioxidant term, at the largest coefficient in the table. The bottom channel therefore continued to be ranked partly on the property that defined it as the bottom channel, which means the two arms were not independent and the comparison the design was built to enable was weakened.

Both were addressed in version 1.4 by changing the pipeline's structure rather than by adjusting coefficients — which is where principles A and C above come from.

### 3.7 Two results that require explanation

**The eight highest-scoring constructs in the entire run belong to the Bottom channel.** The best of them outscores the best Top-channel construct, and the Bottom channel is ahead on confidence, solubility, thermal stability and the composite score by a margin large enough to be robust across the final set. This is a direct consequence of the score containing no functional term: antioxidant prediction and structural quality are simply not correlated in this pool, and the bottom-channel population is not different from the top in any way that structure prediction can see. It is a property of the score, not a defect of the run. The practical conclusion is a wet-lab instruction rather than a caveat — candidates should be drawn from both channels, and a plan that draws only from the top ten of the Top channel is testing the wrong population.

**The top two constructs in the Top channel carry a sequence that is not a functional peptide.** The peptide `MNRPWITGHHHHHHHRRRRRRRRRR`, carried by `con_0418` and `con_0417`, is twenty-five residues of a short serine-rich leader followed by six histidines and nine arginines. That composition is characteristic of a purification or cloning handle, not of a bioactive antioxidant peptide. It entered the pool because preprocessing filters on length and residue type only, and this sequence satisfies both; it survived round 1 on a middling-to-high antioxidant prediction; and it reached the top of the structural ranking because structural ranking never examines what a peptide does. The two entries are the same peptide at the same position, differing only in linker length, which is why they occupy channel ranks 1 and 2 with near-identical scores. Any document quoting the top of that table carries an obligation to flag this entry explicitly or to quote it with the qualification attached. A stronger pair of candidates for wet-lab work is `con_0850`, the highest on the independent structure validation at 0.56, and `con_0317`, which matches `con_0418`'s structural quality among constructs carrying a plausible peptide.

**One further qualification travels with any description of this pipeline's structural track.** Mean structural confidence is 0.42 and the maximum is 0.50, on a scale where 0.50 marks the edge of meaningful confidence, and the independent second model returns 0.52. This is not a failure of the constructs but a property of silk fibroin: the scaffold is built from glycine-alanine repeats that adopt a disordered, partly amorphous fold with no natural structural template for a folding predictor to work from. The structures underpinning the final score are therefore low-confidence models, and the score is properly described as a consistent way to rank imperfectly modelled structures rather than as a precise physical measurement. The ceiling cannot be raised by using a better tool, because the limit is the disorder of the repeats rather than the quality of the predictor.

---

## 4. Stage two: what the evidence review changed

The platform-scale runs did not reuse the stage-one funnel unchanged. Before widening from one functional direction to four, the project re-read the published material behind every predictive tool it intended to use, and the review (recorded 2026-09-05) refuted four working assumptions that had seemed obvious from the project's own description of itself.

### 4.1 Four working assumptions, and what refuted them

**Assumption: the funnel can be transplanted directly.** The first stage was an eight-round funnel and the platform excludes the last four rounds, so the natural assumption was that the first four transfer intact. The evidence did not support it. The tool mix that the first four rounds depend on had changed — different functional predictors, different coverage, different failure modes — and reusing the round structure would have carried the earlier round's assumptions into a library with different properties. The correct move was to keep the principles and rebuild the round structure around the tools that actually work on this library.

**Assumption: each direction should be given its best tool as a hard gate.** Using a single strong functional predictor as a pass/fail line is the intuitive design. It fails on this library for a specific reason: the functional predictors were trained to separate typical database peptides from random fragments, not to separate active peptides from inactive ones, and on a twenty-million-peptide library of real short sequences their thresholds behave nothing like their reported accuracies. One predictor's threshold at 0.5 marked 72.83% of the library as positive; another marked 99.5%. A threshold that admits three-quarters or almost all of a library is not a gate. The correct use of a functional predictor on this material is ranking and a percentile cut, never a probability threshold.

**Assumption: the developability tools work on short peptides.** The tools are sequence-based scorers, so they appear applicable. In practice several were trained exclusively on full-length proteins and degenerate on short sequences: one returns a single peak pinned at 0.5 across the whole three-to-thirty-residue range, carrying no signal at all; another measures whether a recombinant protein forms inclusion bodies when expressed in *Escherichia coli*, which is not the same question as whether a free peptide is soluble in water; and two require a three-dimensional structure, which short peptides do not have. Only one developability predictor was found to hold directly on short peptides. Developability therefore had to be split into three tiers — usable at peptide level, usable only at construct level after assembly, and out of scope because it needs a structure.

**Assumption: the four directions are equally ready.** The four directions differ not in model maturity but in whether a clean training benchmark exists at all. Three candidate anti-inflammatory models were all found unusable: two learned the shortcut "is this a functional peptide" rather than "is this anti-inflammatory", because their negative examples were random fragments rather than confirmed non-anti-inflammatory functional peptides, and the third had a training set overlapping the project's own test set. This is a benchmark defect, not a model defect — the same representation performs at a usable level on independently collected data — and it means the anti-inflammatory direction is blocked on data rather than on compute. A second direction had a single weak candidate available, uncalibrated and requiring a wet-lab loop before it could be trusted.

### 4.2 The reclassification of the tool set

The outcome of the review is a single table that determines what every tool is allowed to do.

| Tool | Dimension | Role in the pipeline | Readiness |
|---|---|---|---|
| ToxinPred3 | safety, toxicity | hard veto | usable, with a length and source bias to annotate |
| HemoPI2 | safety, haemolysis | hard veto | usable, threshold to be fixed |
| MHCflurry | safety, MHC class I | hard veto at multi-allele best case | usable, recomputed across alleles |
| NetMHCIIpan | safety, MHC class II | soft risk signal only | ranking only; the binding-grade label loses its meaning on this library |
| AlgPred2 | safety, allergenicity | soft signal | low third-party specificity; reported, never a gate |
| BepiPred-3.0 | safety, B-cell epitope | soft feature | continuous score only; absolute value untrusted |
| AnOxPePred | function, antioxidant | supporting confirmation | weak; high specificity, so used as conservative confirmation |
| AOPxSVM | function, antioxidant | primary ranking | usable, but not at its own threshold |
| AMPlify | function, antibacterial | primary ranking | deployable; biased toward cationic amphipathic peptides |
| AIP-iFeature-LightGBM | function, anti-inflammatory | unavailable | benchmark defective |
| AIP-ESM2 | function, anti-inflammatory | unavailable | same defect reproduced with a different representation |
| iMFP-LG | function, anti-inflammatory | unavailable | training leakage |
| TIPred | function, anti-melanogenic | unavailable | no enrichment power on this library |
| BLSAM-TIP (locally rebuilt) | function, anti-melanogenic | weak ranking, pending calibration | uncalibrated; ordering only |
| pLM4CPPs | developability, membrane crossing | effective feature | usable; precision about 50%, so a ranking feature rather than a filter |
| TemStaPro | developability, thermal stability | construct level | no signal on three-to-thirty residues; usable on the assembled protein |
| SoDoPE | developability, solubility | construct level | meaningful on the fusion protein, not on the free peptide |
| Aggrescan3D / SASA | developability, aggregation and exposure | out of scope | require a three-dimensional structure |

The reclassification is the project's most consequential piece of analysis, because it converted "eighteen tools are available" into "three tools can eliminate a candidate, two can rank, one can rank weakly, and the rest can inform". Everything about the platform's safety semantics follows from that sentence.

### 4.3 The architecture that came out of it

The revised architecture is four segments rather than one linear funnel.

```
[Shared safety skeleton]        hard vetoes, identical for every direction
        ↓
[Direction-specific funnel]     ranking and a percentile cut, per direction
        ↓
[Delivery-weighted developability]  weights and thresholds set by the application route
        ↓
[Construct assembly]            peptide + linker + scaffold, then construct-level rescoring
```

The important structural change is that the safety skeleton is **shared** and the functional funnel is **specific**. Safety depends on the peptide's sequence, not on why it is wanted, so a candidate that fails a safety criterion fails it identically in all four directions. Activity depends on biology that differs per direction, so each direction has its own predictor, its own percentile cut and its own readiness determination. The third segment is where the platform's route system enters the pipeline: the application route determines which developability components are up-weighted and how tightly immunogenicity is bounded, which means the same peptide can rank differently, and can be vetoed or cleared, depending on the product form it is intended for.

Two further rules from the review constrain the implementation. The composite follows the three commitments established in stage one — safety is a veto, each metric is used exactly once, and weights are derived from the data by winsorised standard deviation with at most one recorded manual coefficient. And each direction's readiness determines whether it produces a ranked candidate set at all: a direction whose functional model cannot be trusted produces a set marked as pending, rather than producing nothing or producing a set presented as equal to the others.

### 4.4 The readiness determinations

| Direction | Functional signal | Readiness | Consequence |
|---|---|---|---|
| Antioxidant | AOPxSVM as primary ranking, AnOxPePred as conservative confirmation | ready | produces a ranked candidate set; all constructs cleared the safety gates |
| Antibacterial | AMPlify, with a second channel as cross-check | ready, model deployment pending | produces a ranked candidate set; the selected channel is thin because the predictor's score distribution is narrow |
| Anti-inflammatory | the only usable channel is a multi-label model with known leakage and a fragment blind spot | pending signature | produces a ranked set labelled as ordering only, not as a probability |
| Anti-melanogenic | a locally rebuilt ranking model, uncalibrated | pending signature | produces a ranked set labelled as ordering only, not as a probability |

The distinction between the last two is worth stating precisely, because it is the difference between a data gap and a data caveat. The anti-inflammatory and anti-melanogenic directions have data; what they lack is sign-off, because the models behind their scores are known to answer a weaker question than the direction's name implies. A multi-label model of this kind discriminates **whether a sequence looks like a known functional peptide**, not **whether it suppresses inflammation**; a high score means the sequence sits near known anti-inflammatory peptides in feature space. Both the data and the interface carry that marker, and neither direction issues a pass-or-fail badge on its functional score.

---

## 5. Stage three: the platform-scale pipeline

Stage three applies the architecture of section 4.3 to the full twenty-million-peptide library, once per direction. Its output is the 496 constructs the platform serves.

### 5.1 The four runs

The library is 20,248,885 peptides, from one residue to thirty. A direction's candidate pool is the top ten percent of the library by that direction's functional score, which is 2,024,889 peptides. Against that pool the runs apply the shared safety skeleton and the direction's own funnel.

| Run | Date | Duration | Selected channel | Control channel | Total | State |
|---|---|---|---|---|---|---|
| antioxidant | 2026-09-05 | 8 s | 113 | 57 | **170** | all passed |
| antibacterial | 2026-09-12 | 31 s | 7 | 58 | **65** | all passed |
| anti-inflammatory | 2026-09-13 | 40.3 s | 87 | 67 | **154** | all pending signature |
| anti-melanogenic | 2026-09-13 | 17.8 s warm, 113 s cold | 83 | 24 | **107** | all pending signature |
| | | | **290** | **206** | **496** | |

Two numbers in that table need reading carefully. Each run targeted 150 selected and 100 control constructs per direction; the totals are short of 250 in every direction, and the shortfall concentrates in the selected channel. The antibacterial direction is the extreme case, with seven selected constructs against a target of one hundred and fifty. The cause is visible in the run record: 47% of the two hundred and fifty highest-scoring peptides by the antibacterial predictor were eliminated by the safety gates, so only seven both cleared a high percentile cut and satisfied the gates. That single number is the clearest evidence the project has that a strong functional score says nothing about safety, and it is the reason the two are handled by separate mechanisms.

The durations are of a different order from stage one because the expensive work had already been done once for the whole library and stored. Scoring twenty million sequences with a dozen tools is a pre-computation; the run that produces constructs from it is a sequence of queries and one assembly step. One direction's run took 113 seconds cold against 17.8 seconds warm, the difference being index preheating for a score table it reads.

### 5.2 The safety skeleton, and why its coverage differs by direction

The shared safety skeleton is three veto items plus two non-vetoing signals, and the difference between them is the project's most substantive methodological commitment.

| Item | Tool | Threshold | Direction | Type |
|---|---|---|---|---|
| Toxicity | ToxinPred3 | 0.38 | lower is better | hard veto |
| Haemolysis | HemoPI2 | 0.55 | lower is better | hard veto |
| MHC class I immunogenicity | MHCflurry | 0.50, tightened to 0.35 under two routes | lower is better | hard veto |
| MHC class II immunogenicity | NetMHCIIpan | strong-binder sub-boundary at the 2nd percentile | **higher is better** | soft signal |
| Allergenicity | AlgPred2 | 0.30 | lower is better | reported only |
| B-cell epitope | BepiPred-3.0 | 0.1512 | lower is better | reported only |

Three things about this table matter more than the numbers.

**The toxicity threshold is the only threshold in the system that is the project's own decision.** The tool's default admits a set of candidates this library does not support; the whole library was scored, the distribution inspected, and 0.38 chosen as the value that suppresses both false negatives and false positives on this distribution. Every other threshold is either the tool's own recommendation or a route convention.

**The MHC class II gate runs in the opposite direction to every other gate.** The tool outputs a percentile rank in which a smaller number means stronger binding, and strong class II binding is the route by which helper T cells are recruited and an immune response initiated, so passing means the rank is above the strong-binder sub-boundary. Any implementation that writes "above the limit means exceeding" without checking the direction states the opposite conclusion on this gate. NetMHCIIpan is also the tool whose framing changed most under scrutiny: on this library 94.48% of peptides fall in the weak-binding band, because the library's sequences are more MHC-II-like than random natural peptides, so the ordinary binding-grade labels lose their meaning and the cross-allele percentile rank is the only stable scale.

**Coverage differs by direction, and the first run shows it.** The antioxidant run was executed before the class II pathway was connected, so its construct set carries no class II measurement at all; the antibacterial run, one week later, includes the class II gate as a fourth veto and is the only direction whose constructs all passed four gates. A second tool, the B-cell epitope predictor, had no rows in the library when the antioxidant direction ran. The data-driven weighting handled this exactly as designed — a component with no measurement drops out and its weight goes to zero — and the recorded outcome is that the antioxidant composite contains no epitope contribution, with epitope's computed weight at 0.00 against 0.31 for membrane crossing, 0.30 for allergenicity and 0.39 for aggregation. That is an honest consequence of which tools were loaded, and it must be described as such rather than reported as a modelling result.

### 5.3 What the four runs exposed

Four findings from the platform runs are worth separating from the mechanism that produced them.

**A functional predictor's bias becomes a safety outcome.** The antibacterial run's seven selected constructs are the direct consequence of one predictor favouring a particular chemistry — cationic amphipathic peptides, overwhelmingly of amphibian origin in its training data — and the relationship between that chemistry and predicted toxicity. The bias was identified in the evidence review before the run; the run quantified its cost.

**An unavailable model must be reported, not silently substituted.** The anti-inflammatory run proceeded on a single available functional channel, and the record states plainly that the direction's output is a shortlist for wet-lab validation produced from one signal plus a de-confounding heuristic, not a set of leads.

**Percentile cuts, not thresholds, are what make a functional predictor usable.** Every direction's candidate pool is defined as the top ten percent of the library by that direction's score, never as the set above a fixed value. This is the single decision that most changes the behaviour of the platform-scale runs relative to stage one, and it follows directly from the evidence review's central finding that these predictors' reported accuracies do not transfer to a library of real short sequences.

**The library's own properties limit a direction from inside the model.** The anti-inflammatory model's training set effectively stops around twenty-five residues, so that direction's top-ranked candidates concentrate at twenty-one to twenty-five residues by constraint rather than by merit, and a stratified band covering twenty-six to thirty residues is empty. This is a property of the model, not of the biology, and it is recorded in the data.

### 5.4 The construct layer

The four runs populate one table of 496 rows, which is the layer the platform serves from. Its fields fall into four groups: identity and classification (construct identifier, functional direction, channel, status); assembly (three foreign keys pointing at a peptide, a scaffold and a linker); results (rank, an aggregate of nine scores in a structured field, and three booleans recording whether haemolysis, MHC class I and MHC class II were assessed); and one historical field the platform does not expose.

Every row belongs to either a selected or a control channel, and the control channel is not filler: it holds the lowest-scoring candidates from the same ranking and exists so that a later assay can confirm the scoring genuinely discriminates rather than sorting noise inside a narrow dynamic range. Control-channel constructs pass the same safety gates and receive the same scoring as selected ones, which is what makes their numbers comparable.

Scores are heterogeneous by direction, which is the table's second structural feature. The aggregate field holds 26 distinct keys and no row holds all of them. Six keys are shared across all four directions — toxicity, haemolysis, MHC class I immunogenicity, aggregation propensity, allergenicity and membrane crossing — and the remainder are direction-specific: the antioxidant direction uses its own activity predictor and two branch heads, the antibacterial direction an antibacterial model, the anti-inflammatory direction an anti-inflammatory channel plus control values from four other channels, and the anti-melanogenic direction a tyrosinase-inhibition model. A row carrying fewer scores is not an incomplete row; those scores do not apply to that direction. The structurally notable case is immunogenicity: the MHC class I key is present in all 496 rows but holds a value in only 117, for the reason given in section 8.

---

## 6. Stage four: the platform

### 6.1 What the platform is

The platform is a single-page web application organised as five surfaces, three of them working surfaces and two of them reference surfaces.

**Landing page.** Four key numbers, three feature cards, five application-route cards, three governing principles, an explanation of the screening rounds, and four direction status cards. The key numbers are derived from the service rather than written into the page — the search space is the measured maximum peptide count across directions, the construct total is the sum across directions, the scaffold count and direction count are the lengths of the respective lists — so the page cannot disagree with the data.

**Library browser.** The entry point to what has already been computed, with three tabs: functional peptides and constructs, scaffolds, and linkers. The construct tab offers filtering by functional direction and by the application route a candidate was screened under. Each row shows its rank, direction, status, peptide sequence and length, scaffold, linker, a safety verdict indicator, the composite score and the direction's functional score, with a marker where that score can only be read as a ranking.

**Builder.** The core surface, a five-step guided flow: select the application route; select one or more functional directions; confirm the scaffold; confirm the linker; receive the result. The result is a set of candidates sorted by composite score, each carrying the fusion sequence assembled from the chosen scaffold and linker and its fusion length, together with counts of how many candidates in the whole matched set cleared every gate, how many sit within ten percent of a boundary, and how many were vetoed.

**Result page.** Where a single candidate is read, in four tabs. The construct tab is the primary view: composite score, rank and aggregation propensity at the top; the safety gate panel below; then the sequence in three colour-coded segments — scaffold, linker, functional peptide — with any segment whose sequence is unavailable drawn as a marked placeholder rather than as residues; then a within-direction comparison and six generated blocks of prose. The peptide tab shows origin, length, all nine tool scores and locally computed sequence properties. The scaffold tab shows the current binding alongside the alternatives, and clicking an alternative re-renders the same candidate on that scaffold immediately. The linker tab shows the entry's unit composition and literature provenance. A conversational panel attached to the page answers questions against that construct's real scores.

**Scaffold detail page.** Expands a single scaffold across basic information, source and patent, patent sequence variants, admitting routes, experimental evidence, regulatory registration status, and the other scaffolds in the library. The page carries an explicit region listing fields the dataset genuinely lacks, so that a reader can distinguish a field that does not exist from a panel that has failed.

Two design decisions in the builder carry the platform's main product argument.

**The platform does not ask the user questions the user cannot answer.** A non-specialist cannot decide which of eight scaffold proteins is appropriate; a specialist does not want to be asked at every step. The platform therefore converts scaffold selection from a decision the user makes into a conclusion derived from the product form: the user states the product, the platform derives the scaffold. The linker is not that shape — the real difference between library entries is a single rigidity class, and the trade-off between a flexible and a rigid unit can be understood without protein-engineering training — so a single linker is exposed as a changeable option. Both choices change the sequence assembled from each candidate; neither changes the candidate set or any score, and the interface states this rather than allowing the user to believe the choice had a filtering effect.

**Delivery mode is derived from the route rather than selected by the user** — section 6.3 explains why.

### 6.2 The five application routes, and why barrier integrity orders them

The five routes are not five parallel labels. They are ordered by one physical quantity: how intact the barrier is at the interface the construct ultimately contacts. That quantity determines the likelihood that the immune system encounters the fusion protein, and therefore how tightly the immunogenicity threshold should be set.

| Route | Barrier state | Scaffold clusters admitted | Immunogenicity threshold |
|---|---|---|---|
| injectable filler | barrier bypassed; the only route that genuinely enters the body | 2 | 0.35 |
| wound dressing | barrier breached; direct contact with the wound bed and tissue fluid | 4 | 0.35 |
| mask patch | intact barrier under occlusion | 4 | 0.50 |
| topical film | intact barrier, no occlusion | 2 | 0.50 |
| hair care | non-living surface: the keratinised hair shaft has no vessels or immune cells | 2 | 0.60 |

The wound-dressing route taking the same strict threshold as injection is the point that needs stating explicitly: the wound barrier is already broken and the construct is in direct contact with tissue fluid, so its immune exposure is of the same order as injection, and treating it as intact skin underestimates the risk. Binding the threshold to the route rather than letting the user select it is what prevents a candidate being judged acceptable under a threshold its use case does not have.

The three modulated developability components are derived from the same physical picture. Topical film is applied at ambient temperature, so its thermal-stability requirement is lowest and its membrane-crossing and solubility requirements highest. Mask patch relies on occlusion to enhance permeation, so its crossing requirement is one tier lower while solubility stays high. Injectable filler and wound dressing enter or contact tissue directly, so membrane crossing is not required. Hair care is applied to the shaft, so crossing is lowest while solubility must be high to support shampoo and conditioner formulations. The tiers are 1.8 for high, 1.0 for medium and 0.4 for low.

Each route also carries a set of non-vetoing additional checks — sterility and endotoxin control for a wound dressing, injectability and rheological performance for a filler, occlusion irritation assessment for a mask patch, film-forming and spreading behaviour for a topical film, adherence and wash resistance for hair care. These are not in the data; they are the experiment list the route must still complete, and the interface presents them as guidance rather than as adjudication.

### 6.3 The data the platform serves

The data is three layers at three scales, and mixing them up destroys the meaning of any statement about it.

**The peptide layer.** 20,248,885 short peptide sequences and the scores a dozen predictive tools assigned to each. The score table measures about 367,717,240 rows and 130 GB, the largest in the database. Twelve tools cover the library at 100% — toxicity, haemolysis, allergenicity, the three antioxidant heads, antibacterial activity, membrane crossing, solubility, thermal stability, anti-melanogenic activity and the MHC class I immunogenicity predictor — with two caveats that belong with the number: the immunogenicity figure reports 100% because its denominator counts only the 134,888 peptides inside its applicable length range, and the haemolysis figure rests on a 500,000-peptide sample. A second immunogenicity pathway is stored separately, organised by peptide and allele, at an estimated 147.5 million rows and 35 GB across 131 alleles; it retains each peptide's binding rank and grade on each allele, which would support finer analysis than a single score, and the platform does not use that granularity.

**The construct layer.** The 496 assembled constructs described in section 5.4.

**The reference layer.** Small but the most "hard" content in the system: eight scaffold protein clusters with sixteen patent sequence variants all carrying real amino-acid sequences, and fifteen curated linker entries with literature provenance. Both were compiled by hand from real patent records and design literature rather than produced by a predictor.

The eight scaffold clusters divide into three categories. **Recombinant collagen**, five clusters — a humanised type III collagen and its tandem-repeat variant, a type XVII collagen fragment, and a human-like collagen. Collagen is the principal extracellular matrix component of the dermal layer, and this category carries most of the library's high-grade evidence: four of its five clusters reach the highest tier, because they correspond to registered medical-device products including an injectable filler, a repair dressing and a lyophilised-fibre product. **Silk fibroin**, one cluster, whose representative sequence is only 62 residues and is therefore a heavily truncated engineered fragment rather than a complete silk heavy chain. **Spider silk**, two clusters, one at human-use evidence and one whose verifiable evidence stops at cell-free and ex vivo work.

The evidence grading is itself part of the data and is easy to read backwards. **E1** is purified protein, physicochemical or cell-free work; **E2** is cell work; **E3** is animal work; **E4** is human use or a controlled clinical study; **E5** is regulatory review, a controlled clinical study and post-market safety data. A label of E5 means there is regulatory review or post-market safety data supporting that protein's safety in **some** use; it does not mean the new use the platform proposes has been validated. Conversely a label of E1 does not mean the protein is worthless; it means the publicly verifiable evidence stops at the cell-free tier. Each record carries an evidence-limitation field precisely to record that gap.

The hair-care route is where this reading matters most. It appears to be backed by two well-established applicants, and taken apart it is not: the highest evidence attached to one of its scaffolds comes from that applicant's wound-dressing product and has nothing to do with hair, and the other reaches only the cell-free tier. Each of the other four routes has at least human or regulatory evidence corresponding to its own indication; this one has none. The platform's handling is to keep the route and write the fact into the data as an explanatory string, rather than deleting the entrance or letting it appear as mature as the other four.

The route structure itself is taken from the dataset rather than invented. The five routes correspond to five application-tag columns in the scaffold source table, and they are used directly because three conditions hold simultaneously: every route admits at least one scaffold, every scaffold is reachable from at least one route, and no two routes admit exactly the same group. The measured result is that the five routes admit two, four, two, four and two clusters respectively, and that all eight clusters are reachable. An earlier self-designed scenario hierarchy was abandoned precisely because its subcategories admitted identical scaffold groups, so the user could not perceive having filtered anything.

Two data facts belong here because they affect how the platform reads.

**Every stored construct's scaffold binding is a placeholder.** All 496 rows point at the same placeholder record, whose sequence is a marker string of length zero, so no real scaffold can be read from a construct and no complete fusion sequence can be assembled from it. A binding strategy has been designed and implemented: because team material covers the scaffold side completely and says nothing about which peptide belongs to which scaffold, the only key that can join the two sides is the application route, and the rule is to take the route's admitted scaffold with the highest evidence level, breaking ties by fewer admitting routes and then by name for reproducibility. The result is that three directions land on one recombinant collagen cluster and the fourth on another. Those bindings are the platform's per-route default and not a pipeline output — no record shows the pipeline ever made that pairing — and the service distinguishes the two cases, reporting a binding recorded on the construct as verified and one specified in a request as inferred.

**The two immunogenicity pathways have not been merged, and the gap is large.** MHC class I has a value on 117 constructs, MHC class II on 186, at least one of the two on 298, and both are empty on 198. For those 198 constructs the immunogenicity gate is in the not-assessed state, and the platform reports that as an indeterminate verdict rather than a clear one.

### 6.4 How the platform is built

**Stack.** Vite, React 19, TypeScript and Tailwind on the frontend; FastAPI, Pydantic and a PostgreSQL driver on the backend; PostgreSQL 16.15 as the database. The frontend's TypeScript types deliberately mirror the backend's field names exactly, so that the schema and the types can be compared mechanically with no naming-conversion layer in which a rename could hide.

**Four layers with hard constraints between them.** Routes validate parameters, call the service layer and serialise the response, with no SQL and no computation. Services carry every threshold, weight and business judgement, and write no SQL. Repositories perform queries and row conversion only, with no threshold and no convention. Models define the response contract. The single purpose of these constraints is that **every threshold exists in exactly one place**. An audit recorded three defect classes caused by a copied value drifting: the same safety threshold table written twice under a comment claiming the two shared a definition; the immunogenicity threshold hard-coded globally at 0.50 while the route definitions specified three tiers, with the result that a construct sitting exactly on the tightened threshold was displayed as clearing every gate; and generated prose citing an acceptance floor that existed in no tool metadata. With thresholds centralised in the service layer those classes are structurally impossible rather than merely fixed.

**Reference data is the backend's single source of truth.** The five routes' definitions, the nine indicators' tool metadata, the pipeline's retained and excluded rounds, and the four directions' display information all live in one module. Everything in it is read by the frontend as data, and the frontend keeps no copy of any of it.

**The interface** is 19 read-only endpoints in five resource groups — reference data including a health check, constructs, a build endpoint, scaffolds and linkers — plus one write endpoint for dialogue. List endpoints uniformly return an item array plus a total, so the frontend can display a total without a second counting request.

Four contract decisions are worth singling out.

**A missing value must carry a marker.** Every nullable score is accompanied by an assessment flag, which removes any possibility of a caller reading a not-assessed item as a zero.

**The composite travels with its route and is reproducible.** A single construct's response carries, per route, every normalised component value, the weight each component received, the multiplier it received and the pool size the normalisation was computed over — enough to recompute the composite by hand from one response.

**The safety conclusion is a structure rather than a sentence.** It is an object containing the route's immunogenicity threshold, an overall verdict, per-gate detail, the keys of unassessed gates, and the keys of vetoed gates. Each gate's detail carries its measured value, threshold, threshold provenance, pass or fail, whether it is borderline, whether it is a veto gate, and which side counts as exceeding — the last field being necessary because MHC class II is the one gate where lower is worse.

**Generated text carries its sources.** The analysis prose is produced in six fixed blocks, each accompanied by a list of the response field paths it cites, and the whole response carries a marker stating whether the text is template-generated or model-generated. The generation capability is abstracted as a protocol rather than a function, so connecting a language model later means adding an implementation and switching the registration, with the routes and the response models unchanged.

**Deployment.** The platform is live at a Cloudflare Pages address, deployed in a three-step chain: export the data from the real database, build the frontend, and upload the built output. The form changed fundamentally during the rollout and the reason is worth recording. Previously a service had to run continuously and connect to a database on a school workstation, so every interface call crossed the network to that machine; that dependency became unavailable, because the machine is not under the project's control. The goal was therefore to make the project run with **no backend process and no database access**, moving everything the service previously computed at runtime into a one-off export step, with only the conversational feature handled by an edge function — it cannot be pre-generated because it must handle free-form questions, and the model's key exists only in that function's environment variables and never reaches the browser.

The export's output is not the database's tables converted raw into JSON; it is **a call to the backend's own interface functions, storing whatever they return**. The reason is the one given above: every threshold and adjudication is concentrated in one place, and an export script that bypassed the service layer and assembled output with its own SQL would be a fresh copy of the defect class the audit had just eliminated, and would ship silently. Every byte of the export is therefore the service's own output.

The static layer that reads those files duplicating no threshold, weight or adjudication in the browser is a hard constraint, not a preference. It does two things: take one page from an already-sorted list, and concatenate three already-exported amino-acid sequences. Because the composite varies with the route and the safety verdict varies with the route's immunogenicity threshold, both are computed once per route during export and stored rather than recomputed in the browser.

**Verification** runs in three layers, and a failure in each means something different: a data-layer failure means the mapping is broken, an interface-layer failure means the contract has drifted, and an interface-presentation failure means the rendering and the data disagree. The backend suite stands at 115 tests, of which 113 pass and 2 are skipped because the fixture data happens not to satisfy the tested condition. The static data layer's walkthrough runs with no backend at all, serves the export directory over HTTP and reads it with the frontend's own data layer, and stands at 91 assertions, including one that compares the sequence the interface assembles with the service's sample residue by residue and another that fails if any read reaches the network. Two browser-free walkthroughs render the real application in a DOM emulation and walk the builder through its five steps with real clicks against a genuinely running service, at 33 and 25 assertions. None of the three can answer questions about layout, because the DOM emulation has no layout engine.

### 6.5 The methodological commitments the platform carries

The platform's governing principles are not new. Three of them are the rules established in version 1.4, applied to a different substrate, and it is worth stating the continuity explicitly because it is the project's main methodological claim.

**Safety is a veto, never a weighted term.** A candidate exceeding any gate is eliminated and does not participate in compensation of any kind. The consequence is visible in the runs: 47% of the best peptides by the antibacterial predictor were removed by the gates, and the direction's selected channel fell to seven constructs. A weighted design would have kept them and ranked them near the top.

**Each metric is used exactly once.** The functional score appears only in the functional ranking and is never referenced again. This targets a specific and plausible failure mode: if the functional score kept participating in later weighting it would mask scaffold and route suitability, and the pipeline would select the peptide with the highest functional score rather than the peptide that performs best against the current scaffold and route. Those are not the same thing, and the platform needs the latter.

**Weights come from the data.** The composite is formed from six developability components — membrane crossing, solubility, thermal stability, allergenicity inverted, B-cell epitope propensity inverted and aggregation propensity inverted. Each is normalised within the candidate pool and oriented so that larger is better, and each component's weight is its winsorised standard deviation, normalised so the weights sum to one. A component with genuine discriminating power in a given pool is automatically up-weighted; one with almost none is driven toward zero. This is why the four directions have different weights: they are computed, not configured. The first three components are modulated by the route's weight tier; the latter three participate at 1.0, preserving the contribution the data gives them without introducing a route difference. When a component has no measurement it drops out of the sum and the remaining weights are renormalised, so the denominator does not distort because of a missing measurement.

**None of the six components is a functional activity score**, and that is deliberate — it is the same exclusion that made stage one's final ranking structural only.

Three further conventions are the platform's own and answer misreadings that are easy to make.

**Not assessed is not zero.** All nine scores are nullable at the data layer, and an empty value means no measurement exists, which is a different thing from a measured zero. The weight of this convention is visible in the numbers: alongside 379 empty MHC class I values there are 135 genuine zeros, of which 116 are immunogenicity measured at zero. Rendering the empty values as zeros would put more than a hundred candidates on screen described as immunogenic at zero and therefore completely safe, when none has been measured. The safety panel accordingly rolls up into four possible verdicts, not three — everything clear, at least one item exceeded, nothing exceeded but at least one item inside the ten-percent boundary zone, and nothing assessed so the verdict cannot be reached. The fourth exists specifically so that "not measured" is never rendered as "passed".

**A ranking-only score is not dressed as a probability.** The anti-inflammatory and anti-melanogenic functional scores come from models that discriminate whether a peptide looks like a known functional peptide, not from measurements of anti-inflammatory or anti-melanogenic activity. The data marks those rows as usable for ordering only, and the platform shows a ranking marker on list rows and in the score grid, applies no probability colouring, and issues no pass or fail badge. Without the marker on list rows, a ranking position would be displayed as a confidence.

**A very small non-zero value must not be rounded to zero.** The library holds several hundred values that are extremely small but genuinely non-zero, concentrated in the membrane-crossing and solubility columns, and rendering them at two decimal places turns all of them into `0.00`. Score formatting therefore falls back to significant figures when the value is small.

### 6.6 Two improvements the platform made to what the pipeline produced

Two corrections are worth separating from the platform's general work, because both changed what a stored number means rather than how it is displayed.

**The pipeline's delivery multipliers never took effect.** The pipeline defined three multipliers over membrane crossing, solubility and thermal stability, but computed them by looking up a weight dictionary whose keys did not include the multiplier names. The solubility and thermal-stability multipliers therefore never applied, only membrane crossing received one, and the composite scores under the four delivery methods came out nearly identical. The platform keeps the design intent and applies all three multipliers from the route's weight tier, placing the other three components at 1.0. Its composite is therefore not on the same axis as the library's stored delivery scores, and those stored values are retained for inspection and not published.

**The two delivery axes are not convertible.** The stored scores are divided by four physical methods, while the platform's five routes are divided by contact interface and barrier integrity. The two axes are independent and no invertible mapping exists between them, so the platform recomputes the composite entirely under the route convention rather than attempting a translation.

---

## 7. Results

### 7.1 What the project produced

| Asset | Stage | Scale | Notes |
|---|---|---|---|
| Peptide library | three | 20,248,885 sequences | 1 to 30 residues; 94.6% from one metagenomic source |
| Per-tool score table | three | 367,717,240 rows, ~130 GB | twelve tools at nominal 100% coverage |
| Second immunogenicity pathway | three | ~147.5 million rows, ~35 GB | 131 alleles; per-allele rank and grade retained |
| Assembled constructs | three | 496 | 290 selected + 206 control, across four directions |
| Scaffold reference library | three | 8 clusters, 16 patent sequences | all with real amino-acid sequences; E1–E5 evidence grading |
| Linker reference library | three | 15 curated entries | sequence, rigidity class, unit composition, literature provenance |
| Indicator set | four | 9 scores per construct | 3 veto gates, 2 non-vetoing soft signals, 4 developability components |
| Application routes | four | 5 | ordered by barrier integrity; three weight tiers and three immunogenicity tiers |
| Programmatic interface | four | 19 read-only endpoints + 1 write | five resource groups |
| Deployment | four | live | static export plus one edge function |
| Verification | four | 115 backend tests, 91 static assertions, 58 walkthrough assertions | three independent layers |

Stage one's assets belong to the same list and are lighter: a candidate pool of 19,890,021 sequences, 250 assembled constructs in a Top and Bottom channel, 253 predicted structures, and per-round score tables with full provenance per round per candidate. They are not carried into the platform's database; they are the record of the pipeline that established the architecture.

### 7.2 The numbers that define the project

| Quantity | Value | Stage |
|---|---|---|
| Sequences scanned to build the candidate pool | 849,416,450 | one |
| Candidate pool after preprocessing | 19,890,021 | one |
| Metagenomic share of the pool | 96.3% | one |
| Constructs produced by the first complete pipeline | 250 in 250 from 19,890,021, 99.9987% rejected | one |
| Peptide library at platform scale | 20,248,885 | three |
| Per-direction candidate pool | 2,024,889 | three |
| Constructs across four directions | 496 | three |
| Overall rejection rate, library to construct | approximately 99.9975% | three |
| Tools that can eliminate a candidate | 3 | two |
| Tools that can rank functionally | 2, plus 1 weak | two |
| Directions with signed-off output | 2 of 4 | three |
| Constructs with no immunogenicity measurement at all | 198 of 496 | three |

The last four lines of that table are the project's own summary of itself. The screening space is large; the number of things that can legitimately eliminate a candidate within it is small; and the resulting shortlists are ranked candidates for wet-lab validation rather than sets of leads.

---

## 8. What the project does not establish

The following are properties of the work stated with their measurements, not reservations about it. Each is material to how the project's output should be described.

**Nothing in the output is evidence of activity.** Every functional quantity in both stages is a prediction from a model trained on other data. A high composite score means a construct looks developable under models with known biases; it does not mean the peptide scavenges free radicals, kills bacteria, suppresses inflammation or inhibits tyrosinase. The wet-lab work that would test the pipeline's central hypothesis has not been performed, and until it is, the output is a ranked candidate list.

**The immunogenicity check did not operate on the final products of stage one.** The tool accepts peptides of five to fifteen residues. Among the 250 final functional peptides of version 1.4, exactly one is eight residues and every other is at least eighteen. The service returns a score of zero for out-of-range input and labels it as an invalid length, and the acceptance condition is a score below the threshold, so all such inputs pass silently and nothing is eliminated on this basis. Of the four stage-one checks, three genuinely execute on the final products. The accurate formulation is that the final constructs **did not trigger** a toxicity, haemolysis or allergenicity veto — not that they passed four checks.

**A safety check whose service is unavailable is treated as passing.** The elimination condition is that the metric has a score and the score exceeds the threshold, so an empty score yields a pass. Over a nineteen-million-candidate run this permissive policy is what allows the pipeline to finish at all, and its cost is that an individual unchecked candidate can advance. The accurate external formulation is that **candidates triggering no safety veto were retained**, not that every candidate passed every check.

**The safety case differs by direction, because gate coverage differs by direction.** For the four platform runs, the class II pathway was absent from the first and present in the others, and the B-cell epitope predictor had no rows when the antioxidant direction ran. In the platform's construct set, 198 of 496 constructs have no immunogenicity measurement from either pathway at all. A gate that was not evaluated eliminates nothing — that is the explicit rule — so a construct can be reported as clearing every gate it was measured on while a gate that could have excluded it never ran. The interface reports this as an indeterminate verdict rather than a clear one, which is the correct handling, and the underlying fact is that the safety case for the long-peptide majority rests on toxicity, haemolysis and developability alone.

**Structural confidence is low throughout, and this is intrinsic to the material.** The mean is 0.42 and the maximum 0.50, on a scale where 0.50 marks the edge of meaningful confidence, and the independent second model returns 0.52. The score is properly described as a consistent way to rank imperfectly modelled structures rather than as a precise physical measurement.

**One entry near the top of stage one's table is not a functional peptide.** The 25-residue sequence carried by the two highest-ranked Top-channel constructs is a purification and cloning handle rather than a bioactive antioxidant peptide, and it reached that position because structural ranking never examines what a peptide does. Any document quoting that table carries an obligation to flag the entry.

**The composite score is a ranking value with no absolute meaning.** Its weights differ between directions and between runs over time. It is reproducible, since the response carries everything needed to recompute it, but two composite scores from different directions are not comparable quantities.

**Two predictors cannot serve as hard gates on this material and one is missing where it was expected.** The allergenicity predictor's third-party specificity is low and it labels roughly a third of a twenty-million-peptide library as allergenic, which is why it is reported and never used as a gate. The B-cell epitope predictor overflows badly on short sequences, calling most of the library an epitope, so its continuous score is used for relative ranking and its absolute value is not trusted. The locally rebuilt anti-melanogenic model is absent from the production database, so that direction falls back to a predictor with no enrichment power on this library. The antioxidant direction's supporting predictor has a distribution squeezed into too narrow a band to rank on, and its primary predictor's own threshold is not usable at all.

**The peptide library's declared length range in product prose differs from the library's own.** The library's measured lower bound is one residue and it contains two-residue constructs, while long-standing prose uses three to thirty. The discrepancy does not affect function, but external description should use the library's actual range. Separately, haemolysis prediction covers only a 500,000-peptide sample at library level, which is why it reads as 100% coverage on the 496 constructs but would be a limitation if the gate were extended to a larger candidate set.

**Three fields in the dataset do not carry what their names imply.** The field named as a full fusion sequence holds, in all 496 rows, a pipe-delimited concatenation of a placeholder scaffold name, a linker and a peptide — not one row holds a real amino-acid sequence. The field named for antioxidant activity holds the functional score of whichever direction the row belongs to, filled by four different tools across the four directions. And the linker foreign key on all 496 constructs points at the first row of the sample table, so no linker selection difference is visible from the construct table alone.

**The project has not undergone formal ethics review.** All input is protein sequence from public databases and patent records, with no patient data, no human-subject data and no personal information, so informed-consent and data-privacy procedures do not arise. That is a factual statement and not a claim of approval, and external material should not imply that a review has taken place.

---

## 9. Open questions

Each of these is a question the project has identified and not settled. They are the honest remainder of work, and they are grouped by what they block.

**Experimental.** The pipeline's central hypothesis — that the two channels differ in wet-lab behaviour — is stated but untested. The relationship between the composite score and assay results is likewise untested. Until at least one round of assays exists, the pipeline's output is a ranking and nothing more.

**Data.** Whether the construct-to-scaffold binding should be written into the production database, and when, is undecided; the platform currently carries a per-route default that is labelled as inferred rather than verified. Whether the two immunogenicity pathways should be merged, and at what granularity, is undecided. Whether the candidate pool's 96.3% metagenomic imbalance should be corrected toward annotated sources, at what cost to pool size, is undecided. Eleven scaffold patent records disclose no sequence and cannot participate in assembly. Each scaffold's material form is an extracted value rather than a source field and still requires per-item confirmation, with two entries needing the closest review because their source wording admits more than one form.

**Model.** The anti-inflammatory direction is blocked on a benchmark rather than on a model: a usable training set needs negative examples that contain both functional peptides confirmed not to be anti-inflammatory and random fragments, after which the representation already shown to perform at a usable level on independently collected data can be retrained. The anti-melanogenic ranking model requires wet-lab labels for probability calibration before it can be used for anything but ordering. Every threshold in the system that is not the tool's own requires calibration against a small validation set with known labels; only the toxicity threshold has had that treatment.

**Convention.** The linker library has no route dimension, so the builder offers the same list under all five routes, whereas the scaffold library has had one from the start; filling the gap requires judging each of the fifteen entries by purpose, which is a team task rather than an inference. The reported count of tools covered by the library has widened during the project, and the different counts in circulation — one for the pre-computation, one for the score contract, one for a view — need to be aligned to a stated convention before any of them is quoted.

**Scale.** The platform's deployed data is a snapshot and does not update itself, so the question of whether the data is current is answered by when it was last exported rather than by the system guaranteeing it. Re-running predictions is outside the deployed system's capability: the scores are dead data computed offline and stored. The conversational endpoint currently has no authentication and no rate limiting, which should be configured at the platform rather than relied on at the application layer. And the tooling that uploads the built output has an authorisation that expires, which is an operational interruption rather than a design question but costs time whenever it occurs.

---

## 10. Reference

### 10.1 The version and directory map

| Version | Pipeline directory | Output directory | Repository |
|---|---|---|---|
| 1.1 | `main/stages/` | archived | `iGEM-silk` |
| 1.2 | `main/stages2/` | `output2/` | `iGEM-silk` |
| 1.3 | `main/stages3/` | `output3/` | `iGEM-silk` |
| 1.4 | `main/stages4/` | `output4/` | `iGEM-silk` |
| platform runs | `iGEM-platform-main/scripts/pipeline/` | `iGEM-platform-main/results/pipeline/` | `iGEM-website` |

### 10.2 Thresholds, across both stages

| Item | Tool | Stage one | Platform scale | Direction | Type |
|---|---|---|---|---|---|
| Toxicity | ToxinPred3 | 0.38 | 0.38 | lower is better | hard veto |
| Haemolysis | HemoPI2 | 0.55 | 0.55 | lower is better | hard veto |
| Allergenicity | AlgPred2 | 0.30 | 0.30 | lower is better | stage one: veto; platform: reported only |
| Immunogenicity, class I | MHCflurry | 0.50 | 0.50, tightened to 0.35 under two routes | lower is better | hard veto |
| Immunogenicity, class II | NetMHCIIpan | not used | strong-binder sub-boundary at the 2nd percentile | **higher is better** | platform: soft signal |
| B-cell epitope | BepiPred-3.0 | 0.1512 | 0.1512 | lower is better | reported only |
| Membrane crossing | pLM4CPPs | 0.15 | component of the composite | higher is better | ranking feature |

The one apparent discrepancy in this table is deliberate rather than an inconsistency: the platform treats allergenicity as a reported signal rather than a gate, because its third-party specificity does not support eliminating candidates on it. The difference is a change of role, not of threshold, and both facts should be quoted together.

### 10.3 Glossary

| Term | Definition |
|---|---|
| **Construct** | One assembled molecule: scaffold, linker, functional peptide and purification tag. Distinct from a peptide, which is only the functional segment. |
| **Peptide library** | The 20,248,885 short sequences and their pre-computed tool scores. The raw material; users never see it directly. |
| **Candidate pool** | The top ten percent of the library by one direction's functional score, 2,024,889 sequences. |
| **Channel** | One of two parallel arms of a run. The selected channel holds the highest-scoring candidates; the control channel holds the lowest and serves as a matched negative control. |
| **Veto gate** | A criterion that eliminates a candidate outright and contributes nothing to any later calculation. |
| **Soft signal** | A criterion that is measured and reported but cannot eliminate a candidate. |
| **Composite score** | A derived ordering value, formed by weighting developability components whose weights are computed from the pool's spread. Contains no functional term. |
| **Winsorised standard deviation** | The standard deviation computed after truncating extreme values to the 5th and 95th percentiles, used as the weighting basis so that one outlier cannot dominate a component's weight. |
| **Application route** | One of five product forms, ordered by the integrity of the barrier the construct contacts, which determines the immunogenicity threshold and the developability weight tier. |
| **Barrier integrity** | How intact the skin or tissue barrier is at the interface the construct ultimately contacts; the physical quantity that orders the five routes. |
| **Evidence level (E1–E5)** | E1 purified protein or cell-free work; E2 cell work; E3 animal work; E4 human use or a controlled clinical study; E5 regulatory review, a controlled clinical study and post-market safety data. Read as the highest tier that can be verified, not as a completion score. |
| **pLDDT** | Per-residue confidence reported by a structure predictor, 0 to 1. The construct-level value is the mean over the chain. |
| **SASA** | Solvent-accessible surface area, computed as the mean relative accessibility of the functional peptide region only. Higher is better. |
| **Ranking-only score** | A score usable for ordering but not readable as a probability, because the model behind it discriminates whether a sequence resembles a known functional peptide rather than whether it has the activity. |
| **The three tool counts** | The number of predictive tools quoted differently by different parts of the project: the pre-computation ran a set of tools over the library; the score contract covers nine indicators; and a reporting view covers a wider set. The counts are not interchangeable and the convention should be stated with the number. |

### 10.4 Where each subject is treated in full

| Subject | Document |
|---|---|
| Version 1.1 – 1.4 in detail, the microservice layer, pipeline engineering principles, the engineering failure record | `PeptiCraft-1.x-Master-Reference.md` |
| The platform's product design, data semantics, architecture, deployment record, verification, open decisions | `PeptiCraft-2.0-Master-Reference.md` |
| The per-direction platform runs and their tool-coverage notes | `iGEM-platform-main/results/pipeline/*/OVERVIEW.md` |
| The evidence review and the four-stage architecture | `iGEM-platform-main/docs/proposal/` |
| Per-tool provenance, training data, reproduction record and applicable range | `wiki/` |

---

*This document covers the PeptiCraft project as a whole: the screening pipeline of PeptiCraft 1.1 – 1.4, the evidence review that redirected the project, the four platform-scale pipeline runs and the PeptiCraft 2.0 platform built on their output. It is the umbrella reference above the two version-level master reference documents named in the table above.*

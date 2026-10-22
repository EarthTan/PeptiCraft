# Engineering Success — Five Design–Build–Test–Learn Cycles

**The standard applied.** No decision was accepted because it had been written down. Each was built, examined against the project's own stored results, and changed where the examination disagreed.

**Where the Test leg sits.** Each Test below is an examination of the project's own data or running software, not an assay. That is a stated position rather than a limitation to be excused: it is the test available without a wet-lab, and it is where the largest defects were found. Several were invisible in a successful run — nothing failed, and the composition was wrong.

---

## Cycle 1 — The dataset survey, and why the project stopped training models

**Design.** Train a neural network to predict peptide activity from public labelled data, in the three-to-thirty-residue window.

**Build.** Labelled sets were assembled from sources with published support: antioxidant first, about 1,800 sequences, then every annotated peptide that could be collected, about 1.08 million.

**Test.** A survey of what the label supply could support. For properties with enough labelled data — antioxidant above all — many published predictors already exist, so a further model adds nothing. For the properties the project wanted next, including anti-melanogenic activity and several cosmetic functions considered at the time, there is effectively no labelled data at all, so no model is trainable. The two failures are the same failure seen from opposite sides.

**Learn.** The binding constraint is labelled data, not model capacity. The project stopped training and became an orchestrator instead: eighteen published scoring tools behind one funnel. A direct consequence shaped the whole architecture — with throughputs differing by two orders of magnitude between tools, the funnel became a cost schedule, cheapest and broadest first, most expensive last on the smallest set.

---

## Cycle 2 — One audit, two design errors

**Design.** Every attribute entered a single weighted total, with hand-assigned coefficients, and both a selected and a control channel were carried so that a wet-lab comparison would be possible.

**Build.** An eight-round funnel: 1,081,772 sequences to 150 assembled constructs in 6.5 hours, both arms processed identically.

**Test.** The stored results read as arithmetic, which produced two findings rather than one. First, the safety coefficients — toxicity 0.13, haemolysis 0.09, immunogenicity 0.05 — were smaller than the activity weight they were supposed to override, so a peptide with a severe predicted haemolysis signal and a strong antioxidant score still finished near the top. Second, the composite used for ranking in the later rounds still contained the functional term, at the largest coefficient in the table, so the control arm was being ordered partly by the property that defined it as the control. Neither finding came from a failure. The run completed and its output was coherent.

**Learn.** Two structural rules replaced two coefficients. Safety is a threshold: pass or eliminate, no participation in any average. And each metric is used exactly once — the functional score appears only in the channel split, and the final score contains no functional term of any kind.

**Carried forward, and measured.** The safety rule was confirmed on the antibacterial direction, where 47% of the 250 highest-scoring peptides were eliminated by the gates and the selected set fell to seven; a weighted design would have kept them and ranked them highly. The independence rule was confirmed too, in a result that looks like a mistake: the eight highest-scoring constructs in the entire run all come from the control arm. Structural quality and predicted activity are uncorrelated in this pool, which is exactly what two genuinely independent arms should reveal. It changed the wet-lab instruction to draw candidates from both arms.

---

## Cycle 3 — A tool with no spread is noise, not evidence

**Design.** Each scoring tool entered the composite with a fixed weight of its own.

**Build.** All tool scores computed once over the candidate pool and combined by a configured weighting table.

**Test.** Several tools returned values pinned into a narrow band across the whole pool. They carried almost no discriminating power, and their confidence on this class of sequence is low by their own reporting — but at a fixed weight they injected noise into every decision they touched, diluting the tools that could actually separate candidates. The defect is not that such a tool is wrong; it is that a constant is indistinguishable from a signal once it is given a coefficient.

**Learn.** Weights are computed from the data rather than configured: normalise each component within the pool, orient so that larger is better, weight by the winsorised standard deviation, renormalise to one. A flat component then has a weight near zero by construction, and a component with real spread is up-weighted automatically.

**Carried forward, and measured.** The mechanism corrected itself later without anyone intervening. In the antioxidant run the B-cell epitope table was empty, and the computed weight for that component came out at exactly 0.00 — against 0.31 for membrane crossing, 0.30 for allergenicity and 0.39 for aggregation — so the term simply vanished from the composite. A configured weight would have spent a fifth of the score on a measurement that did not exist.

---

## Cycle 4 — The labelled sets were the ceiling

**Design.** Keep enlarging the curated labelled data: 1,800 sequences, then 1.08 million, then about two million.

**Test.** The label supply does not scale the way the question does. After three rounds of enlargement the pool stood two orders of magnitude below the space it was supposed to represent, and every additional round of curation returned less than the last.

**Learn.** Labels are needed to **rank**, not to establish truth. The requirement was dropped and the sequence universe screened instead: 849,416,450 sequences from a reference proteome and a metagenomic protein catalogue, filtered to the three-to-thirty-residue window and the twenty standard residues, leaving 19,890,021 candidates. Safety and developability carry the constraint; activity only sorts.

**Carried forward, and measured.** The result is a pool in which 96.3% of candidates are unannotated metagenomic fragments — a real cost, accepted deliberately, because a sequence that has never been studied can still be synthesised, expressed and tested, whereas a label that does not exist cannot be invented.

---

## Cycle 5 — Re-read the tools instead of trusting them

**Design.** Adopt each tool at its published threshold and its reported accuracy.

**Build.** Every tool was reproduced from its authors' code and model, its architecture and decision logic studied, and several were retrained on better data in an attempt to improve them.

**Test.** Two results, one negative and one decisive. Retraining produced only marginal gains, and the same defects reproduced under a different representation — which locates the problem in the benchmark rather than in the model. Then, on the real library, the reported accuracies failed to transfer: one functional predictor's published 0.5 boundary labelled 72.83% of sequences positive, another labelled 99.5%. A boundary that admits three-quarters or almost all of a library is not a gate.

**Learn.** Stop treating a published threshold as portable. The tools were reclassified by what each can actually support — three can eliminate a candidate, two can rank, one ranks weakly, the rest only inform — and functional selection moved from a probability threshold to an in-pool percentile cut.

**Carried forward.** The negative result is the most useful thing this cycle produced. A better model does not fix a broken benchmark, and that conclusion is why two of the four functional directions are shipped as pending signatures rather than as results.

---

## What the five have in common

In each, the fix was to **move a decision**, not to tune a number: safety out of the average, the functional score out of the ranking, the weight out of a configuration table and into the pool's own spread, the label out of the requirement, the threshold out of the tool's paper and into the population being screened.

## The four rules that came out, stated so another project can use them

1. **A precondition cannot be a term in an average.** Anything that makes a candidate unusable must be a threshold, because a coefficient small enough to be a fair weight is also small enough to be outvoted.
2. **A component that cannot separate candidates must not be given a fixed weight.** A constant given a coefficient becomes noise in every decision downstream of it.
3. **A published threshold is not a portable threshold.** It was calibrated against its authors' population. A different population needs its own percentile cut or its own calibration, and this is checkable before any biology is discussed.
4. **Data availability, not model capacity, sets the ceiling.** Where labelled data is scarce the correct response is to change the question, not to train harder — and where the supply is already saturated with existing tools, a new model is duplication rather than contribution.

These four cost five iterations to find. Each was found by examining the project's own stored results rather than by a failure, and none of them is specific to peptides.

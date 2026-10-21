# PeptiCraft — Our Story

*A recollection in English, kept for its author's own reading rather than as submission material; it explains no significance and is not written for judges.*

---

## 1. At first there was only one thought

The thought at the beginning was simple: however useful a peptide is, it is not a product.

A short peptide of ten to thirty amino acids can do almost nothing in a real environment — it has no structural stability, proteases soon cut it to pieces, it cannot form a film, be spun, or gel, and once applied it does not stay in place. Its activity is real, but its physical form is empty.

So the thought arose: attach it to a structural protein. The structural protein is responsible for becoming the material — forming films, forming fibres, forming gels, carrying strength — and the peptide, riding on it, is carried along. The two segments are joined by genetic fusion, and the product is one recombinant polypeptide that can be expressed, purified, and processed as a single molecule, rather than the two-object relationship of "putting a peptide into a carrier".

The target scenarios were restricted from the start to topical and non-systemic use: skincare products, dressings and the like, with the activity carried by the silk-based material and kept in place. That restriction never changed, and it grew more important as the work went on — because it turned "whether the immune system will encounter this protein" into something bound to the product form rather than to the sequence alone.

Silk fibroin was chosen as the scaffold. Four reasons were recorded: its mechanical behaviour comes from repeat patterns in the sequence rather than from some fragile fold, so the sequence can be changed substantially while the material properties remain; it is biocompatible and degrades through normal proteases; recombinant expression precedents already exist in E. coli, so the wet-lab half is not wishful thinking; and under mild conditions it self-assembles into films and fibres, so a liquid formulation can turn directly into a coating without chemical crosslinking.

There was one more thing that was not written down at the time but that kept acting on the work later: short peptides in nature and in metagenomes are vast in number, and the great majority are toxic, hemolytic, sensitizing, or immunogenic. That is, the very act of intuitively picking "the most active" is dangerous — it selects a batch of things that rank very high and cannot be used at all. This problem later became the main line of the whole project.

---

## 2. The material at hand

When work began, only a little was actually at hand.

Four functional peptide tables. One was a manually curated multi-label master table of more than twenty-four thousand entries, labelled antimicrobial, antioxidant, anti-glycation, pro-collagen, and cell-penetrating, and carrying source species, source protein, and journal; of these, just over sixteen hundred were actually labelled antioxidant. The other two were exports from the same curated library (Peptipedia), one of 1.05 million entries and one of just over 1,100, all antioxidant, which underneath are an aggregation of the peptideatlas, Biopep, and plantpepdb libraries. There was also a table of just over four hundred entries, a homologous reference subset kept specifically for evaluation.

Looking back later, the input to the first step was in fact drawn from the first and third tables: the antioxidant batch merged with the third table, which after deduplication left 1,864 entries, and then the odd strings that were not amino acids but SMILES-style annotations were removed — they had got in because some entries in the source library record something other than a sequence — leaving **1,843 entries**. That number is the starting point of everything.

Two sequences. One silk fibroin, FibLNT8-10xRep-FibHCT, a synthetic version of 372 amino acids, with a Bombyx mori fibroin domain at the N-terminus, ten glycine-rich repeats in the middle, and a histidine tag native to the C-terminus (this native tag was later removed during assembly, because every construct still needs another one added at its end, and the duplication serves no purpose). Ten linker designs, starting from the shortest, GGGGS.

That was all. No database, no interface, no one else who would use it.

---

## 3. From 1.1 to 1.2: getting the pipeline running, then running it to the end

**The first version answered a single question**: of these more than eighteen hundred peptides already labelled antioxidant, which were safe enough to be worth building a fusion construct for.

The pipeline was written as six stages. The first rule laid down was "run the cheap ones first" — not an aesthetic choice but arithmetic: a tool that processes two thousand entries per second and one that processes twenty-five differ by a factor of eighty, which over twenty-five thousand entries is the difference between "under a minute" and "several hours". So the first step put all three hard filters (toxicity, sensitization, hemolysis) in place at once; the first two are almost free, and the third requires loading a model but is not expensive either. When it finished, of the more than eighteen hundred entries only **107** remained: 656 judged toxic, 1,077 judged sensitizing, and 3 judged hemolytic.

That result was shocking at the time. More than 94% of a collection that had already been curated by others and specifically labelled "antioxidant" failed a single safety line.

The first version also left three habits that were used from then on: scripts stayed independent of one another, with state written to disk rather than kept in the conversation; every rejected candidate had to be written out, recorded together with the tool and score that rejected it; and structure prediction was treated as the ceiling of cost, with the cheap tools taking the bulk first and the high-precision ones reserved for the last few candidates.

The later stages were written but not run to completion, because the goal had already changed: the ceiling of eighteen hundred entries was a few hundred constructs, not worth spending more time to finish.

**The second version was the first to be genuinely run to the end.** The input was changed to 1.08 million entries made by directly concatenating three tables (24,694 + 1,055,961 + 1,117, exact to the last digit), eight rounds, six and a half hours, producing 150 constructs, an elimination rate of 99.986%.

Five things were changed in this version, and each was changed only after hitting a problem. Toxicity prediction was originally to run in the first round over all 1.05 million entries, estimated at twenty-two hours, while the total budget was only a few hours; moved to the second round and run only on a subset of fifty thousand, it took forty-eight minutes with no change in outcome, because everything that reached the second round had already been selected once on activity. The two-channel split was changed to use the raw antioxidant score rather than the weighted total, because the several scores differ in scale and direction, and mixing them before selecting blurs what is actually being selected. The fast and slow structure models originally ran in parallel; the fast one had confidence below 0.30 on this kind of sequence, low enough that the downstream surface-exposure and aggregation analyses carried no information, and it occupied GPU memory while competing with the other — cut, leaving only one to run in series, which was in fact faster and more stable, halving the GPU time. And an intermediate composite score originally carried half the weight of the final ranking; opening the first ninety rows showed it to be almost a constant in this batch (a difference of only 0.011 between quartiles), which amounts to deciding on noise with half the weight, so it was deleted and the final ranking became three structural quantities at 0.40 / 0.40 / 0.20.

This version also established what seemed at the time a refinement and later proved to be the key design of the whole line: **the dual channel**. The high-scoring batch goes into the Top channel, and the lowest batch is carried along the whole way, under exactly the same safety gates, assembly, structure prediction, and ranking. The Bottom channel is not leftovers; it is a paired negative control — if the wet lab eventually finds no difference between the two channels, the core hypothesis of this pipeline is refuted. Here falsifiability is built into the structure, not written into the prose.

---

## 4. Going through the accounts: two errors that raised no error

After 1.2 finished, the pipeline was a success: nothing crashed, no error was raised, and the output was self-consistent. The real problems surfaced only when the saved results were gone through and the arithmetic compared against the design intent, and both were errors of "how it was composed", not of "how it was executed".

The first: **safety could be outvoted**. That version's composite score weighted activity, toxicity, sensitization, hemolysis, immunogenicity, epitopes, and thermostability together, and the safety coefficients were all small — hemolysis 0.09, immunogenicity 0.05, toxicity 0.13. Under that arrangement a peptide with a strong hemolytic signal but a very high antioxidant score could still rank near the top, because the deduction for hemolysis was smaller than the addition for activity. Safety was written as a score, and a score can be compensated. The correct approach is a threshold: pass, or be eliminated, without taking part in any average.

The second: **the antioxidant score leaked out of the channel**. The channel split did use the raw antioxidant score, but the composite used for ranking in rounds three through seven still contained an antioxidant term, and it was the largest coefficient in the table. So the Bottom channel, after being defined as "low activity", continued to be ranked by activity — the two arms were no longer independent, and the comparison that was supposed to serve as a control was weakened.

Both went into the next version's skeleton: not by tuning coefficients, but by changing the structure.

---

## 5. 1.3 and 1.4: from scaling up to redesigning

**The third version tried to leap to the billion scale in one step.** The data sources were entirely replaced here — no longer curated tables but the two largest public sequence resources: UniProt at more than 225 million entries and metagenomic protein clusters at more than 623 million, together more than 849 million.

The first stage was a streaming scan that kept only sequences of three to thirty amino acids made solely of the twenty standard amino acids; it ran for 98.7 minutes and left **19,890,021 entries**, a library of 2.6 GB, at a scan rate of roughly 140,000 entries per second.

The two sources behaved completely differently, and that difference determined the shape of everything that followed. UniProt is a catalogue of full-length proteins and was almost entirely cut away by the thirty-amino-acid ceiling, a pass rate of 0.33%; the metagenome is a catalogue of predicted small proteins and short open reading frames that falls exactly in this window, a pass rate of 3.07%. The consequence is that in the pool that remained **96.3% came from the metagenome and only 3.7% had annotation**. This proportion was not designed; it is the inevitable result of applying a thirty-amino-acid ceiling to two libraries with completely different length distributions.

A deduplication step was also tried — clustering at 90% similarity — but it removed only 0.2% to 5%; short peptides are too dispersed for it to be worth it, and it was abandoned.

What this version really left behind was not results but **the machinery of measurement and recovery**: weights were no longer filled in by hand but derived from the Winsorized standard deviation of each component in this pool (extreme values first clipped to the 5th and 95th percentiles before the standard deviation was computed, lest a single outlier take the whole weight of an item) — components with discriminative power automatically gained weight, near-constants automatically fell to zero, which is far more honest than "someone filled in 0.2"; state moved from CSV into a database, so it could be queried, resumed from checkpoints, and have a later stage read an earlier stage's snapshot; services were changed to be declared per stage and stopped when done, because GPU memory is not released by politely closing a process; and every write was an upsert keyed by candidate ID, so runs could be repeated without producing duplicates.

All of this was inherited by 1.4. The later stages of 1.3 itself were written but not run, because 1.4 had already been redesigned on the same pool.

**The fourth version is the one treated as a genuine result.** It no longer mixes but stratifies: each round uses a single criterion — either ranking and taking a percentile, or setting a threshold and eliminating — and never mixes different qualities into one number. Two things can be weighted together only when they share a scale and a direction, and antioxidant activity and hemolytic risk share neither.

Four rules hang beneath this principle: safety is only a hard threshold — not scored, not weighted, not compensable; the functional score is used once, in the first round, and never appears again, so that the two channels stay independent; the whole pipeline permits a single weighted average, whose weights come from the data, and any manual adjustment must be recorded together with its reason (this rule guards against "changing the weights after seeing who won"); and everything is ordered by cost, with the most expensive run last and only on the smallest set.

Nine rounds, more than sixty hours. The first round ranked by antioxidant score, with the top 10% entering Top and the bottom 1% entering Bottom (the proportions are deliberately asymmetric: the Top candidate pool must be wide, while Bottom only needs enough for a control); the second round judged three safety thresholds independently, with elimination on failing any one, and this round was almost entirely toxicity prediction consuming time, on the order of a day; the third round scored epitopes, thermostability, solubility, and cell penetration, computed each one's standard deviation as its weight, and combined the single weighted score; the fourth round assembled the peptides into molecules — enumerating for each peptide the insertion position and six combinations of linkers, and then **recomputing** solubility and thermostability **on the assembled full-length fusion protein**, because a peptide that is itself both stable and soluble is not necessarily so once attached to a scaffold of more than three hundred amino acids; the fifth and sixth rounds predicted structures and measured surface exposure and aggregation propensity on them; the seventh round combined the final score; and the eighth round reran the top ten of both channels with a second model as an independent check.

The result: 25,944 enumerated constructs reduced to 2,594 and finally to **250** (Top 150 + Bottom 100), an overall elimination rate of 99.9987%. Mean surface exposure 0.72, aggregation propensity 0.33, mean structural confidence 0.42 — the second model produced 0.52, with the same trend and top-end ordering, and this is the only evidence that "the ranking is not the product of any one model".

The final score contains **no functional term at all**. It speaks only of physical quality: whether the protein can fold, whether it will settle out, whether the peptide is exposed. It says nothing about how antioxidant the peptide is.

Two things then emerged that look like errors but are not.

One is that **the global top eight all lie in the Bottom channel**, with the best of them higher than the first of the Top channel. Because the score has no functional term, antioxidant prediction and structural quality are simply uncorrelated in this pool, and the Bottom channel batch was not structurally poor to begin with. The conclusion is not "it ran wrong" but a sentence that must go into the wet-lab plan: candidates must be taken from both channels, and picking only from the Top ten amounts to testing the wrong population.

The other is that **the top two of the Top channel are not carrying a functional peptide at all**. The sequence `MNRPWITGHHHHHHHRRRRRRRRRR`, twenty-five residues, has a short serine-rich leader at the front and six histidines plus nine arginines at the back — a handle for purification or cloning, not an active antioxidant peptide. It got in because preprocessing looks only at length and residue type and it satisfies both; in the first round it received a moderately high antioxidant score; and it reached first place in structure because structural ranking never asks what a peptide does. These two are in fact the same peptide at the same position, differing only in linker length, which is why their scores are almost identical. This later became a discipline: wherever this table is cited externally, either this entry is explicitly annotated or the citation carries the qualification.

There is also a fact that must accompany all of it: structural confidence across the whole dataset is low, with a mean of 0.42 and a maximum of 0.50, and 0.50 is barely the threshold for "meaningful". This is not a problem of the constructs but of silk fibroin itself — glycine-alanine repeats are intrinsically disordered and semi-amorphous, and folding predictors have no natural template to follow. So that score can only be described as "a consistent way of ordering imperfectly modelled structures", not as a precise physical measurement. Nor can a better tool lift the ceiling, because the limit lies in the disorder of the material, not in the level of the predictor.

---

## 6. Stopping to read the literature: reclassifying the eighteen tools

Before expanding from one direction to four, we did something that looked like procrastination at the time and later proved to be the greatest saving of time: every prediction tool we intended to use was read again against the evidence it had itself published, instead of being used according to its manual.

After that reading, four assumptions collapsed.

The first assumption: **the funnel could be copied over directly**. The first version had eight rounds; the platform cut the last four, so carrying over the first four would suffice — it does not. The tools changed, the coverage changed, the failure modes changed; copying over amounts to bringing the assumptions of the old pool into the new one. What should be kept is the principle; what should be rewritten is the rounds.

The second assumption: **pick the strongest tool in each direction as a hard gate**. This is the most intuitive design, and on this data it is thoroughly wrong. These functional models learn "does this look like a peptide in the database", not "does it have this activity". Over more than twenty million real short peptides, their threshold behaviour is nothing like the accuracy reported in the papers: one tool at 0.5 judges 72.83% positive, another judges 99.5%. A threshold that lets through three quarters or nearly the entire library is not a gate. On this kind of data a functional score can only be used for ranking and taking percentiles, never as a probability threshold.

The third assumption: **developability tools are directly usable on short peptides**. They do take sequences, but several were trained only on full-length proteins: one degrades over three to thirty amino acids into a single peak hugging 0.5, with no signal at all; one measures "whether recombinant expression in E. coli will go into inclusion bodies", which is not the same question as "whether a free peptide dissolves in water"; and two require a three-dimensional structure, which short peptides do not have. Only cell-penetration propensity genuinely holds up on short peptides. Developability was therefore forced to split into three layers: usable at the peptide level, usable only after assembly to full length, and excluded because it requires a structure.

The fourth assumption: **the four directions are equally mature**. What they differ in is not model capability but whether there is a clean training benchmark. All three candidate models for anti-inflammatory failed — two had learned "is this a functional peptide" rather than "is this anti-inflammatory", because their negatives were random fragments rather than "functional peptides experimentally confirmed to have no anti-inflammatory activity"; the third had a training set overlapping its own test set. This is a fault of the benchmark, not of the models — the same representation reaches above 0.80 on independently collected data. On the anti-melanogenic side only a locally rebuilt weak ranking remained, uncalibrated. So "four directions" is not four copies of one thing; it is one that can already deliver conclusions plus three still on the way.

This review finally condensed into one sentence: **of the eighteen tools, only three can eliminate candidates, only two can rank functional order (plus one weak one), and the rest can only provide information.** The entire safety semantics of the platform grew out of this sentence.

The architecture changed shape accordingly: one shared safety skeleton (safety depends on the sequence, not on what it is wanted for, so it is identical across the four directions), plus four direction-specific functional funnels (the activities differ, so each has its own models, percentile lines, and maturity), plus a layer of developability weighted by delivery method, and finally an assembly layer.

---

## 7. Four platform runs, and 496 constructs

When it came time to run for real, the approach was: first carve out a candidate pool for each direction — rank the whole library by that direction's functional score and take the top 10%, that is **2,024,889 entries** (about 2.02 million, not the 20.24 million of the whole library; the two numbers must not be confused). Then, on this pool, run the shared safety skeleton plus that direction's funnel.

Four runs, four dates, 496 constructs produced.

Antioxidant ran first, on September 5, 2026, in 8 seconds, producing 170 constructs (Top 113 + Bottom 57), all passing the safety gates. At the time of this run the second immune pathway had not yet been wired in, and B-cell epitopes still had zero rows in the library — the data-driven weights honestly pushed the epitope term to 0.00, with the other three at cell penetration 0.31, sensitization 0.30, and aggregation 0.39. This was recorded at the time as a sentence that had to be made clear: it is a consequence of "which tools happened to be installed at the time", not a modelling conclusion.

Antimicrobial ran on September 12, in 31 seconds, producing 65 constructs (Top 7 + Bottom 58). This was the only run with all four veto gates open. The numbers are ugly, but it is the single most useful measurement of the whole project: of the 250 entries with the highest antimicrobial model scores, 47% were filtered out by the safety gates, and only 7 satisfied both high percentile and safety. **A high functional score and safety are entirely two different things**, and this sentence has had a concrete number ever since.

Anti-inflammatory and anti-melanogenic ran on September 13, in 40 seconds and 18 seconds (113 seconds cold), producing 154 and 107 constructs, all marked as pending sign-off. The data for these two directions exists; what is missing is the sign-off — because the models behind them answer a weaker question than the direction's name. So their scores are marked, in both the data and the interface, as "ranking only, not probability", and no pass/fail badge is given.

496 = 290 selected + 206 control. The target for each direction is 150 + 100; none of the four directions was filled, and the shortfall is entirely in the selected channel; antimicrobial is the most extreme, 7 against 150.

---

## 8. The months spent building the website

The website did not start from design mockups; it started from a pile of hard-coded data. Five pages rendered a single hard-coded dataset, while the engineering description already claimed support for "search, filter, and sort" even though only filtering existed.

The first task was to **delete that static data module together with its type definitions entirely**, with no migration — as long as it remained, no page could be guaranteed not to render a constant secretly. After deletion, every number on the pages could be traced to a column.

The second task was to **pull the thresholds out of the pages and gather them in one place**. The occasion was an audit on September 17 that found three kinds of defect, all of them "the same value copied in several places and then drifting": the same safety threshold table written separately in two pages, with comments still claiming the two share a definition; the immunogenicity threshold hard-coded globally at 0.50 while the route definitions had three tiers, so that a construct sitting exactly on the tightened line was displayed as "all passed"; and generated analysis text citing an acceptance floor that exists in no tool metadata. The fix was not to repair these three places but to fix the layering: the routing layer only validates and serializes, the service layer takes all thresholds and weights, the repository layer writes only SQL, and the model layer only defines contracts. Similar errors thereby become structurally impossible.

The third task was to **move sorting from the browser to the server**. The builder originally fetched a direction's list and sorted it in the browser. Three faults were involved: a construct's composite score depends only on its own direction's weight pool, and that pool is request-independent and cached per direction, so paging the sort made scores jump with the filter conditions; ranking must cover the whole matching set before slicing, otherwise the offset is meaningless; and candidates can come only from the selected channel, since the control channel is the control arm and mixing it in leaves both sides unreadable. After changing to a single endpoint returning the complete ranking, counts describe the whole matching set rather than the current page, and entries whose composite score cannot be computed sort to the end instead of entering as zero.

The fourth task was forced: **the deployment form changed entirely**. There used to be a resident Python service connected to the database on a university workstation, with every request travelling over the network to that machine. Then that machine became unavailable — it is university property and not under the project's control. So the goal became "no backend process, no database connection": data is exported once into static files before deployment and read directly by the frontend; only the conversation cannot be pre-generated (it must handle free-form questions) and is handed to an edge function on the platform that forwards it to the model, with the key existing only in that function's variables and never entering the browser.

The export step involved a key choice: what is exported is not "a direct conversion of the database tables into JSON" but **a call to the backend's own API functions, with their responses saved**. Because all thresholds and judgments are gathered in one place in the service layer, an export script that bypassed the service layer and assembled its own version with its own SQL would be a fifth copy of the same class of defect — and would go out silently.

Three pitfalls were hit along the way, all of the "looks right, actually wrong" kind. One was that static files quietly shadowed the real service: the export directory was placed under the frontend asset directory, and a development build returns any static file first, so what was seen locally was the previous export's snapshot rather than the current library contents; more troublesome, a production build configured with a remote address was also shadowed by the snapshot, and the interface could not tell the difference. The second was that the exported list rows did not line up with the columns used for search: list search covers four columns, while the exported rows carried only the sequence, so on the deployed site a search by accession number found nothing, and neither answer looked wrong on its own. The third was that the two sides wrote numbers differently: the server used Python's formatting to write the fact block, while the edge function used JavaScript to write the same batch of numbers; the rounding agreed, but the notation diverged below 1e-4 and above 1e6, so the model cited a number that could not be found on the page — and "every number the model cites can be found on the page" is the entire reason that fact block exists.

The website ended up as five pages. The four numbers on the landing page are all computed from the API, not hard-coded. Library browsing is split into three tabs: peptides and constructs, scaffolds, and linkers. The builder has five steps: choose the application route, choose the functional direction, confirm the scaffold, confirm the linker, and produce the result. The detail page has four tabs, and the construct tab is the heaviest: composite score, rank, and aggregation propensity at the top, the safety gate panel below, the sequence coloured in three segments (scaffold blue, linker green, functional peptide orange, with any unavailable segment drawn as a grey placeholder rather than as residues), and further down the same-direction comparison and six automatically generated text blocks. The scaffold detail page has a section specifically listing "fields genuinely absent from this data", so that "this field does not exist" can be distinguished from "this panel is broken".

Two design decisions are worth recording. **The platform does not ask users questions they cannot answer**: a non-specialist cannot choose among eight scaffold proteins, and a specialist does not want to be asked at every step either, so scaffold selection changed from "the user decides" to "derived from the product form" — the user says what product is wanted, and the platform determines the scaffold. The linker is different: its real difference is a single rigidity tier, and the trade-off between flexible and rigid can be judged without protein-engineering training, so it remains an editable option. Both affect only the assembled sequence, not the candidate set or any score, and the interface states this plainly, so that no one mistakes a change for having filtered something out.

The other is that **the delivery method is not left for the user to choose; it is derived from the route**. This is not a simplification of the interface but a question of scoring: the delivery method materially changes who ranks first and who survives — the injection and wound routes tighten the immunogenicity threshold to 0.35, so the same construct may pass under a mask patch and be vetoed outright under those two routes. Letting the user pick freely would amount to letting them decide which candidates qualify without understanding the consequences.

The five routes are ordered by one physical fact: **how intact the barrier is at the interface the construct finally contacts**. Into tissue (injectable filler) — barrier broken (wound dressing) — barrier intact but occluded (mask patch) — barrier intact and not occluded (topical film) — non-living surface (hair care). The immune threshold follows this line: 0.35 / 0.35 / 0.50 / 0.50 / 0.60. Wound dressing is in the same tier as injection, and this must be stated clearly: the wound barrier is broken to begin with, the construct contacts tissue fluid directly, and the immune exposure is of the same order as injection; treating it as intact skin would underestimate the risk.

---

## 9. What is at hand now

The data has three layers. At the bottom are 20,002,488 short peptides together with the scores twelve tools gave each of them, in a score table of more than 367 million rows and 130 GB. In the middle are 496 constructs, each carrying nine scores, safety markers, and parameters. The top layer is small but hardest: eight scaffold protein clusters and sixteen patent sequence variants, all with real amino acid sequences, graded by evidence from E1 to E5; and fifteen curated linkers with rigidity tier and literature source.

All four stages of the pipeline have been run, two directions are signed off and two are marked pending sign-off, and the four three-dimensional rounds are explicitly out.

The service layer has nineteen read-only endpoints plus one conversation endpoint, all working. All five frontend pages take their data from the library; the former batch of static data modules and type definitions has been deleted, and no page renders a hard-coded value any more.

The deployment is live, static export plus one edge function, and the data is the snapshot of the moment of deployment — so the answer to "is the data up to date" is always "when was the last export".

Verification has three layers: 115 backend tests (113 pass, 2 skipped, the two skipped because the fixture data happens not to satisfy the condition under test); a static-layer walkthrough run with no backend at all, 91 assertions, one of which compares the sequence assembled by the interface residue by residue against the service's sample, and another that fails if any read request ever reaches the network; and two walkthrough suites running the real application in a DOM simulation, 33 and 25 assertions, making real clicks against the real service.

What is missing is also specific. The chain from construct to scaffold is broken — all 496 point to the same placeholder scaffold, whose sequence is a marker string of length zero, so no construct can read a real scaffold or assemble a complete fusion sequence. A backfill strategy was later designed for this: the team material covered the scaffold side completely but did not state which peptide should pair with which scaffold, and the only key joining the two sides is the application route; the rule is to take the highest evidence grade on that route, and on a tie the one claimed by fewer routes, and on a further tie order by name. The result is that three directions land on the same recombinant collagen cluster and the fourth on another. But this binding is the platform's per-route default, not the pipeline's output — no record shows the pipeline having made this pairing, so the service marks it "inferred" rather than "verified".

The two immune pathways have never been merged. MHC-I has a value on 117 constructs, MHC-II on 186, 298 have a value on at least one, and 198 have both empty. For these 198, the immune gate is in the "not evaluated" state, and the interface reports "cannot be determined", not "passed", because a gate that has not been evaluated eliminates nothing, which is a rule hard-coded in the pipeline.

One more thing has not changed since the first version: **all functional numbers are predictions, and none of them is experimental evidence**. A high composite score means "in the view of these models, which have known biases, this construct looks makeable", not "this peptide really is antioxidant". The platform's contribution is to make predictions legible and to keep the unsafe outside, not to replace experiments.

---

## Appendix: a timeline

| Time | What happened |
|---|---|
| Starting point | Four functional peptide tables, one silk fibroin, ten linkers; 1,843 antioxidant peptides enter the first version |
| 1.1 | Six stages, 107 entries left after the hard filters; the design principles were fixed, and the later stages were not run to completion |
| 1.2 | 1.08 million entries, eight rounds, six and a half hours, 150 constructs; the dual channel established |
| After 1.2 | Going through the accounts turned up two errors: safety could be compensated, and the antioxidant score leaked |
| 1.3 | Source changed to public libraries, 849 million entries scanned, 19.89 million kept, 98.7 minutes; weighting, checkpoints, services started on demand |
| 1.4 | Nine rounds, sixty-five hours, 250 constructs; one criterion per round, safety as veto only |
| 2026-09-05 | Eighteen tools reread, four assumptions overturned; on the same day antioxidant produced 170 constructs |
| 2026-09-12 | Antimicrobial produced 65 constructs; 47% of the high-scoring peptides were toxic, leaving only 7 in the selected channel |
| 2026-09-13 | Anti-inflammatory 154 constructs, anti-melanogenic 107, both pending sign-off |
| 2026-09-17 | Audit found thresholds copied in several places and the immune threshold hard-coded; layering refactor |
| After that | Static data deleted, sorting moved to the server, deployment changed to static export + edge function, website live |
| Now | 496 constructs, 496 scaffold bindings pending backfill, two immune pathways unmerged, all functionality is prediction |

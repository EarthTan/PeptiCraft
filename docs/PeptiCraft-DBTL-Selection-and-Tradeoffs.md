# DBTL Writing Notes: What Can Stand Up, and Which Numbers Must Be Fixed First

This document holds the candidates sifted out of the recollection, and the five that the final draft used, discarded, or had to correct.

## 1. Seven places that can stand as cycles

There are only two criteria: **whether all four legs are present** (especially whether Test actually measured something, rather than "it finished"), and **whether it was later confirmed again**. Candidates satisfying both take priority.

| # | Candidate cycle | Four legs | Later measured results | Value | Disposition |
|---|---|---|---|---|---|
| 1 | Dataset census → abandon self-training, switch to orchestrating tools | Complete | The whole architecture is its result | ★★★★★ | Adopted as Cycle 1 |
| 2 | Safety as a weight → change to a threshold | Complete | Antimicrobial run: 47% of the top 250 eliminated, leaving 7 in the selected channel | ★★★★★ | Adopted as the first half of Cycle 2 |
| 3 | The control channel ranked by its own defining property → each metric used only once | Complete | All 8 globally highest come from the control channel | ★★★★★ | Adopted, merged into Cycle 2 |
| 4 | A tool with no discriminative power = noise → variance-aware weighting | Complete | With the epitope table empty, the weight was automatically computed as 0.00 | ★★★★☆ | Adopted as Cycle 3 |
| 5 | Label volume is the ceiling → abandon labels, scan the whole library | Complete | 19.89 million candidates, 96.3% unlabelled | ★★★★★ | Adopted as Cycle 4 |
| 6 | Rereading the tools + a failed retraining → reclassify by role | Complete | The same 0.5 threshold judges 72.83% positive; another tool 99.5% | ★★★★★ | Adopted as Cycle 5 |
| 7 | Order by cost (fast first, slow later) | Half | Estimated down from 22 hours to 48 minutes | ★★★☆☆ | Merged into the Learn of Cycle 1; too thin to stand as a round on its own |
| 8 | The dual channel is the control the wet lab needs | Design only | — | ★★★☆☆ | Merged into the Design of Cycle 2 |
| 9 | Server unavailable → static export + edge function | Complete | The new form exposed three more defects | ★★★☆☆ | Not used. It belongs to delivery engineering; judges would see it as leaning toward software operations |

**Why five rather than nine**: with more than five cycles, each round can only be given two or three sentences, the Test leg is compressed into "it finished", and points are lost instead. With five, each has exactly the room to state clearly "what was measured".

**Item 6 is the strongest cycle at hand**, because it contains a **failure**: retraining brought only a slight improvement, and the defect reappeared with a different representation. This negative result located the problem in the benchmark rather than the model, and for that reason it later became possible to mark two directions as WIP instead of forcing them.

## 2. Five places that must be changed before the final draft

If these are not changed, they will clash with the other submission materials in the repository, and even with one another.

**1. The output of 1.4 is 250, not 150.**
The record is **Top 150 + Bottom 100 = 250**, not "50 bottom + 100 top". The whole funnel is 19,890,021 → 250, an elimination rate of 99.9987%.

**2. The 0.38 of ToxinPred3 must not be written as "the threshold recommended by the paper".**
Two statements in the repository clash: the 1.x master text says "calibrated by this project on this library's distribution; the only threshold in the whole system that belongs to the project itself", while the platform proposal table says "default threshold". Both statements exist, which shows the attribution has not been settled.
**Recommended phrasing**: do not mention attribution, and write only "pin the toxicity line at 0.38 and enforce it as a hard elimination". This neither lies nor loses points — the emphasis is on the act of hard elimination, not on where the number came from.

**3. The weights of 1.2 are not "equal weighting".**
The record shows manual assignment: antioxidant 0.50, B-cell epitope 0.20, cell penetration 0.15, immune 0.10, graph-based cell penetration 0.05; the three safety coefficients 0.13 (toxicity) / 0.09 (hemolysis) / 0.05 (immune).
Writing "equal weighting" would clash with other materials. **Recommended phrasing**: "weights assigned by hand, with the coefficients of the safety terms far smaller than those of the activity terms" — the conclusion is the same, but it survives an audit of the figures.

**4. The metagenomic library is called MGnify, not Magnify.**
It is recorded in the repository as `legacy_mgy_2022`, the 2022 version. This is EBI's metagenomic protein catalogue, and a misspelt name is visible to a reviewer at a glance.

**5. The 800 million did not first come into use at 2.0.**
849 million (UniProt 225.6 million + metagenome 623.8 million) is the "scan first, then filter" action of the **1.3** step; after the scan 19.89 million remained, and **1.4 used exactly these 19.89 million**; the 2.0 library is 20.249 million (ten sources).
**Do not write "the 800 million only formally entered service at 2.0"** — that would contradict the 20 million the project itself reports. The accurate statement: the 800 million is the scan volume and the 20 million is the post-filter volume; the two numbers cannot be exchanged.

## 3. Two details that can be written without concern

**The motivation for the dual channel**: the wet lab needs a control. This is consistent with the record (the recorded reason is "to make the results falsifiable"), can be used directly, and sounds better than a purely technical reason.

**Length filtered out the great majority**: this step has hard numbers. UniProt's pass rate was 0.33% (225.6 million reduced to 730,000), the metagenome's pass rate 3.07% (623.8 million reduced to 19.16 million). When writing "the first round filtered out the great majority", these two percentages can be included.

## 4. One trade-off made in the final draft

The recollection records two problems in the 1.2 round (safety being overridden, the control channel not being independent), but they were found in the **same audit**. So they were not split into two rounds but merged into one round, "one audit, two design errors", with the two legs written in parallel.

The reason: splitting into two rounds would make readers think two iterations were performed when there was one; merging them instead explains better the most valuable property, that "it ran successfully and the results were self-consistent, and the error was in the composition".

The final draft handled this way is at `PeptiCraft-Engineering-DBTL.md`, five rounds, about 1,460 words.

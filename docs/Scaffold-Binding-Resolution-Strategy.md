# Scaffold Binding Resolution Strategy

> Chinese version: [中文版](Scaffold-Binding-Resolution-Strategy.cn.md)

The 496 precomputed constructs in the database point to the same scaffold row, while the genuinely usable scaffolds are held in another table, and there is no correspondence between the two. This document explains how the placeholder state arose, which half the scaffold material provided by the team filled in, the changes already in place together with how they were verified, and the three items that still require a team decision.

## How the placeholder state arose

A construct is assembled from three sequence segments: scaffold, linker, and functional peptide. The latter two are real in the library — the functional peptide comes from the peptide library and the linker from the linker table. The scaffold segment is not. The pipeline had no scaffold-selection step when writing to the database; it took the first row of the scaffold table and the first row of the linker table and wrote the construct record from them. What was written into the fusion sequence field was a text string formed by joining the scaffold's **name**, treated as a sequence, to the linker and the functional peptide with vertical bars. This processing path applied to all 496 constructs across the four functional directions, so they point to the same scaffold row, and that row's sequence field holds a literal marker string, recorded as length 0.

The real scaffolds are held in `scaffold_library`, whose primary key is a text identifier; the `backbone_proteins` table referenced by constructs has an integer primary key. There is no mapping between the two identifier sets, and the names do not overlap either — on the placeholder side are a few abbreviations for silk fibroin and elastin, and on the real side are the patented constructs of eight structural proteins. The placeholder therefore cannot be turned into a real scaffold by changing an identifier; what is missing is a whole set of correspondences.

## Which half the team material filled in

The team material explains the scaffold side clearly: eight protein clusters, sixteen patent sequences, one representative sequence per cluster, with application labels, evidence grades, and experimental records. It does not, and does not undertake to, address the construct side — no row in the material connects a peptide or a functional direction to a scaffold.

So the only common key on which the two sides can meet is the **application route**. A scaffold belongs to a number of routes through its application labels; a construct, through the scenario name it records, can also be mapped to a number of routes; the scaffolds falling on the same route are that construct's candidate scaffolds. This path works only on the premise that the route definitions agree between the material side and the platform side.

## Inconsistency within the material itself

The material states that the master table uses only four application labels: film coating, Mask patch, Wound dressing, and Injectable filler, with the old scenario labels and delivery labels listed as deleted. Yet the label columns of the same material are still five, the fifth being Hair care, and the repeat-unit and purification-tag versions carry over the labels of the parent protein. The difference between the two definitions is concrete: recomputed on the four labels with inherited labels removed, the number of scaffolds per route is 2 for film coating, 3 for Mask patch, 4 for Wound dressing, and 1 for Injectable filler, counted by protein cluster; whereas counted by the labels actually present in the table, the hit row counts are 3, 8, 7, and 5, with Hair care hitting 5 rows.

Data processing has been carried out according to the material's declaration: four labels are taken, and the Hair care column is read out but mapped to no route. The consequences of this being in place are described in the next section. The material's rule that "repeat-unit and purification-tag versions no longer inherit the parent labels" has not been executed, because the material gives no rule for deciding which records belong to that class, and inferring from the `_repeat_` string in record identifiers would sweep in the Yusong and Bolt Threads constructs as well, contradicting the material's own count for film coating (2, including Bolt 18B). This item is therefore left pending a basis for judgment from the team.

## Changes on the platform after the definitions were applied

After the hair-care label was withdrawn, the hair-care route among the platform's five application routes no longer has any scaffold in the scaffold library; the interface shows no scaffold available on that route, the route itself is retained, and its screening configuration and immune threshold are unchanged. eADF4(C16) loses its only application label and becomes a scaffold with no application label. The anti-melanogenic direction's former candidate routes included hair care; after narrowing, mask patch and film coating remain available, and the direction itself is unaffected.

If the material's rule that "repeat-unit and purification-tag versions no longer inherit labels" is later executed, the Jinbo 30-aa COL3A1 functional-region 16-repeat construct would likewise lose its label, and the candidate scaffolds for the injectable filler route would fall from two to one; that item has not been executed, for the reason given in the previous section.

## The three changes already in place

The first is the material read path. The scaffold material directory has been moved from `data/` to `resouces/`, while the script that reads that directory and writes the scaffold library still pointed at the old location and could not rebuild the scaffold library from the material; the path in the script has been changed to the new directory.

The second is the label definition. `import_scaffold_library.py` originally mapped the five label columns one by one to the five routes; it is now a table carrying column numbers, in which the Hair care column explicitly maps to no route, with a comment stating that this is a result of the team's declaration rather than an oversight. The server-side `SCENARIO_ROUTE_HINT` has correspondingly dropped the hair-care entry under `depigmentation`, because that entry can no longer resolve to a scaffold.

The third is the addition of `service/scripts/bind_construct_backbones.py`. It writes the eight scaffold clusters into `backbone_proteins`, with real representative sequences and lengths, so that constructs can reference real scaffolds; it then rebinds, one by one, the constructs still on placeholders according to their routes. Writes are keyed by name, so the plan can be generated without connecting to the database, and can also be exported as a SQL file directly executable with `psql`, to be applied once the database host is restored.

## Rules followed by the backfill

A construct record's scenario name yields an application route through `SCENARIO_ROUTE_HINT`; the route then yields candidate scaffolds through the material's application labels; among the candidates the one with the highest evidence grade is taken, and on a tie the one marked by fewer routes — a scaffold accepted by one route fits that use more closely than one accepted by three. When a tie remains, ordering by short name guarantees that the result is reproducible. The rule produces: the antioxidant, antimicrobial, and anti-inflammatory directions all land on wound dressing, sharing Trautec COL17; the anti-melanogenic direction lands on mask patch, using Jinbo HC8/HC16. That three directions share one scaffold follows from their functional descriptions all pointing at wound use; it is not an accident of the value selection.

The defaults for the mask patch and injectable filler routes are additionally pinned explicitly to Jinbo HC8/HC16. The reason is that these two routes have two candidates of the same evidence grade, and the rule on a tie falls to the Jinbo 16-repeat construct, which is exactly the class the material declares "no longer inherits labels"; the pinned entry carries a label under any definition, so the default does not depend on how that question is settled. Removing the pin restores the rule's computed result, and both answers are printed together in the script's output.

The bindings written by the backfill are the platform's defaults by route, not pipeline output — no record shows the pipeline having made this pairing. The server side already makes its own distinction: a binding recorded on the construct reports as `verified`, while one specified at request time reports as `inferred`. The rows after backfill fall in the former group, and that group's description claims only that the pairing is recorded on the construct, not who selected it.

## How it was verified

All changes were executed once against the production table structure on a temporary local PostgreSQL 18 instance: tables were created and placeholder rows matching the shape of the real database written in, the generated SQL was then executed, and each construct's fusion sequence was checked to be equal residue by residue to "scaffold + linker + functional peptide", with all four constructs matching; re-executing the same SQL updated 0 construct rows and left the scaffold row count unchanged, confirming idempotence. The two value paths of the scaffold import script and the backfill script (reading the source table, reading the scaffold library) gave consistent results. Server tests: 113 passed, 2 skipped; frontend type checking reported no errors; the 7 static-check warnings remained the same in number as before the change.

The production database host is currently unreachable, so the changes above exist in code and scripts and have not yet been written to the real database; the SQL file can be executed directly once generated.

## Three items still requiring a team decision

The correspondence between directions and routes. The backfill currently lets the scenario name recorded on the construct decide the route, and three directions therefore share wound dressing. If a direction should fall on several routes at once, or a direction's preferred route needs to change, the corresponding place is one central table.

The default scaffold for each route. The highest evidence is currently taken, with two routes additionally pinned. If the team designates a different scaffold, changing one place suffices, and the rest need not be regenerated.

The inheritance rule for repeat-unit and purification-tag versions. This item affects the labels of the Yusong, Bolt Threads, and Jinbo 16-repeat construct clusters, and hence the candidate range for mask patch and injectable filler. Once the basis for judgment given by the material is confirmed, the import and backfill need only be re-executed.

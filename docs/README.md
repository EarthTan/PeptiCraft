# Project documentation

Six documents in Chinese, about 130 KB together, covering the platform from its product form down
to the table definitions behind it. They are written for three readers at once: the project lead,
who needs the state of the work rather than the code; domain specialists, who need the biology and
the meaning of each field; and whoever takes the work over next, who needs to know what is
finished, what is provisional and where the decisions are recorded.

| Document | Covers |
| --- | --- |
| `PeptiCraft-文档体系/00-总览.md` | Project positioning and a status snapshot. Start here. |
| `PeptiCraft-文档体系/01-产品形态与用户体验.md` | The five pages, the walkthrough, and an inventory of what is complete. |
| `PeptiCraft-文档体系/02-数据资产与数据形态.md` | The three data layers and the conventions that govern how a value is read. |
| `PeptiCraft-文档体系/03-生物学逻辑与筛选管线.md` | The four pipeline rounds, where each threshold came from, and the weighting. |
| `PeptiCraft-文档体系/04-技术架构与开发进度.md` | Architecture, the endpoint surface, progress by layer, and the open risks. |
| `PeptiCraft-文档体系/05-开发交接技术参考.md` | Full endpoint table, enumerations, invariants, and where a given change belongs in the code. |

The six are numbered rather than nested: a reader starting at `00` reaches any later document
without having read the ones between. Terminology is explained where it first appears instead of
being collected into a glossary or an appendix, and each document is organised by topic rather
than by section of the codebase, so a topic is covered in one place.

Four documents have the same subject matter as the directory READMEs and are not duplicates of
them. The READMEs describe how to run a directory and what is inside it; these documents carry the
reasoning, the provenance and the unfinished business. Where the two disagree, a running endpoint
and a `count(*)` against the database are what settle it.

An earlier generation of project documents was retired when this set was written; the READMEs in
`../service/`, `../app/` and `../data/` were written against the same state. The screening
pipeline under `../iGEM-platform-main/` has its own documentation, which is a separate body of
work and is not part of this set.

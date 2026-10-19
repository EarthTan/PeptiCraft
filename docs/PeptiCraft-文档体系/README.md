# Project Documentation

Seven documents in English, about 165 KB in total, covering everything from product form through to release progress. They address three kinds of readers at once: the project lead, who cares about work progress rather than code; domain experts, who care about the biology and the meaning of each field; and whoever takes over next, who needs to know what is complete, what is still in provisional form, and where the decision records are.

| Document | Content |
| --- | --- |
| `PeptiCraft-文档体系/00-总览.md` | Project positioning and status snapshot. Start here. |
| `PeptiCraft-文档体系/01-产品形态与用户体验.md` | The five pages, walkthrough records, and an inventory of completeness. |
| `PeptiCraft-文档体系/02-数据资产与数据形态.md` | Three layers of data, and the conventions that govern how a value should be read. |
| `PeptiCraft-文档体系/03-生物学逻辑与筛选管线.md` | The four-round pipeline, the source of each threshold, and the weighting scheme. |
| `PeptiCraft-文档体系/04-技术架构与开发进度.md` | Architecture, the API surface, progress by layer, and open risks. |
| `PeptiCraft-文档体系/05-开发交接技术参考.md` | The complete endpoint table, enum values, invariants, and where in the code a given class of change belongs. |
| `PeptiCraft-文档体系/06-上线进度与后续工作.md` | The status of the static deployment conversion, the three items remaining before release, and the new boundaries imposed by the deployment form. |

The seven are numbered rather than nested: starting from `00`, a reader can reach any later document directly without passing through the intervening ones. Terms are explained where they first appear rather than collected into a glossary or an appendix; each document is organized by topic rather than sectioned by code structure, so a single topic is covered in one place.

Four of the seven share their topics with the READMEs in individual directories, but they are not duplicates of those READMEs. A README explains how a directory runs and what it contains; these documents carry the reasons, the provenance, and the outstanding items. Where the two disagree, the running API and a single `count(*)` against the database are authoritative; the parts concerning the deployment form take *06 Release Progress and Remaining Work* as authoritative, since it was written after the form changed.

An earlier generation of project documentation was retired when this set was written; the READMEs under `../service/`, `../app/`, and `../resouces/` were written against the same state. The screening pipeline appears locally as `../iGEM-platform-main/`, a copy (mirror) of [EarthTan/iGEM-platform](https://github.com/EarthTan/iGEM-platform); it carries its own documentation and is not part of this set. The positioning and succession of the three repositories are described in [`../repositories.md`](../repositories.md). The deployment steps themselves are recorded in [`../../app/DEPLOY.md`](../../app/DEPLOY.md), an operational document for whoever carries out the deployment; this set explains only the trade-offs and boundaries of the deployment form.

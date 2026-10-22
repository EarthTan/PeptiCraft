# PeptiCraft Website and iGEM Presentation Optimization Plan

> Version date: 2026-10-17. Applies to: the PeptiCraft product website, the DKU iGEM 2026 Wiki and the Software deliverable.
> Chinese version: [中文版](Website-Optimization-Plan-2026.cn.md)

## 1. Core Positioning

**One-sentence claim:** PeptiCraft organizes precomputed functional-peptide predictions, protein-scaffold evidence and application-route-related screening rules into a traceable candidate design workflow, helping researchers choose the next fusion protein construct worth validating.

All pages of the website should jointly hold two boundaries:

1. What the platform outputs is computational candidates and rankings, not experimental conclusions about activity, safety or clinical efficacy.
2. Missing data, model bias, unconfirmed directions and inferred construct relationships must all be stated at the place where readers see the conclusion, and must not be hidden only in the methodology documentation.

The core audiences are, in order, judges, future iGEM teams, computational-biology users, and people without a protein-engineering background who need to understand the project. The home page first explains what problem the project solves, then presents the workflow and the evidence, and finally guides readers to try the tool or to go deeper into the Wiki.

## 2. Website Design and Content Strategy

### What a visitor should understand within 30 seconds

1. **Problem:** There are many functional-peptide candidates, and prediction, safety gating and scaffold selection are scattered, making it difficult to form an interpretable experimental candidate.
2. **Solution:** PeptiCraft puts candidate screening, route-related safety and developability assessment, and scaffold and linker assembly into a single workflow.
3. **Evidence:** Each candidate can be traced to its sources, model scores, thresholds, composite-score composition and part provenance.
4. **Boundaries:** Scores require experimental validation; two functional directions are still WIP; the current data snapshot has no verified scaffold pairing.
5. **Next step:** A judge can open the builder directly, view the complete evidence for one candidate, or find the data, models and reproduction instructions from the Wiki.

### Proposed Wiki information architecture

| Page | Question the page answers | Content that must appear |
|---|---|---|
| Home | What problem does the project solve, and what has been built? | Project claim, system diagram, key results, evidence boundaries, entry links |
| Project / Description | Why was this problem chosen? | Source of the need, users and stakeholders, project goals, success criteria |
| Engineering | How did the design iterate based on results? | Design-Build-Test cycle, designs that were changed, records of failures and decisions |
| Software | How is the tool used, validated and reproduced? | User scenarios, data and models, architecture, inputs and outputs, benchmark validation, API/format, installation, licence, limitations |
| Dry Lab | How are candidates obtained? | Inputs, rules, tool versions, threshold provenance, retained/eliminated counts, error and bias for each round |
| Wet Lab / Results | Which claims were actually measured? | Reproducible methods, raw data, units, replicate counts, controls, statistical methods, failed results; state directly when there are no experimental results |
| Safety & Ethics | Who identifies the risks, and how are they mitigated? | Biosafety, model misuse, privacy, AI-assisted content, real-world application risks and mitigation measures |
| Human Practices | How did outside input change the project? | Interviewees and methods, feedback, specific design changes, input not adopted and the reasons |
| Contributions / Attributions | What can later teams take away? Who completed what? | Reusable code/data/methods, Registry records, attribution of contributors and external resources |

Wiki pages should use consistent navigation, terminology, legends and citation formats. Figures should state units, sample size, data source and the "prediction/experiment" type within the figure itself; each figure should be accompanied in the body text by the conclusion readers are meant to draw, rather than being placed without explanation.

## 3. Design Language and Accessibility

- **Visual direction:** Retain the existing blue-green gradient as the PeptiCraft identity colour, and adopt a clear laboratory-record style overall; use whitespace, grids and a numbered workflow to establish hierarchy, and no longer substitute marketing-style "all-encompassing" copy for evidence.
- **Information hierarchy:** The home page first presents the project claim and the two main entry points; after that it presents the workflow, key methods, evidence boundaries and reusable information. Decorative images must not compete with data figures for attention.
- **Figure system:** Establish fixed labels for "measured, predicted, inferred, not assessed, WIP"; colour alone must not carry the meaning. Sequence segmentation, risk levels and evidence tiers should use text and colour together.
- **Accessibility:** Support keyboard navigation, clear focus styles, skip navigation, screen-reader progress status, zoom and narrow screens; respect the reduced-motion preference. Maintain sufficient contrast between body text and background, and make interactive targets easy to tap on touch screens.
- **Consistency:** The product name is uniformly `PeptiCraft`; unify the definitions of candidate, construct, scaffold, linker, composite score, prediction and experimental measurement. Page titles, favicon, share summaries and the footer should all use the same brand convention.

## 4. Correspondence with iGEM Judging Requirements

### Best Wiki and General Project

| Judging concern | Evidence the website needs to provide | Current direction for improvement |
|---|---|---|
| Clear project goals | One-sentence claim, user needs, success criteria | The home page starts from the candidate-design problem and reduces generalized promotion |
| Data supports claims | Each result distinguishes prediction from experiment; controls, sample size, units and methods are shown | The results page connects raw scores, thresholds, ranking semantics and coverage |
| Easy to find and understand | Clear page hierarchy, cross-page links, figure captions, term explanations | The home page takes on the entry role; the Wiki's Software, Dry Lab and Results pages link to one another |
| Usable as a long-term record | Data version, code version, reproducible steps, negative results, follow-up recommendations | State the export time, data snapshot and environment requirements; preserve failed and unfinished work |
| Accurate sources and attribution | Provenance of literature, datasets, models, code, images and external assistance | Establish a citation list for figures and materials; unify the reference format |
| Engineering and Human Practices | Design iteration records, how stakeholder input changed the project | Each piece of feedback corresponds to a design change, evidence and decision date |

### Best Software

The official 2026 Best Software criteria cover six items: compatibility with synthetic-biology standards, validation quality, value to other projects, integration with external tools, usability, and whether future teams can maintain and extend it. The website and the Software page should each provide directly checkable evidence:

| Concern | Suggested evidence and next step |
|---|---|
| Standards compatibility | Explain the inputs, outputs and sequence representation; assess SBOL 3 or other suitable sequence/construct exchange formats. If a standard is not adopted, explain the boundaries of the current data model and the conversion path. |
| Validation | Provide an independent test set or benchmark, applicability per direction, failure cases and coverage; establish a prediction–measurement correspondence where wet-lab results are available. A model's own training data cannot be used to prove that the model works. |
| Useful to the community | State the reusable parts, screening rules, data-curation methods and scope of applicability; explain how other teams can substitute directions, models or input data. |
| External integration | Publish stable data-structure/API documentation and provide FASTA/JSON exports with provenance, version and score semantics; assess Registry or SBOL workflows step by step. |
| Usability | Record task observations of new users completing "find a candidate—understand the verdict—reproduce the result", and fix the obstacles actually encountered; publish the process rather than pre-writing conclusions about user feedback. |
| Maintainable | Provide an architecture diagram, installation/run steps, environment-variable documentation, model and data versions, known limitations, API contracts and contribution instructions. |

**The eligibility checks must be completed immediately:** iGEM 2026 requires software to use an OSI-approved open-source licence and to place the source code in a dedicated repository on iGEM GitLab; teams from the Software & AI Village cannot compete for Best Software. The GitHub workspace currently checked has no `LICENSE` file, and the local materials are insufficient to confirm the dedicated GitLab repository and the team's Village status. The team should verify these three items before submission; the licence is a legal authorization and must be explicitly chosen by the team, and website copy cannot substitute for it.

## 5. Risks and Current Content Boundaries

- The data snapshot was recorded on **2026-10-15**; before formal deployment it should be confirmed that the data version seen in this round of judging is consistent with the Wiki text.
- The anti-inflammatory and anti-melanogenic directions are still marked WIP. The home page, results and presentation script must not promote them alongside directions that have been signed off.
- The composite score is used for ranking, not as an activity probability; scores from different functional directions and routes should also not be compared directly across the board.
- The scaffold binding in the current construct data is a placeholder value. What a user obtains after selecting a real scaffold in the builder is an assembly inferred on request, not an experimentally validated fusion protein.
- An unassessed safety metric is not equivalent to passing; when explaining safety conclusions, the assessment coverage and the gaps should be reported together.
- If model chat is enabled, the page needs to disclose the model provider/purpose, the verification method and the privacy boundary, and to retain the marker "answers are generated by a model". AI-assisted content is verified by and the responsibility of team members.
- The current user workspace has no visible root licence. Do not add any licence to the repository without team authorization.

## 6. Execution Order

### From now to 2026-10-21: before submission

1. **17 October:** Unify the project claim and the evidence boundaries; check whether the home page, the builder and the results page distinguish prediction, inference, WIP and experimental results. Confirm the team's Village, the software licence and the dedicated iGEM GitLab repository.
2. **18 October:** Fix the data and model versions; compile the six Best Software evidence items, the complete installation guide, the system diagram, the API/data-format documentation and the literature/material citations.
3. **19 October:** Have team members who did not take part in development walk through the judge path: understand the project within 30 seconds, reproduce one result within 3 minutes, and locate the limitations and sources; collect problems and fix blocking points.
4. **20 October:** Freeze the page content; check the consistency of counts and terminology across the Wiki, the software submission, the presentation script and the demonstration; complete the final build according to the real deployment method and confirm the deliverables list.
5. **21 October:** Confirm on the iGEM Deliverables Dashboard the delivery status of the Wiki and Software, that submission succeeded, and that links are accessible. The official 2026 page lists 21 October as the deadline for the Wiki and Software.

### Before and after the Jamboree: strengthening long-term value

- Establish an item-by-item correspondence between model results and available wet-lab measurements, and publish negative results, the calibration process and the boundaries of applicability.
- Provide versioned data exports, reusable API/standard formats and reproducible demonstration samples.
- Continuously improve screening, candidate comparison and result interpretation based on user task observations; write the feedback and the changes it prompted into Engineering and Human Practices.
- Enable future teams to reproduce the main workflow starting from a new dataset, rather than only being able to view the current snapshot.

## 7. Product Website Adjustments Implemented in This Round

- The first screen of the home page was changed to explain how PeptiCraft turns peptide screening into traceable candidates, and to make explicit that prediction results are not experimental or clinical validation.
- A "how to interpret results" section was added, explaining ranking semantics, unassessed safety gates and the inferred nature of the current scaffold pairing.
- Navigation and builder steps gained current-status indicators, skip navigation, visible focus and reduced-motion support.
- A fallback page for unknown routes was added; the site title, search summary, brand favicon and iGEM Wiki entry point were updated.

## Reference: official iGEM 2026 pages

- [Special Awards: questions and eligibility conditions for Best Wiki and Best Software](https://competition.igem.org/judging/special-prizes)
- [Project Awards: General Project judging questions](https://competition.igem.org/judging/awards/project)
- [Deliverables: 2026 deliverables and timeline](https://competition.igem.org/deliverables/)
- [Rules & Policies: entry point for the attribution, AI, communication and safety policies](https://competition.igem.org/about/rules-and-policies)

# AI chat: evidence contract and verification

The assistant explains candidate records and the sources attached to the selected scaffold
and linker. It does not establish the efficacy, safety or expression conditions of a newly
assembled fusion protein.

## Answer construction

Both the Python service and the deployed Pages Function resolve the current construct,
application route, scaffold and linker before producing an answer. The selected route sets
the composite and immunogenicity gate. A request-time scaffold pairing remains a
reconstruction, not a pipeline-validated pairing.

The export includes complete per-route safety contexts and per-route standing analyses.
The static detail view and chat use those server-computed contexts. An incomplete snapshot
must fail explicitly rather than mix the current route with the default route's thresholds.

The model writes an original answer to the current question and recent conversation. It
returns `answer` and `evidence_ids`; the evidence catalogue is context rather than a list of
paragraphs to paste into the answer. Record values are referenced with `{{fact:key}}`
placeholders, which the server replaces with labelled values and their evidence. Unknown
references, untraceable numeric values, URLs and malformed output are rejected. These checks
reduce numeric and citation errors; they cannot prove every qualitative scientific statement
or inference is correct. Real model evaluation is still required.

Record mode selects from the catalogue using English and Chinese topic keywords. It is an
explicit **View records** action, shown separately and excluded from AI conversation history.
Missing model configuration or model failures produce errors rather than template replies.
Source-specific expression records take precedence over general assumptions about sequence
composition. No host, induction recipe or yield is inferred from short-peptide predictions.
Literature citations without an exact URL or identifier remain text references; they must
not be presented as independently verified experimental evidence for a new fusion.

Each generated message carries its provider, context key and evidence. `GET /api/chat/status`
reports configuration without disclosing the endpoint or credential. A configured model has
not necessarily been contacted successfully. Changing the page context starts a separate
conversation and invalidates pending answers from the old one. AI requests without a model
return `llm_not_configured`; connection failures return `model_unavailable`; failed output
checks return `invalid_model_output`. No error is disguised as a generated answer.

## Live model sample (2026-10-20)

The local Pages handler was exercised against the configured `MiniMax-M3.1-Flash` service,
using `con_0001`, the `mask-patch` route, `juzi-fhlc` scaffold and `LK_EAAAK` linker. Risk
analysis and a follow-up about missing measurements returned distinct generated answers in
about 11 and 12 seconds. Their route scores and missing-measurement statements matched the
current records. A browser question about expression evidence also returned a generated
answer and the recorded patent link, preserving the source's sequence/construct limitations.

This run found and fixed a false rejection of recorded vector identifiers embedded within
qualified source sentences (`PSC101` and `PPD1121`). Exact identifiers from expression fields
are now recognised individually; bare numbers and invented identifier variants remain
rejected. The original failed completion was accepted by an offline replay after the fix,
and a fresh browser request succeeded. Threshold attribution and unsupported priority
recommendations were also clarified in the prompts after reviewing the sample answers.

These are limited live integration and quality samples, not proof that every future answer
is scientifically correct. The model uses the supplied records and source excerpts; this
chat path does not independently retrieve or re-read external literature on each turn.

## Scientific interpretation

- Missing measurements remain unknown; they are neither zero nor a pass.
- Scores describe the functional peptide rather than the full fusion sequence.
- TemStaPro's stored score averages classifier outputs at six temperature thresholds. It is
  not a melting temperature or a calibrated probability on these short peptides. See the
  [original paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11001493/) and the local
  `iGEM-platform-main/results/plots/temstapro/temstapro_score_definition.md`.
- SoDoPE is an exploratory signal from recombinant protein expression modelling; it cannot
  establish fusion solubility or purification yield.
- The existing composite formula is retained as an exploratory, pool-relative ranking.
  It includes signals whose applicability to short peptides remains unverified and must not
  be read as an activity, safety or experimental-success probability.
- The toxicity cut of 0.38 is a project screening choice, not the predictor's default.

## Verification before release

Run the service tests from `service/`, then the frontend checks from `app/`:

```sh
python -m pytest tests
npm run verify:chat
npm run verify:dev-chat
npm run verify:static
npm run lint
npm run build
```

The chat checks execute the actual Pages handler against local exported assets and a mocked
model. Cases cover route thresholds and composites, scaffold/linker selections, missing
scores, source qualifiers, context isolation, distinct freely written replies and fact
substitution. The development HTTP check calls a local OpenAI-compatible mock server and
verifies that the actual questions and follow-up history reach it. The tests do not spend
an API key or demonstrate the quality of a particular live model.

After refreshing the data export and deploying the checked build, validate one normal
response and one unavailable-model case in the actual deployment. Confirm the per-message
provider, selected context, cited values and sources. A live model configuration remains an
operational prerequisite; no credential is added by this change. Public model usage also
requires deployment-level rate and spending controls.

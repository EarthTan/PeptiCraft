"""Tests for the model-backed generator.

These exist because the failure this feature can produce is not a crash. A model given a
construct's record will answer fluently whether or not the record supports what it says, so the
only defence is that it is never asked for a number and that whatever it returns is labelled.
That is what these check:

    * the fact block carries the record and states nulls as "not assessed", never as 0
    * the instructions forbid the two moves that would make an answer wrong — inventing a figure
      and reading a ranking signal as a probability
    * any failure to reach the model produces the template's answer, labelled as the template's
    * the provider name travels on the response, so the interface can label the output
    * the two copies of the prompt — this module's and the Pages Function's — have not drifted
      apart, which is the one duplication the deployment forced

No test calls a network. The transport is injected, which is what makes the failure paths
testable at all: a real client would have to be made to fail on demand.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from app.models.analysis import MAX_HISTORY_TURNS  # noqa: E402
from app.repositories import constructs as repo  # noqa: E402
from app.repositories import enrichment  # noqa: E402
from app.services import analysis as analysis_service  # noqa: E402
from app.services import constructs as construct_service  # noqa: E402
from app.services.analysis import ModelUnavailable, TemplateGenerator, _verdict_word  # noqa: E402
from app.services.llm import (  # noqa: E402
    HISTORY_TURNS,
    SYSTEM_PROMPT,
    LlmGenerator,
    build_fact_block,
    build_messages,
    chat_completions_endpoint,
)

# The repository root, for the checks that read a file the Python side cannot import: the
# Pages Function restates the prompt and the fact block in TypeScript, and the restatement is
# what has to be compared.
REPO = Path(__file__).resolve().parents[2]
PAGES_FUNCTION = REPO / "app" / "functions" / "api" / "constructs" / "[id]" / "chat.ts"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def detail():
    """One real construct out of the fixture, built through the service like any request."""
    row = repo.get_construct(9001)
    assert row is not None
    enriched = enrichment.scores_for_peptides([row["peptide_id"]])
    return construct_service.build_detail(row, enriched.get(row["peptide_id"], {}), route_id=None)


# ---------------------------------------------------------------------------
# The fact block
# ---------------------------------------------------------------------------

def test_fact_block_carries_every_score(detail):
    text = build_fact_block(detail)
    for key in (
        "antioxidant", "toxicity", "hemolysis", "immunogenicity", "b_cell_epitope",
        "thermal_stability", "solubility", "cpp",
    ):
        assert f"- {key}:" in text, f"{key} missing from the fact block"


def test_fact_block_states_unassessed_as_such_not_as_zero(detail):
    """The single most important property of the block.

    A model handed a JSON `null` reads it as a missing value. A model handed 0 reads it as a
    score of zero, and a construct with no immunogenicity measurement would then be described
    as having an immunogenicity of 0, which is a real claim and a false one.

    The fixture construct happens to have every predictor covered, so the missing value is
    introduced here rather than found: what is under test is how the formatter renders a null,
    and a test that only ran against a complete record would pass even if it rendered 0.

    The change is made to a copy. `detail` is module-scoped — building it reads the database —
    so editing it in place would leave every later test in this file looking at a construct
    whose immunogenicity was never assessed, and the file's outcome would depend on the order
    pytest happened to run in.
    """
    probe = detail.model_copy(deep=True)
    probe.scores.immunogenicity = None
    probe.score_meta["immunogenicity"] = probe.score_meta["immunogenicity"].model_copy(
        update={"assessed": False}
    )
    text = build_fact_block(probe)
    assert "NOT ASSESSED" in text
    assert "- immunogenicity: not assessed (NOT ASSESSED)" in text
    # No bare zero may stand in for a missing measurement.
    assert "- immunogenicity: 0 " not in text
    # And the record the other tests read is untouched.
    assert detail.scores.immunogenicity is not None


def test_fact_block_carries_the_gate_table_with_thresholds(detail):
    text = build_fact_block(detail)
    assert "SAFETY VERDICT" in text
    for gate in detail.safety.gates:
        assert gate.label in text
        assert str(gate.threshold) in text


def test_fact_block_states_which_side_of_the_threshold_fails(detail):
    """MHC-II fails on a low value; everything else fails on a high one.

    A block that said only "threshold 2.0" would let a model read the rank backwards, which
    would invert the one gate whose direction is opposite to the rest.
    """
    text = build_fact_block(detail)
    assert "a value below the threshold fails" in text
    assert "a value above the threshold fails" in text


def test_fact_block_marks_a_ranking_only_score_as_such(detail):
    text = build_fact_block(detail)
    if detail.semantics.value != "ranking_only":
        pytest.skip(
            "the fixture holds no ranking-only construct, so the rendering of one cannot be "
            "checked here; the assignment is what is under test, not this construct"
        )
    assert "NOT a probability" in text


def test_fact_block_reports_the_assembly_state(detail):
    text = build_fact_block(detail)
    assert f"- scaffold binding: {detail.backbone_binding}" in text
    if not detail.assembled_sequence_available:
        assert "not available" in text


def test_fact_block_notes_an_unsigned_direction(detail):
    if detail.status != "WIP":
        pytest.skip(
            "the fixture's first construct is from a signed-off direction, so the wording for "
            "an unsigned one cannot be checked against it"
        )
    assert "has not been signed off" in build_fact_block(detail)


def test_fact_block_marks_a_named_scaffold_as_a_reconstruction(detail):
    """A detail assembled against a reader-named scaffold must not read as a pipeline result."""
    row = repo.get_construct(int(detail.id.split("_")[1]))
    inferred = construct_service.build_detail(
        row, {}, route_id=None, scaffold_id="fixture-silk-s1",
    )
    text = build_fact_block(inferred)
    assert "inferred" in text


# ---------------------------------------------------------------------------
# The instructions
# ---------------------------------------------------------------------------

def test_system_prompt_forbids_inventing_a_number():
    assert "Never produce a number that is not in the fact block" in SYSTEM_PROMPT
    assert "estimate" in SYSTEM_PROMPT


def test_system_prompt_separates_unassessed_from_zero():
    assert "not a zero and not a pass" in SYSTEM_PROMPT


def test_system_prompt_forbids_reading_a_ranking_signal_as_a_probability():
    assert "not probabilities" in SYSTEM_PROMPT


def test_system_prompt_states_the_scores_describe_the_peptide_alone():
    assert "no predictor was run on the fusion protein" in SYSTEM_PROMPT


def test_system_prompt_forbids_softening_a_borderline_result():
    assert "borderline" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# The two copies of the prompt
# ---------------------------------------------------------------------------

def pages_function_source() -> str:
    return PAGES_FUNCTION.read_text(encoding="utf-8")


def test_the_pages_function_exists_where_this_module_says_it_does():
    """A path in a comment is a claim; this is the assertion that keeps it true."""
    assert PAGES_FUNCTION.is_file(), f"expected the model proxy at {PAGES_FUNCTION}"


def test_the_pages_function_carries_the_same_prompt():
    """The one duplication the deployment forced, checked rather than trusted.

    A Worker cannot import a Python module, so the prompt exists twice. The two have to say
    the same thing or the same construct is described differently depending on which path
    answered it, which is a difference no reader could see. Whitespace is normalised because
    the Python copy is wrapped with explicit line continuations and the TypeScript copy is
    not; the words are what has to match.
    """
    body = re.search(r"const SYSTEM_PROMPT = `(.*?)`", pages_function_source(), re.S)
    assert body is not None, "the Pages Function no longer declares SYSTEM_PROMPT"
    assert " ".join(body.group(1).split()) == " ".join(SYSTEM_PROMPT.split())


def test_the_two_fact_blocks_carry_the_same_sections():
    """The block a model reads must not lose a section on one of the two paths.

    The two build it in different languages and cannot share code, so the guard is on what the
    block is made of: the section titles, the nine score keys and the three supplementary ones.
    A section dropped from either side, or a field read by the wrong name, is exactly the drift
    that would otherwise ship — the deployed block would be thinner than the development one,
    or would report a measurement it failed to look up as "not assessed".
    """
    source = pages_function_source()
    python_block = build_fact_block_for_sections()

    for section in (
        "CONSTRUCT",
        "APPLICATION ROUTE AND ITS SCREENING PROFILE",
        "SAFETY VERDICT",
        "SCORES",
        "SUPPLEMENTARY MEASUREMENTS",
        "COMPOSITE UNDER EVERY ROUTE",
        "ASSEMBLY",
    ):
        assert section in python_block, section
        assert section in source, f"the Pages Function's fact block drops {section}"

    for key in (
        "antioxidant", "toxicity", "hemolysis", "immunogenicity", "b_cell_epitope",
        "thermal_stability", "solubility", "cpp", "composite",
        # The supplementary block, which is read by field name on both sides. A name spelled
        # differently on one side does not fail loudly — it renders as "not assessed" — so this
        # is the only thing standing between a typo and a false claim about a real measurement.
        "immunogenicity_ii_pct_rank", "allergenicity", "aggregation_a3v",
    ):
        assert key in python_block, f"the service's fact block drops {key}"
        assert key in source, f"the Pages Function's fact block drops {key}"


def test_the_two_fact_blocks_word_a_verdict_the_same_way():
    """The third duplicated table, which the section check does not reach.

    That check compares the block's section titles and its score keys; the verdict wording is
    neither. It is a mapping from the four verdicts to a clause, written once in `_verdict_word`
    and written again in the Pages Function, so a change to one that is not made to the other
    describes the same construct two ways depending on which path answered — the failure the
    prompt comparison exists to prevent, in a table that was outside it. The gate lines are
    checked here for the same reason, and they carry the one fact a model can invert: which
    side of the threshold fails, which is the reverse for the MHC-II percent rank.
    """
    source = pages_function_source()
    for verdict in ("clear", "vetoed", "borderline", "indeterminate"):
        clause = _verdict_word(verdict)
        assert clause in source, f"the Pages Function words {verdict!r} as something else"
    assert "a value above the threshold fails" in source
    assert "a value below the threshold fails" in source


def build_fact_block_for_sections() -> str:
    """The Python fact block, built from whatever the fixture offers.

    The fixture's own construct is enough for this: the sections are emitted unconditionally,
    so what is being compared is the block's shape rather than its contents.
    """
    row = repo.get_construct(9001)
    assert row is not None
    enriched = enrichment.scores_for_peptides([row["peptide_id"]])
    detail = construct_service.build_detail(row, enriched.get(row["peptide_id"], {}), route_id=None)
    return build_fact_block(detail)


def number_cases() -> list[dict]:
    """The agreed strings for the figures a fact block prints, shared with the deployment.

    One table rather than one on each side. The service writes these numbers with Python's
    `%g` and the Pages Function writes them with its own helper, and a table kept twice would
    drift in exactly the way the table exists to catch. The deployment's half of the comparison
    is `app/verify/static-export-check.mjs`, which runs its `formatNumber` over this same file.
    """
    path = REPO / "app" / "verify" / "number-format-cases.json"
    assert path.is_file(), f"expected the shared number table at {path}"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def test_the_service_writes_every_number_the_shared_table_names():
    """`%g`'s two notations, pinned from the service's side.

    The table holds values on both sides of the notation switch — below 1e-4 and at or above
    1e6 the service writes exponential notation — because that is the only place the two
    languages differ by default, and the previous check, four values chosen from the middle of
    the fixed range, was satisfied by a function that got the switch completely wrong. A value
    moved here without the function moving with it fails in the check script.
    """
    cases = number_cases()
    assert len(cases) >= 15, "the table is the guard; a short one is not one"
    for case in cases:
        assert f"{case['value']:.6g}" == case["expected"], case


def test_the_pages_function_formats_a_fact_block_number_in_one_place():
    """One helper, and every figure goes through it.

    The count matters as much as the pattern: a call site that formatted a number on its own
    would reintroduce the divergence for that one field, silently. The value half of this is
    the check script's, which runs the deployed function over the shared table; what can be
    asserted from here is that there is only one function to run.
    """
    source = pages_function_source()
    assert re.search(r"export function formatNumber\(value: number\)", source), (
        "the Pages Function no longer exports the fact-block number formatter, so the check "
        "script cannot run it against the shared table"
    )
    # Comments are stripped first, so the count is over code — the docstring above the helper
    # explains the rule and must not read as a second call site.
    code = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    assert code.count("toPrecision(6)") == 1, (
        "a fact-block number is formatted somewhere other than the shared helper"
    )


def test_the_pages_function_reads_the_route_a_reader_switched_to():
    """The deployed block has to take the verdict from the route on screen.

    The detail file carries one route's verdict; a reader who switched routes is looking at a
    different one, so the Function reads the per-route table. Without that it would print the
    default route's verdict beside a page showing another.
    """
    source = pages_function_source()
    assert "verdicts" in source and "verdicts.json" in source
    assert re.search(r"verdicts\?\.\[detail\.id\]\?\.\[", source), (
        "the Pages Function no longer reads the per-route verdict table"
    )


def test_the_pages_function_falls_back_to_the_routes_own_id():
    """A request that named no route still has one — the record's.

    The block reports the route it describes, and the verdict beside it is that route's. A
    block that said "no route was named" while quoting a route's verdict would contradict
    itself on the page.
    """
    source = pages_function_source()
    assert re.search(r"safety\.route_id", source), (
        "the Pages Function no longer falls back to the record's own route when the request "
        "named none"
    )


def test_the_pages_function_validates_the_construct_id():
    """The id reaches a file path, so it is a shape and not a string."""
    source = pages_function_source()
    assert re.search(r"con_\\d\+", source), (
        "the Pages Function no longer constrains the construct id before using it as a path"
    )


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "configured, expected",
    [
        ("https://api.example.com", "https://api.example.com/v1/chat/completions"),
        ("https://api.example.com/", "https://api.example.com/v1/chat/completions"),
        ("https://api.example.com/v1", "https://api.example.com/v1/chat/completions"),
        ("https://api.example.com/v1/", "https://api.example.com/v1/chat/completions"),
        (
            "https://api.example.com/v1/chat/completions",
            "https://api.example.com/v1/chat/completions",
        ),
    ],
)
def test_endpoint_expansion(configured, expected):
    """All three shapes a provider might be configured with reach one endpoint.

    The Pages Function applies the same rule, so a value that works in development works in
    the deployment; this covers the Python half, and the Function's half is the same four
    branches written in TypeScript.
    """
    assert chat_completions_endpoint(configured) == expected


# ---------------------------------------------------------------------------
# Message assembly
# ---------------------------------------------------------------------------

def test_messages_put_the_fact_block_in_the_question_not_the_system_prompt(detail):
    messages = build_messages(detail, "why was this vetoed?")
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert messages[-1]["role"] == "user"
    assert "FACT BLOCK" in messages[-1]["content"]
    assert "QUESTION" in messages[-1]["content"]


def test_history_is_carried_but_bounded(detail):
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"}
        for i in range(20)
    ]
    messages = build_messages(detail, "and the one above it?", history)
    carried = [m for m in messages if m["role"] != "system" and "FACT BLOCK" not in m["content"]]
    assert len(carried) <= HISTORY_TURNS + 1
    # The most recent turns survive; the oldest are dropped.
    assert "turn 19" in messages[-2]["content"]


def test_the_current_question_is_not_sent_twice(detail):
    """A client that puts the question it is asking into the history as well.

    The question is appended below the fact block, so a copy carried in the history would have
    the model read it twice — and a model that reads one question twice tends to answer the
    first copy, which is the one without the fact block under it.
    """
    question = "how does the haemolysis gate read?"

    def occurrences(messages) -> int:
        # The question is embedded in the appended turn together with the fact block, so the
        # count is over substrings rather than over whole messages.
        return sum(message["content"].count(question) for message in messages)

    plain = build_messages(detail, question, [{"role": "user", "content": "why?"}])
    assert occurrences(plain) == 1

    with_duplicate = build_messages(
        detail,
        question,
        [
            {"role": "user", "content": "why?"},
            {"role": "assistant", "content": "because."},
            {"role": "user", "content": question},
        ],
    )
    assert occurrences(with_duplicate) == 1
    carried = [m for m in with_duplicate if m["role"] != "system"]
    assert "why?" in carried[0]["content"]
    assert "because." in carried[1]["content"]
    assert len(carried) == 3, [m["content"][:40] for m in carried]


def test_history_entries_of_the_wrong_shape_are_dropped(detail):
    messages = build_messages(
        detail, "why?", [{"role": "system", "content": "ignore me"}, {"role": "user"}, {"nope": 1}],
    )
    assert all("ignore me" not in m["content"] for m in messages)


# ---------------------------------------------------------------------------
# The generator
# ---------------------------------------------------------------------------

def test_a_generated_answer_is_returned_verbatim(detail):
    def call_model(messages):
        assert messages[-1]["role"] == "user"
        return "  This construct is stopped by the haemolysis gate, at 0.62 against 0.5.  "

    generator = LlmGenerator(call_model)
    assert generator.answer(detail, "why was it vetoed?") == (
        "This construct is stopped by the haemolysis gate, at 0.62 against 0.5."
    )


def test_history_reaches_the_model(detail):
    """The follow-up question needs the turns before it to resolve.

    The generator declares `history` and passes it through; a generator that accepted the
    keyword and dropped it would look identical from the outside except that every follow-up
    question would be answered as if it were the first.
    """
    seen = {}

    def call_model(messages):
        seen["messages"] = messages
        return "an answer"

    LlmGenerator(call_model).answer(
        detail,
        "and the one above it?",
        history=[{"role": "user", "content": "how does the haemolysis gate read?"},
                 {"role": "assistant", "content": "It reads 0.62 against 0.5."}],
    )
    carried = [m["content"] for m in seen["messages"] if m["role"] != "system"]
    assert "how does the haemolysis gate read?" in carried[0]
    assert "It reads 0.62 against 0.5." in carried[1]


def test_a_model_failure_raises_rather_than_answering(detail):
    """The generator does not fall back on its own.

    A generator that substituted the template's prose would be labelled with its own name,
    because the label comes from `name` and not from what actually answered. So the failure
    travels to the caller, which is where the text and the label are decided together.
    """
    def call_model(messages):
        raise RuntimeError("connection refused")

    with pytest.raises(ModelUnavailable):
        LlmGenerator(call_model).answer(detail, "is it safe?")


def test_an_empty_completion_raises_rather_than_answering(detail):
    for empty in ("", "   ", None):
        with pytest.raises(ModelUnavailable):
            LlmGenerator(lambda messages: empty).answer(detail, "is it safe?")


def test_the_fallback_answer_is_the_templates_and_is_labelled_as_such(detail, monkeypatch):
    """The two things that must agree — the text and the label — decided in one place."""
    monkeypatch.setattr(analysis_service, "get_generator", lambda: LlmGenerator(
        lambda messages: (_ for _ in ()).throw(RuntimeError("no route to host"))
    ))
    response = analysis_service.chat(detail, "is it safe?")
    assert response.provider == "template"
    assert response.llm_configured is False
    assert response.message.content == TemplateGenerator().answer(detail, "is it safe?")


def test_a_generated_answer_is_labelled_llm(detail, monkeypatch):
    monkeypatch.setattr(
        analysis_service, "get_generator", lambda: LlmGenerator(lambda messages: "an answer")
    )
    response = analysis_service.chat(detail, "is it safe?")
    assert response.provider == "llm"
    assert response.llm_configured is True
    assert response.message.content == "an answer"


def test_a_two_argument_generator_still_works(detail, monkeypatch):
    """The original protocol, kept so a third-party generator does not have to be rewritten."""
    class Legacy:
        name = "legacy"

        def blocks(self, construct):
            return []

        def answer(self, construct, question):
            return "answered without history"

    monkeypatch.setattr(analysis_service, "get_generator", lambda: Legacy())
    response = analysis_service.chat(detail, "is it safe?")
    assert response.message.content == "answered without history"
    assert response.provider == "legacy"
    assert response.llm_configured is False


def test_a_type_error_inside_a_generator_is_not_swallowed(detail, monkeypatch):
    """The signature decides whether history is passed, not a caught TypeError.

    A generator that raises TypeError from a bug in its own body must surface it. Retrying the
    call without the keyword would return prose written past the failing line.
    """
    class Broken:
        name = "broken"

        def blocks(self, construct):
            return []

        def answer(self, construct, question, *, history=None):
            raise TypeError("a real bug, not a signature mismatch")

    monkeypatch.setattr(analysis_service, "get_generator", lambda: Broken())
    with pytest.raises(TypeError):
        analysis_service.chat(detail, "is it safe?")


def test_the_standing_analyses_stay_on_the_template(detail):
    """The six blocks are not questions and must not vary between readers of one construct."""
    generator = LlmGenerator(lambda messages: "a model would have said something else")
    assert generator.blocks(detail) == TemplateGenerator().blocks(detail)


def test_the_generator_names_itself(detail):
    assert LlmGenerator(lambda messages: "x").name == "llm"
    assert TemplateGenerator().name == "template"


def test_a_long_conversation_is_trimmed_rather_than_rejected(client):
    """The interface sends the whole transcript, so a long session must not start failing.

    A reader who has asked more questions than the ceiling is not doing anything wrong, and
    the turns the generator reads are the most recent ones either way. The tail is therefore
    kept and the head dropped, in place of a 422 the reader could not act on.
    """
    turns = [
        {
            "id": f"msg_{index}",
            "role": "user" if index % 2 == 0 else "assistant",
            "content": f"turn {index}",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        for index in range(MAX_HISTORY_TURNS + 40)
    ]
    response = client.post(
        "/api/constructs/con_9001/chat",
        json={
            "construct_id": "con_9001",
            "message": "why is this vetoed?",
            "route_id": None,
            "history": turns,
        },
    )
    assert response.status_code == 200


def test_one_turn_of_history_is_bounded(client):
    """A single turn cannot be arbitrarily large.

    The question is capped at 2,000 characters and an answer at 700 output tokens, so the
    interface cannot reach this; the field is bounded for whatever else calls the endpoint.
    """
    response = client.post(
        "/api/constructs/con_9001/chat",
        json={
            "construct_id": "con_9001",
            "message": "why?",
            "route_id": None,
            "history": [
                {
                    "id": "msg_1",
                    "role": "user",
                    "content": "x" * 5000,
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            ],
        },
    )
    assert response.status_code == 422


def test_a_malformed_model_response_does_not_crash_the_endpoint(client, monkeypatch):
    """The whole chain, with the transport raising at the point a real network would.

    The reader still gets an answer, the answer is the record's own, and the response says
    which generator produced it rather than leaving the reader to guess.
    """
    def call_model(messages):
        raise ValueError("upstream said something unexpected")

    generator = LlmGenerator(call_model)
    monkeypatch.setattr(analysis_service, "get_generator", lambda: generator)

    response = client.post(
        "/api/constructs/con_9001/chat",
        json={"construct_id": "con_9001", "message": "why is this vetoed?", "route_id": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"]["content"]
    assert body["provider"] == "template"
    assert body["llm_configured"] is False
    assert body["message"]["content"] == TemplateGenerator().answer(
        analysis_service_chat_detail(body["construct_id"]), "why is this vetoed?"
    )


def analysis_service_chat_detail(construct_id: str):
    """The same detail the endpoint builds, for comparing its fallback against the template."""
    row = repo.get_construct(int(construct_id.split("_")[1]))
    assert row is not None
    enriched = enrichment.scores_for_peptides([row["peptide_id"]])
    return construct_service.build_detail(row, enriched.get(row["peptide_id"], {}), route_id=None)


# ---------------------------------------------------------------------------
# The registration
# ---------------------------------------------------------------------------

def test_build_llm_generator_returns_none_without_a_model(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "analysis_provider", "template", raising=False)
    assert analysis_service.build_llm_generator() is None


def test_build_llm_generator_returns_none_without_a_key(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "analysis_provider", "llm", raising=False)
    monkeypatch.setattr(settings, "llm_base_url", "https://api.example.com", raising=False)
    monkeypatch.setattr(settings, "llm_api_key", None, raising=False)
    assert analysis_service.build_llm_generator() is None


def test_build_llm_generator_builds_one_when_a_model_is_configured(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "analysis_provider", "llm", raising=False)
    monkeypatch.setattr(settings, "llm_base_url", "https://api.example.com", raising=False)
    monkeypatch.setattr(settings, "llm_api_key", "test-key", raising=False)
    monkeypatch.setattr(settings, "llm_model", "test-model", raising=False)
    generator = analysis_service.build_llm_generator()
    assert generator is not None and generator.name == "llm"


def test_ensure_generator_keeps_the_template_when_no_model_is_configured(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "analysis_provider", "template", raising=False)
    monkeypatch.setattr(analysis_service, "_generator", TemplateGenerator())
    assert analysis_service.ensure_generator().name == "template"


def test_llm_configured_is_false_without_a_key(monkeypatch):
    """Configuredness is a settings question and stays one.

    It is not the same question as "did this answer come from a model" — a configured model
    can still fail on a turn, and `provider` is what reports that. This covers the settings
    probe that decides whether to build a generator at all.
    """
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_base_url", None, raising=False)
    assert analysis_service.llm_configured() is False


def test_a_transport_is_injected_rather_than_imported(monkeypatch):
    """The transport is a deployment concern, so the module must not import one at build time.

    A generator that reached for `urllib` or `httpx` on import would make the static exporter,
    which imports the service, depend on a model being configured.
    """
    import app.services.llm as llm_module

    source = Path(llm_module.__file__).read_text()
    assert "import urllib" not in source
    assert "import httpx" not in source
    assert "import requests" not in source
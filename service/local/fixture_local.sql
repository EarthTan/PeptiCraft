-- fixture_local.sql
--
-- The local SQLite stand-in for the remote Postgres instance, used when that instance is
-- unreachable and IGEM_DB_BACKEND permits a fallback. See app/sqlite_backend.py.
--
-- This is FIXTURE DATA. It exists to exercise code paths offline, not to stand in for
-- pipeline output, and nothing here should be read as a result. Four constructs are seeded:
--
--   con_9001  a construct whose stored scaffold binding is the same placeholder the real
--             496 rows carry (backbone_proteins id 1, sequence `PLACEHOLDER_4RepCT`,
--             length 0). Its fused sequence must NOT be emitted.
--   con_9002  a construct whose stored binding points at a backbone row that carries a real
--             amino-acid sequence. This is the case the service could not previously
--             represent at all: a real, stored binding that assembles into a full sequence.
--   con_9003  an antibacterial candidate on the top channel. Present so that a build can
--             cover two directions at once rather than one, and so that the build's ranking
--             has rows from more than one direction to merge. It also records a different
--             linker from the other three, so that a build naming no linker can be shown to
--             follow each row's own record.
--   con_9004  an antibacterial row on the bottom channel — the negative-control arm. Present
--             so that the build's top-channel filter is observable: a build over
--             `antibacterial` must return con_9003 alone, while the unfiltered construct
--             list returns both.
--
-- The first two exist so both branches of the binding logic are reachable in one run. Their
-- scores are chosen to land one construct clear of every veto gate and the other past two of
-- them (haemolysis 0.71 > 0.55, MHC-I 0.44 > 0.35 under the wound-dressing route).
--
-- The two antioxidant constructs sit in the same direction and the same channel so that the
-- composite's pool statistics have two observations to take a spread over; a single-row pool
-- has no measurable variance and every component weight would collapse to zero. That is why
-- antibacterial holds one top row rather than two: its composite is expected to be absent,
-- and the build's null-composite ordering is exercised for free. The bottom rows are not in
-- the pool at all — `scoring` reads `channel="top"` — so con_9004 changes no statistic.
--
-- Rebuild: delete local/pepticraft_local.sqlite3 and start the service, or run
--   python scripts/build_local_db.py --force

PRAGMA foreign_keys = OFF;

DROP VIEW  IF EXISTS v_peptide_enrichment_coverage;
DROP TABLE IF EXISTS peptide_enrichment;
DROP TABLE IF EXISTS constructs;
DROP TABLE IF EXISTS peptides;
DROP TABLE IF EXISTS backbone_proteins;
DROP TABLE IF EXISTS linkers;
DROP TABLE IF EXISTS linker_library;
DROP TABLE IF EXISTS scaffold_library_sequences;
DROP TABLE IF EXISTS scaffold_library;

-- ---------------------------------------------------------------------------
-- Peptides
-- ---------------------------------------------------------------------------
CREATE TABLE peptides (
    id                INTEGER PRIMARY KEY,
    sequence          TEXT    NOT NULL,
    length            INTEGER NOT NULL,
    source            TEXT,
    source_version    TEXT,
    source_accession  TEXT,
    seq_md5           TEXT
);

INSERT INTO peptides (id, sequence, length, source, source_version, source_accession, seq_md5) VALUES
  (7001, 'WYPLGPK', 7, 'fixture',      '2026-07-17', 'FIX_0001', '6d835a0d05314017cbed4c3725a2b1ec'),
  (7002, 'FHLSTQNR', 8, 'fixture',     '2026-07-17', 'FIX_0002', '2e79a92a19d842c36703b0ffee42022a');

-- ---------------------------------------------------------------------------
-- Backbone proteins — the table `constructs.backbone_id` resolves against.
--
-- Row 1 mirrors the real placeholder exactly: a marker string in the sequence column and
-- length 0. Row 2 carries a collagen-mimetic (GPP)14 repeat, which is what makes con_9002
-- the verified-binding case. `is_placeholder_backbone` keys off the `PLACEHOLDER` marker and
-- off an empty sequence, so row 2 is treated as real and row 1 is not.
-- ---------------------------------------------------------------------------
CREATE TABLE backbone_proteins (
    id        INTEGER PRIMARY KEY,
    name      TEXT,
    sequence  TEXT,
    length    INTEGER
);

INSERT INTO backbone_proteins (id, name, sequence, length) VALUES
  (1, 'PLACEHOLDER_4RepCT', 'PLACEHOLDER_4RepCT', 0),
  (2, 'Fixture-C1', 'GPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPP', 42);

-- ---------------------------------------------------------------------------
-- Linkers — the six-row sample table a construct's linker_id resolves against.
-- ---------------------------------------------------------------------------
CREATE TABLE linkers (
    id              INTEGER PRIMARY KEY,
    name            TEXT,
    sequence        TEXT,
    length          INTEGER,
    flexible_count  INTEGER,
    rigid_count     INTEGER,
    rigidity        REAL,
    description     TEXT
);

INSERT INTO linkers (id, name, sequence, length, flexible_count, rigid_count, rigidity, description) VALUES
  (1, '(GGGGS)', 'GGGGS', 5, 1, 0, 0.0, 'Glycine-serine sample linker.'),
  (2, '(EAAAK)', 'EAAAK', 5, 0, 1, 1.0, 'Helix-forming sample linker.');

-- ---------------------------------------------------------------------------
-- Curated linker library (the fifteen-entry table; three are seeded here).
--
-- The third entry exists so that a linker chosen at request time is distinguishable from
-- the one a row records, and distinguishable by *length* rather than by letters: the sample
-- table's two entries are both 5 residues, so an assertion on a fused length could not tell
-- a chosen linker from a stored one. This one is 15.
-- ---------------------------------------------------------------------------
CREATE TABLE linker_library (
    id               TEXT PRIMARY KEY,
    name             TEXT,
    sequence         TEXT,
    length           INTEGER,
    rigidity         TEXT,
    rigidity_index   REAL,
    flexible_count   INTEGER,
    rigid_count      INTEGER,
    unit_composition TEXT,
    description      TEXT,
    reference        TEXT,
    priority_reason  TEXT
);

INSERT INTO linker_library (id, name, sequence, length, rigidity, rigidity_index, flexible_count, rigid_count, unit_composition, description, reference, priority_reason) VALUES
  ('LK_GGGGS', '(GGGGS)1', 'GGGGS', 5, 'Flexible', 0.0, 1, 0,
   '[{"unit": "GGGGS", "count": 1, "label": "flexible"}]',
   'Fixture entry. Flexible glycine-serine linker.', 'Fixture reference', 'Fixture entry'),
  ('LK_EAAAK', '(EAAAK)1', 'EAAAK', 5, 'Rigid', 1.0, 0, 1,
   '[{"unit": "EAAAK", "count": 1, "label": "rigid"}]',
   'Fixture entry. Helix-forming rigid linker.', 'Fixture reference', 'Fixture entry'),
  ('LK_GS3', '(GGGGS)3', 'GGGGSGGGGSGGGGS', 15, 'Mostly Flexible', 0.25, 3, 0,
   '[{"unit": "GGGGS", "count": 3, "label": "flexible"}]',
   'Fixture entry. Three glycine-serine repeats, the length the curated library mostly sits at.',
   'Fixture reference', 'Fixture entry');

-- ---------------------------------------------------------------------------
-- Scaffold library — cluster grain, with the application tags that link a scaffold to an
-- application route. `route_ids` and `application_tags` are stored as JSON arrays, the
-- SQLite counterpart of the Postgres `text[]` columns.
-- ---------------------------------------------------------------------------
CREATE TABLE scaffold_library (
    id                        TEXT PRIMARY KEY,
    name                      TEXT NOT NULL,
    short_name                TEXT NOT NULL,
    category                  TEXT,
    construct_cn              TEXT,
    applicant                 TEXT NOT NULL,
    patent_family             TEXT,
    species                   TEXT,
    length_aa                 INTEGER,
    aa_sequence               TEXT,
    sequence_count            INTEGER NOT NULL DEFAULT 0,
    application_tags          TEXT NOT NULL DEFAULT '[]',
    route_ids                 TEXT NOT NULL DEFAULT '[]',
    material_forms            TEXT NOT NULL DEFAULT '[]',
    max_evidence              TEXT,
    product_use               TEXT,
    potential_uses            TEXT,
    evidence_limits           TEXT,
    registrations             TEXT NOT NULL DEFAULT '[]',
    registration_note         TEXT,
    description               TEXT,
    patent_source_url         TEXT,
    regulatory_evidence_url   TEXT,
    source_version            TEXT
);

-- `length_aa` on both the cluster and its variant equals the residue count of the sequence
-- beside it. A fixture whose declared length disagrees with its own sequence is a trap: every
-- arithmetic assertion written against it fails for a reason that looks like a code defect.
INSERT INTO scaffold_library (
    id, name, short_name, category, construct_cn, applicant, patent_family, species,
    length_aa, aa_sequence, sequence_count, application_tags, route_ids, material_forms,
    max_evidence, product_use, potential_uses, evidence_limits, registrations,
    registration_note, description, patent_source_url, regulatory_evidence_url, source_version
) VALUES
  ('fixture-collagen-c1', 'Fixture recombinant collagen C1', 'Fixture C1', 'recombinant-collagen',
   'Fixture construct', 'Fixture Applicant', 'Fixture patent family',
   'Homo sapiens collagen fragment', 42, 'GPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPP', 1,
   '["Wound dressing", "Injectable filler"]', '["wound-dressing", "injectable-filler"]',
   '["injectable-gel", "solution"]', 'E3',
   'Fixture entry used as a wound-care gel.', 'Fixture entry for a dermal filler.',
   'Fixture entry, not a real evidence record.', '[]', NULL,
   'Fixture scaffold used to exercise the scaffold endpoints offline.',
   NULL, NULL, '2026-09-06'),
  ('fixture-silk-s1', 'Fixture silkworm silk S1', 'Fixture S1', 'silkworm-silk',
   'Fixture construct', 'Fixture Applicant', 'Fixture patent family',
   'Bombyx mori fibroin fragment', 47,
   'GAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAG', 1,
   '["Mask patch", "Topical appliance"]', '["mask-patch", "topical-film"]',
   '["film", "sheet"]', 'E2',
   'Fixture entry used as a topical film.', 'Fixture entry for a mask patch.',
   'Fixture entry, not a real evidence record.', '[]', NULL,
   'Fixture scaffold used to exercise the scaffold endpoints offline.',
   NULL, NULL, '2026-09-06');

CREATE TABLE scaffold_library_sequences (
    sequence_id             TEXT PRIMARY KEY,
    scaffold_id             TEXT NOT NULL,
    fasta_filename          TEXT,
    length_aa               INTEGER NOT NULL,
    aa_sequence             TEXT NOT NULL,
    sha256                  TEXT,
    product_use             TEXT,
    potential_uses          TEXT,
    regulatory_status       TEXT,
    safety_testing_summary  TEXT,
    evidence_level          TEXT,
    experiment_group        TEXT,
    experiment_level        TEXT,
    specific_experiments    TEXT,
    principal_result        TEXT,
    result_location         TEXT,
    evidence_limitations    TEXT,
    patent_source_url       TEXT,
    regulatory_evidence_url TEXT,
    confidence_limitations  TEXT,
    source_version          TEXT
);

INSERT INTO scaffold_library_sequences (
    sequence_id, scaffold_id, fasta_filename, length_aa, aa_sequence, sha256,
    product_use, potential_uses, regulatory_status, evidence_level,
    experiment_group, experiment_level, specific_experiments, principal_result,
    result_location, evidence_limitations, source_version
) VALUES
  ('FIX-SEQ-0001', 'fixture-collagen-c1', 'fixture_c1.fasta', 42,
   'GPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPP',
   '0000000000000000000000000000000000000000000000000000000000000001',
   'Fixture wound-care gel', 'Fixture dermal filler', 'Fixture status', 'E3',
   'Fixture group', 'Fixture level', 'Fixture experiment', 'Fixture result',
   'Fixture location', 'Fixture limitation', '2026-09-06'),
  ('FIX-SEQ-0002', 'fixture-silk-s1', 'fixture_s1.fasta', 47,
   'GAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAG',
   '0000000000000000000000000000000000000000000000000000000000000002',
   'Fixture topical film', 'Fixture mask patch', 'Fixture status', 'E2',
   'Fixture group', 'Fixture level', 'Fixture experiment', 'Fixture result',
   'Fixture location', 'Fixture limitation', '2026-09-06');

-- ---------------------------------------------------------------------------
-- Constructs — four rows: one per binding branch, and a second direction with a control.
-- ---------------------------------------------------------------------------
CREATE TABLE constructs (
    id               INTEGER PRIMARY KEY,
    direction        TEXT,
    scenario         TEXT,
    backbone_id      INTEGER,
    linker_id        INTEGER,
    peptide_id       INTEGER,
    full_sequence    TEXT,
    channel          TEXT,
    status           TEXT,
    rank             INTEGER,
    scores           TEXT,
    delivery_scores  TEXT,
    assessed_hemo    INTEGER NOT NULL DEFAULT 0,
    assessed_mhci    INTEGER NOT NULL DEFAULT 0,
    assessed_mhcii   INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT
);

-- con_9001: placeholder binding. `full_sequence` holds the same vertical-bar text the real
-- rows hold, which the service must NOT serve as a sequence.
INSERT INTO constructs (
    id, direction, scenario, backbone_id, linker_id, peptide_id, full_sequence,
    channel, status, rank, scores, delivery_scores,
    assessed_hemo, assessed_mhci, assessed_mhcii, created_at
) VALUES (
    9001, 'antioxidant', 'wound_care', 1, 1, 7001, '4RepCT|GGGGS|WYPLGPK',
    'top', 'passed', 1,
    '{"aggrescan_a3v": -0.19, "netmhcipan_min_rank_pct": 6.5, "func_score_meaning": "probability"}',
    '{}', 1, 1, 1, '2026-09-06T00:00:00Z'
);

-- con_9002: verified binding. The stored fused sequence is the real concatenation of
-- Fixture-C1 + GGGGS + FHLSTQNR.
INSERT INTO constructs (
    id, direction, scenario, backbone_id, linker_id, peptide_id, full_sequence,
    channel, status, rank, scores, delivery_scores,
    assessed_hemo, assessed_mhci, assessed_mhcii, created_at
) VALUES (
    9002, 'antioxidant', 'wound_care', 2, 1, 7002,
    'GPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGGGGSFHLSTQNR',
    'top', 'passed', 2,
    '{"aggrescan_a3v": 0.08, "netmhcipan_min_rank_pct": 1.4, "func_score_meaning": "probability"}',
    '{}', 1, 1, 1, '2026-09-06T00:00:00Z'
);

-- con_9003 / con_9004: the second direction, and the negative-control arm.
--
-- Both point at the placeholder backbone, so neither can emit a fused sequence on its own
-- binding — which is what makes the build's behaviour visible: naming a scaffold for a build
-- must produce a sequence for every row, and naming none must produce none.
--
-- con_9003 records the sample table's second linker rather than its first, which no other
-- row does. That is what makes "a build that names no linker shows each row's own" an
-- assertion rather than an argument: the two antioxidant rows carry `GGGGS` and this one
-- carries `EAAAK`, so the two cases are distinguishable in one response.
--
-- con_9004 reuses peptide 7002, whose scores are the vetoed ones, because a control arm that
-- passed everything would not be a control arm.
INSERT INTO constructs (
    id, direction, scenario, backbone_id, linker_id, peptide_id, full_sequence,
    channel, status, rank, scores, delivery_scores,
    assessed_hemo, assessed_mhci, assessed_mhcii, created_at
) VALUES (
    9003, 'antibacterial', 'wound_careing', 1, 2, 7001, '4RepCT|EAAAK|WYPLGPK',
    'top', 'WIP', 1,
    '{"aggrescan_a3v": -0.11, "netmhcipan_min_rank_pct": 5.1, "func_score_meaning": "probability"}',
    '{}', 1, 1, 1, '2026-09-06T00:00:00Z'
), (
    9004, 'antibacterial', 'wound_careing', 1, 1, 7002, '4RepCT|GGGGS|FHLSTQNR',
    'bottom', 'failed_safety', 1,
    '{"aggrescan_a3v": 0.12, "netmhcipan_min_rank_pct": 1.4, "func_score_meaning": "probability"}',
    '{}', 1, 1, 1, '2026-09-06T00:00:00Z'
);

-- ---------------------------------------------------------------------------
-- Peptide enrichment — the per-tool score table, in its Postgres shape.
-- ---------------------------------------------------------------------------
CREATE TABLE peptide_enrichment (
    peptide_id  INTEGER NOT NULL,
    tool        TEXT    NOT NULL,
    score       REAL,
    label       TEXT,
    details     TEXT,
    scored_at   TEXT,
    PRIMARY KEY (peptide_id, tool)
);

-- con_9001's peptide: clears every veto gate (toxicity 0.18 <= 0.38, haemolysis 0.31 <= 0.55,
-- MHC-I 0.20 <= 0.35) and sits clear of the borderline band on each.
INSERT INTO peptide_enrichment (peptide_id, tool, score, label, details, scored_at) VALUES
  (7001, 'toxinpred3',           0.18, 'Non-toxic',   '{"model": "ToxinPred3", "threshold": 0.38}', '2026-07-18'),
  (7001, 'hemopi2',              0.31, 'Non-hemolytic', '{"model": "HemoPI2", "threshold": 0.55}', '2026-07-18'),
  (7001, 'mhcflurry',            0.20, 'Weak binder', '{"model": "MHCflurry 2.0"}', '2026-07-18'),
  (7001, 'bepipred3',            0.09, 'Low epitope', '{"model": "BepiPred-3.0", "threshold": 0.1512}', '2026-07-18'),
  (7001, 'sodope',               0.61, 'Soluble',     '{"model": "SoDoPE"}', '2026-07-18'),
  (7001, 'temstapro',            0.55, 'Mesophile',   '{"model": "TemStaPro", "band": "mesophile"}', '2026-07-18'),
  (7001, 'plm4cpps',             0.42, 'CPP',         '{"model": "pLM4CPPs"}', '2026-07-18'),
  (7001, 'algpred2',             0.12, 'Non-allergen','{"model": "AlgPred2"}', '2026-07-18'),
  (7001, 'anoxpepred-frs',       0.78, 'FRS',         '{"model": "AnOxPePred", "head": "frs", "threshold": 0.5}', '2026-07-18'),
  (7001, 'anoxpepred-chelating', 0.44, 'Chelating',   '{"model": "AnOxPePred", "head": "chelating"}', '2026-07-18'),
  (7001, 'aopxsvm',              1.0,  'Class 1',     '{"model": "AOPxSVM", "prob": 0.83}', '2026-07-18'),
  (7001, 'amp-esm',              0.21, 'AMP',         '{"model": "AMPlify v0.1.0"}', '2026-07-18'),
  (7001, 'imfp_lg_AMP',          0.33, 'AMP',         '{"model": "iMFP-LG", "channel": "AMP"}', '2026-07-18'),
  (7001, 'imfp_lg_AIP',          0.29, 'AIP',         '{"model": "iMFP-LG", "channel": "AIP"}', '2026-07-18'),
  (7001, 'tipred',               0.41, 'TIP',         '{"model": "TIPred", "threshold": 0.5}', '2026-07-18');

-- con_9002's peptide: past two veto gates (haemolysis 0.71 > 0.55, MHC-I 0.44 > 0.35) and a
-- strong MHC-II binder (percent rank 1.4, carried in constructs.scores).
INSERT INTO peptide_enrichment (peptide_id, tool, score, label, details, scored_at) VALUES
  (7002, 'toxinpred3',           0.22, 'Non-toxic',   '{"model": "ToxinPred3", "threshold": 0.38}', '2026-07-18'),
  (7002, 'hemopi2',              0.71, 'Hemolytic',   '{"model": "HemoPI2", "threshold": 0.55}', '2026-07-18'),
  (7002, 'mhcflurry',            0.44, 'Strong binder','{"model": "MHCflurry 2.0"}', '2026-07-18'),
  (7002, 'bepipred3',            0.21, 'Epitope',     '{"model": "BepiPred-3.0", "threshold": 0.1512}', '2026-07-18'),
  (7002, 'sodope',               0.38, 'Soluble',     '{"model": "SoDoPE"}', '2026-07-18'),
  (7002, 'temstapro',            0.71, 'Thermophile', '{"model": "TemStaPro", "band": "thermophile"}', '2026-07-18'),
  (7002, 'plm4cpps',             0.73, 'CPP',         '{"model": "pLM4CPPs"}', '2026-07-18'),
  (7002, 'algpred2',             0.05, 'Non-allergen','{"model": "AlgPred2"}', '2026-07-18'),
  (7002, 'anoxpepred-frs',       0.66, 'FRS',         '{"model": "AnOxPePred", "head": "frs", "threshold": 0.5}', '2026-07-18'),
  (7002, 'anoxpepred-chelating', 0.30, 'Chelating',   '{"model": "AnOxPePred", "head": "chelating"}', '2026-07-18'),
  (7002, 'aopxsvm',              1.0,  'Class 1',     '{"model": "AOPxSVM", "prob": 0.77}', '2026-07-18'),
  (7002, 'amp-esm',              0.55, 'AMP',         '{"model": "AMPlify v0.1.0"}', '2026-07-18'),
  (7002, 'imfp_lg_AMP',          0.61, 'AMP',         '{"model": "iMFP-LG", "channel": "AMP"}', '2026-07-18'),
  (7002, 'imfp_lg_AIP',          0.25, 'AIP',         '{"model": "iMFP-LG", "channel": "AIP"}', '2026-07-18'),
  (7002, 'tipred',               0.38, 'TIP',         '{"model": "TIPred", "threshold": 0.5}', '2026-07-18');

-- The coverage view the reference-data endpoints read. In Postgres this is a real view over
-- `peptide_enrichment`; the eligible count is the full library size the predictors cover.
CREATE VIEW v_peptide_enrichment_coverage AS
SELECT tool,
       count(*)                              AS done_count,
       20248885                              AS eligible_count,
       round(100.0 * count(*) / 20248885, 4) AS coverage_pct
  FROM peptide_enrichment
 GROUP BY tool;

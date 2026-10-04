-- 20_create_scaffold_library.sql
--
-- 目的：把 data/scaffold_database_2026-09-06/scaffold_sequence_database.tsv 这份团队整理
--       的骨架主表落进数据库，让后端服务能按骨架维度供数。
--
-- 为什么需要新表：库里已有的 scaffold_patent_records(27 行) / scaffold_groups(11 行) /
--   scaffold_experiments(12 行) 是「序列记录」粒度，其中 16 行有 FASTA、11 行无序列；
--   而前端按「蛋白簇」粒度工作（一个簇一行，簇内挂多个专利序列变体）。更关键的是，
--   连接骨架与应用路径的五个应用标签列（Topical appliance / Mask patch / Hair care /
--   Wound dressing / Injectable filler）在既有三张表里都没有，只有这份 TSV 有。
--   没有这五列就无法复现 routes.ts 的骨架收窄逻辑。
--
-- 粒度：scaffold_library 一簇一行（8 行），scaffold_library_sequences 一序列一行（16 行）。
--
-- 幂等：CREATE TABLE IF NOT EXISTS + 导入脚本用 ON CONFLICT DO UPDATE，可重复执行。
--
-- 用法：
--   psql "$IGEM_PG_DSN" -f service/sql/20_create_scaffold_library.sql
-- 或直接跑 service/scripts/migrate.py

BEGIN;

-- ---------------------------------------------------------------------------
-- 蛋白簇维度表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scaffold_library (
    id                      TEXT PRIMARY KEY,          -- slug，如 jinbo-hc8-hc16
    name                    TEXT NOT NULL,             -- 英文完整名
    short_name              TEXT NOT NULL,             -- 卡片与列表用短名
    category                TEXT                       -- spider-silk / silkworm-silk / recombinant-collagen
        CHECK (category IS NULL OR category IN ('spider-silk','silkworm-silk','recombinant-collagen')),
    construct_cn            TEXT,                      -- 源表「蛋白/构建体」原文，保留可追溯
    applicant               TEXT NOT NULL,             -- 申请人/权利人
    patent_family           TEXT,                      -- 专利/家族
    species                 TEXT,                      -- 来源物种或序列学描述
    length_aa               INTEGER,                   -- 代表序列长度（簇内最长）
    aa_sequence             TEXT,                      -- 代表序列
    sequence_count          INTEGER NOT NULL DEFAULT 0,

    -- 连接骨架与应用路径的关键字段。application_tags 是源表列的原始英文名，
    -- route_ids 是映射后的应用路径 id，后者是前端真正消费的。
    application_tags        TEXT[] NOT NULL DEFAULT '{}',
    route_ids               TEXT[] NOT NULL DEFAULT '{}',

    -- material_forms 不是数据集的列，是从「产品/用途」「潜在应用」「关键结果」
    -- 三段散文里人工提取的，仍待团队最终确认。
    material_forms          TEXT[] NOT NULL DEFAULT '{}',

    max_evidence            TEXT
        CHECK (max_evidence IS NULL OR max_evidence IN ('E1','E2','E3','E4','E5')),

    product_use             TEXT,
    potential_uses          TEXT,
    evidence_limits         TEXT,
    registrations           TEXT[] NOT NULL DEFAULT '{}',
    registration_note       TEXT,
    description             TEXT,

    patent_source_url       TEXT,
    regulatory_evidence_url TEXT,

    source_table            TEXT NOT NULL DEFAULT 'scaffold_sequence_database.tsv',
    source_version          DATE NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS scaffold_library_category_idx  ON scaffold_library (category);
CREATE INDEX IF NOT EXISTS scaffold_library_evidence_idx  ON scaffold_library (max_evidence);
CREATE INDEX IF NOT EXISTS scaffold_library_applicant_idx ON scaffold_library (applicant);
-- GIN 让 `WHERE route_ids @> ARRAY['wound-dressing']` 走索引；只有 8 行时无所谓，
-- 但按路径筛选是这个表最主要的查询形状，索引保持在位成本极低。
CREATE INDEX IF NOT EXISTS scaffold_library_routes_idx    ON scaffold_library USING GIN (route_ids);

-- ---------------------------------------------------------------------------
-- 专利序列变体维度表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scaffold_library_sequences (
    sequence_id             TEXT PRIMARY KEY,          -- 源表「序列记录ID」
    scaffold_id             TEXT NOT NULL
        REFERENCES scaffold_library (id) ON DELETE CASCADE,

    fasta_filename          TEXT,
    length_aa               INTEGER NOT NULL,
    aa_sequence             TEXT NOT NULL,
    sha256                  CHAR(64),                  -- 源表「序列SHA256」，用于比对版本

    product_use             TEXT,
    potential_uses          TEXT,
    regulatory_status       TEXT,                      -- 市场批号/监管状态（核查至 2026-08-05）
    safety_testing_summary  TEXT,                      -- 安全性与功能性检验概述
    evidence_level          TEXT
        CHECK (evidence_level IS NULL OR evidence_level IN ('E1','E2','E3','E4','E5')),

    experiment_group        TEXT,
    experiment_level        TEXT,
    specific_experiments    TEXT,
    principal_result        TEXT,
    result_location         TEXT,
    evidence_limitations    TEXT,

    patent_source_url       TEXT,
    regulatory_evidence_url TEXT,
    confidence_limitations  TEXT,

    source_version          DATE NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS scaffold_lib_seq_scaffold_idx ON scaffold_library_sequences (scaffold_id);
CREATE INDEX IF NOT EXISTS scaffold_lib_seq_evidence_idx ON scaffold_library_sequences (evidence_level);

COMMIT;

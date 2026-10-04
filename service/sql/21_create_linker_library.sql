-- 21_create_linker_library.sql
--
-- 目的：把前端 linkers.ts 里那 15 条带文献出处的 linker 落进数据库，让后端按 linker 维度供数。
--
-- 为什么另建表而不改既有 linkers 表：
--   12_create_constructs.sql 建的 linkers 表只有 6 行（GGGGS 与 EAAAK 各三个长度），
--   建表脚本自己写明「这里只示例插入最终拼接构造时会用到的几个；完整 32 库由 linker_gen.py 生成」——
--   而 linker_gen.py 在仓库里不存在，完整库从未生成。
--   constructs.linker_id 现在指向这 6 行（496 条全部指向 id=1 即 GGGGS），
--   直接改写该表内容会让既有外键指向的语义发生变化。
--   因此保留 linkers 表原样不动，另建 linker_library 承载 15 条完整条目。
--
-- 两张表的关系由 LinkerView.source_table 字段标注（`linkers` 或 `linker_library`），
-- 等管线按真实场景重新装配 construct 之后再决定是否合并。
--
-- 幂等：CREATE TABLE IF NOT EXISTS + 导入脚本 ON CONFLICT DO UPDATE。
--
-- 用法：
--   psql "$IGEM_PG_DSN" -f service/sql/21_create_linker_library.sql

BEGIN;

CREATE TABLE IF NOT EXISTS linker_library (
    id                  TEXT PRIMARY KEY,              -- LK_<短码>，如 LK_GGGGS
    name                TEXT NOT NULL,                 -- 人类可读名，如 (GGGGS)₂
    sequence            TEXT NOT NULL,
    length              INTEGER NOT NULL CHECK (length > 0),

    -- 五档呈现分级：Flexible / Mostly Flexible / Balanced / Mostly Rigid / Rigid。
    -- 这是展示层约定，不是实测物性；底层的 rigidity 数值是 0.0（全柔性）/ 1.0（全刚性）
    -- 两值约定，见 LinkerDetail.rigidity_index 的说明。
    rigidity            TEXT
        CHECK (rigidity IS NULL OR rigidity IN
               ('Flexible','Mostly Flexible','Balanced','Mostly Rigid','Rigid')),

    flexible_count      INTEGER,                       -- 序列里 GGGGS 单元的个数
    rigid_count         INTEGER,                       -- 序列里 EAAAK 单元的个数
    rigidity_index      REAL,                          -- 0.0 全柔性 / 1.0 全刚性

    -- 单元构成，用于界面上展开解释；结构 [{unit, count, label}, ...]
    unit_composition    JSONB NOT NULL DEFAULT '[]'::jsonb,

    description         TEXT,
    reference           TEXT,                          -- 文献出处
    priority_reason     TEXT,

    source_table        TEXT NOT NULL DEFAULT 'linker_library',
    source_version      DATE NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT linker_library_seq_uniq UNIQUE (sequence)
);

CREATE INDEX IF NOT EXISTS linker_library_length_idx   ON linker_library (length);
CREATE INDEX IF NOT EXISTS linker_library_rigidity_idx ON linker_library (rigidity);

COMMIT;

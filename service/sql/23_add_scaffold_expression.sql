-- 23_add_scaffold_expression.sql
--
-- 目的：给骨架库补上「表达体系推荐」五列。源表 scaffold_sequence_database.tsv 由 30 列
--       扩到 35 列，新增的正是这五列，且 16 条序列记录全部有值：
--
--         31 推荐表达系统（依据来源）      -> expression_system
--         32 来源记载的表达载体/质粒        -> expression_vector_recorded
--         33 推荐表达载体/质粒              -> expression_vector_recommended
--         34 推荐依据与适用范围             -> expression_rationale
--         35 表达系统/载体来源URL           -> expression_source_url
--
-- 两处落库，粒度不同：
--   * scaffold_library_sequences —— 每条序列记录一套，值的原文照录。
--   * scaffold_library          —— 簇这一行存簇内**代表序列**（最长，也是拼装时实际使用
--                                  的那条）的一套，并用 expression_sequence_id 记明出自
--                                  哪条记录。这样构造结果页拿到骨架摘要就能直接给出推荐，
--                                  不必再拉整份序列表。
--
-- 措辞不重写：源表里有「宿主 DE3 状态需确认」「无明确推荐」「同家族公开路线」这类限定，
-- 它们本身就是判断依据，翻译或压缩都会丢掉限定范围。
--
-- 幂等：ADD COLUMN IF NOT EXISTS，可重复执行。
--
-- 用法：
--   psql "$IGEM_PG_DSN" -f service/sql/23_add_scaffold_expression.sql
-- 或直接跑 service/scripts/migrate.py

BEGIN;

ALTER TABLE scaffold_library_sequences
    ADD COLUMN IF NOT EXISTS expression_system             TEXT,
    ADD COLUMN IF NOT EXISTS expression_vector_recorded    TEXT,
    ADD COLUMN IF NOT EXISTS expression_vector_recommended TEXT,
    ADD COLUMN IF NOT EXISTS expression_rationale          TEXT,
    ADD COLUMN IF NOT EXISTS expression_source_url         TEXT;

ALTER TABLE scaffold_library
    ADD COLUMN IF NOT EXISTS expression_system             TEXT,
    ADD COLUMN IF NOT EXISTS expression_vector_recorded    TEXT,
    ADD COLUMN IF NOT EXISTS expression_vector_recommended TEXT,
    ADD COLUMN IF NOT EXISTS expression_rationale          TEXT,
    ADD COLUMN IF NOT EXISTS expression_source_url         TEXT,
    ADD COLUMN IF NOT EXISTS expression_sequence_id        TEXT;

COMMENT ON COLUMN scaffold_library_sequences.expression_system IS
    '源表「推荐表达系统（依据来源）」；宿主与菌株，含来源限定语。';
COMMENT ON COLUMN scaffold_library_sequences.expression_vector_recorded IS
    '源表「来源记载的表达载体/质粒」：专利或文献实际记载的载体。';
COMMENT ON COLUMN scaffold_library_sequences.expression_vector_recommended IS
    '源表「推荐表达载体/质粒」：可执行的推荐；「无明确推荐」也是结论。';
COMMENT ON COLUMN scaffold_library_sequences.expression_rationale IS
    '源表「推荐依据与适用范围」：为什么这样推荐，以及这条推荐能覆盖到哪里。';
COMMENT ON COLUMN scaffold_library.expression_sequence_id IS
    '簇行上的表达推荐取自哪条序列记录：簇内最长序列，即拼装时使用的那条。';

COMMIT;

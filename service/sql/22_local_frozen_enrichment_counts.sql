-- ============================================================================
--  本机子集库的全库聚合冻结表
-- ----------------------------------------------------------------------------
--  背景
--      服务里有两个数字不是从某张表读一行就能得到的，而是对整张
--      `peptide_enrichment` 做聚合才有的：
--        · 首页 / 构建器上每个方向的 `precursor_count`（“该方向的功能预测工具
--          一共打了多少条肽”），来自 v_peptide_enrichment_coverage.done_count；
--        · 覆盖页的 coverage_pct，来自同一张视图。
--
--      本机装的是 496 条构造所引用的 11,736 行分数子集，不是那 3.67 亿行全表。
--      就地重算只会得到子集的行数（每个工具 496 行），数字会明显偏小。
--
--      这份脚本把真库聚合出来的全库条数作为**数据**冻结在本机，并让覆盖视图
--      改从这张冻结表取值。视图对外暴露的列名、类型、语义一字未改，所以服务端
--      代码不需要任何改动。
--
--  数据来源
--      resouces/pg_export_20261011/aggregates/tool_counts.csv
--          42 个工具的精确 row_count（2026-10-11 由 Filo 在真库上聚合）
--      resouces/pg_export_20261011/aggregates/coverage_recomputed.csv
--          真库上覆盖视图的原始输出（12 个被追踪的工具，均 100%）
--
--  适用范围
--      ★ 只在「全表未装载、只有子集」的库上执行。真库（装了完整
--      peptide_enrichment）不需要这张表，其视图本来就取真实计数。
--
--  用法
--      psql -h 127.0.0.1 -d igem_peptides -v ON_ERROR_STOP=1 \
--           -f service/sql/22_local_frozen_enrichment_counts.sql
-- ============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- ---------------------------------------------------------------------------
-- [1] 冻结表：全库每个工具的条数
--     eligible_count 为真库上该工具的适用肽段数（与 done_count 相等即 100%）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.peptide_enrichment_tool_counts (
    tool           text   PRIMARY KEY,
    row_count      bigint NOT NULL,
    eligible_count bigint,
    source         text   NOT NULL DEFAULT 'frozen'
);

COMMENT ON TABLE public.peptide_enrichment_tool_counts IS
    'Full-library per-tool row counts, frozen from the real database so a '
    'subset-only local instance still reports the true library sizes.';

TRUNCATE public.peptide_enrichment_tool_counts;

INSERT INTO public.peptide_enrichment_tool_counts (tool, row_count, eligible_count) VALUES
    ('algpred2',             20248885, 20248885),
    ('amp-esm',              20248885, 20248885),
    ('anoxpepred',           20248885, 20248885),
    ('anoxpepred-chelating', 20248885, 20248885),
    ('anoxpepred-frs',       20248885, 20248885),
    ('aopxsvm',              20248883, 20248885),
    ('bepipred3',            20248885, 20248885),
    ('hemopi2',              20248885, 20248885),
    ('imfp_lg_ACP',          20248885, 20248885),
    ('imfp_lg_ADP',          20248885, 20248885),
    ('imfp_lg_AHP',          20248885, 20248885),
    ('imfp_lg_AIP',          20248885, 20248885),
    ('imfp_lg_AMP',          20248885, 20248885),
    ('mhcflurry',             134888,  134888),
    ('mhcflurry-A0201',       134888,  134888),
    ('mhcflurry-A0203',       134888,  134888),
    ('mhcflurry-A0206',       134888,  134888),
    ('mhcflurry-A0207',       134888,  134888),
    ('mhcflurry-A0301',       134888,  134888),
    ('mhcflurry-A1101',       134888,  134888),
    ('mhcflurry-A2402',       134888,  134888),
    ('mhcflurry-A2601',       134888,  134888),
    ('mhcflurry-A3101',       134888,  134888),
    ('mhcflurry-A3303',       134888,  134888),
    ('mhcflurry-B0702',       134888,  134888),
    ('mhcflurry-B1301',       134888,  134888),
    ('mhcflurry-B1502',       134888,  134888),
    ('mhcflurry-B3501',       134888,  134888),
    ('mhcflurry-B3802',       134888,  134888),
    ('mhcflurry-B3901',       134888,  134888),
    ('mhcflurry-B4001',       134888,  134888),
    ('mhcflurry-B4402',       134888,  134888),
    ('mhcflurry-B4601',       134888,  134888),
    ('mhcflurry-B5101',       134888,  134888),
    ('mhcflurry-B5201',       134888,  134888),
    ('mhcflurry-B5401',       134888,  134888),
    ('mhcflurry-B5801',       134888,  134888),
    ('plm4cpps',             20248885, 20248885),
    ('sodope',               20248885, 20248885),
    ('temstapro',            20248885, 20248885),
    ('tipred',               20248885, 20248885),
    ('toxinpred3',           20248885, 20248885);

-- 库内其余表都归 igem 所有，视图也以 igem 的身份执行；新表同样交给 igem，
-- 否则 igem 读视图时会在底层表上撞 permission denied。
ALTER TABLE public.peptide_enrichment_tool_counts OWNER TO igem;

-- ---------------------------------------------------------------------------
-- [2] 覆盖视图改从冻结表取值
--     工具清单 = 原先追踪的 12 个 + 5 个 iMFP-LG 通道。
--     真库里视图的 VALUES 列表只写死了 12 个，漏掉 30 个（含这 5 个通道），
--     于是抗炎方向的工具 imfp_lg_AIP 只能走 catalog.precursor_counts() 的
--     直接 count 兜底；在本机它会数出子集的 496 行。列进视图即可命中冻结值。
--     详见 resouces/pg_export_20261011/aggregates/VIEW_GAPS.md
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v_peptide_enrichment_coverage AS
 SELECT t.tool,
    COALESCE(c.row_count, 0::bigint) AS done_count,
    COALESCE(c.eligible_count, 0::bigint) AS eligible_count,
        CASE
            WHEN COALESCE(c.eligible_count, 0::bigint) = 0 THEN 0::numeric
            ELSE round(100.0 * c.row_count::numeric / c.eligible_count::numeric, 2)
        END AS coverage_pct
   FROM ( VALUES
            ('toxinpred3'::text), ('tipred'::text), ('algpred2'::text), ('sodope'::text),
            ('anoxpepred'::text), ('anoxpepred-frs'::text), ('anoxpepred-chelating'::text),
            ('hemopi2'::text), ('plm4cpps'::text), ('temstapro'::text),
            ('mhcflurry'::text), ('amp-esm'::text),
            ('imfp_lg_ACP'::text), ('imfp_lg_ADP'::text), ('imfp_lg_AHP'::text),
            ('imfp_lg_AIP'::text), ('imfp_lg_AMP'::text)
        ) t(tool)
     LEFT JOIN public.peptide_enrichment_tool_counts c ON c.tool = t.tool
  ORDER BY
        CASE
            WHEN COALESCE(c.eligible_count, 0::bigint) = 0 THEN 0::numeric
            ELSE round(100.0 * c.row_count::numeric / c.eligible_count::numeric, 2)
        END DESC NULLS LAST, t.tool;

COMMIT;

-- ---------------------------------------------------------------------------
-- [3] 自检：四个方向的功能工具都应报 20,248,885
-- ---------------------------------------------------------------------------
SELECT tool, done_count, eligible_count, coverage_pct
  FROM public.v_peptide_enrichment_coverage
 WHERE tool IN ('anoxpepred-frs', 'amp-esm', 'imfp_lg_AIP', 'tipred')
 ORDER BY tool;

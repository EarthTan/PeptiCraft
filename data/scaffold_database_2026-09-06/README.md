# 蛋白支架专利与序列数据库

本目录是从既有五份数据表及 FASTA 文件中整理出的去重版本。数据库只包含指定的 16 条序列，共计8种蛋白。

1.	锦波生物-重组人源化III型胶原
2.	锦波生物-30-aa COL3A1功能区×16的重组人源化III型胶原；
3.	武汉胶原蛋白-TRHCIII-1 225 aa 三螺旋样重组人胶原III；
4.	江苏创健医疗-重组人XVII型胶原片段170801/170802；
5. 	上海羽松-短重组丝素蛋白SF-4/SF-10；
6. 	Bolt Threads, Inc.-重组蜘蛛丝蛋白18B；
7. 	AMSilk / Evolved By Nature相关主体-eADF4(C16)工程蜘蛛丝蛋白；
8. 	陕西巨子生物-类人胶原蛋白 FHLC 1071 aa）

每条构建体在主表中占一行。


## 文件结构

- `scaffold_sequence_database.xlsx`&`scaffold_sequence_database.tsv`：合并后的主工作簿。
- `fasta/`：16 个白名单 FASTA 文件。

工作簿包含以下工作表：

- `主数据库`：序列、专利、申请人、构建体、产品用途、潜在应用、场景标签、递送标签、监管状态、实验结果、证据限制、来源 URL 和完整氨基酸序列。
- `实验证据`：与入选序列有关的实验组及结果位置；不含 Bellafill 和 BOTOX 比较项。
- `标签字典`：V3 使用场景和递送标签的定义。
- `证据分级`：E1–E5 及判级规则。
- `来源与去重`：五份来源文件的使用与去重决策。

## 主要改进
- 原来的场景、子类、递送方式及递送子类标签已全部删除。
- 应用标签收敛为五列：Topical appliance（涂敷成膜）、Mask patch、Hair care、Wound dressing、Injectable filler。
- 标签字典工作表目前只给出其中四项（Topical appliance、Mask patch、Wound dressing、Injectable filler）的定义，Hair care 一列尚无字典条目。

当前簇级标记数量（同一构建体的多条序列不重复计数）：
- Topical appliance：2 个构建体（Bolt 18B、FHLC）
- Mask patch：4 个构建体（锦波 HC8/HC16、锦波 16× 重复、羽松 SF-4/SF-10、FHLC）
- Hair care：2 个构建体（创健 COL17、eADF4(C16)）
- Wound dressing：4 个构建体（武汉 TRHCIII-1、创健 COL17、羽松 SF-4/SF-10、FHLC）
- Injectable filler：2 个构建体（锦波 HC8/HC16、锦波 16× 重复）

16 条记录每条至少带一个标签，标记依据写在该行自己的「产品/用途」与「潜在应用（中文整合）」两列里。重复单元与纯化标签版本（`eADF4_C16_repeat_unit_35aa`、`TRAUTEC_COL17_STREP_170801_HIS6_SEQID4_249aa`）同样带标签。

## FASTA 白名单

1. `JINBO_HC8_CN103122027B_257aa.fasta`
2. `JINBO_HC16_CN103122027B_501aa.fasta`
3. `JINBO_rhCollagenIII_16x_repeat_SEQID4_480aa.fasta`
4. `JINBO_TEV_rhCollagenIII_16x_486aa.fasta`
5. `JINBO_rhCollagenIII_16x_plus_tail_490aa.fasta`
6. `COLLAGEN_WUHAN_TRHCIII_1_SEQID1_225aa.fasta`
7. `TRAUTEC_COL17_170801_SEQID2_233aa.fasta`
8. `TRAUTEC_COL17_170802_SEQID3_466aa.fasta`
9. `TRAUTEC_COL17_STREP_170801_HIS6_SEQID4_249aa.fasta`
10. `YUSONG_SF4_SEQID1_62aa.fasta`
11. `YUSONG_SF10_SEQID2_38aa.fasta`
12. `BOLT_18B_repeat_SEQID2_315aa.fasta`
13. `BOLT_18B_SEQID1_945aa.fasta`
14. `eADF4_C16_repeat_unit_35aa.fasta`
15. `eADF4_C16_560aa.fasta`
16. `FHLC_SEQ_ID_NO_1.fasta`

所有序列均已用 FASTA 实际残基数与表中长度进行核对，16 条均一致。主表同时保存完整氨基酸序列和序列 SHA-256，便于后续版本校验。

## 合并与去重原则

- 以 `scaffold_application_tags_v3.xlsx` 的 `Scaffold V3` 为最新中文主数据。
- `scaffold_patents+sequence+delivery+scenario_v3.tsv` 与上述 V3 主表逐单元格一致，因此不重复导入。
- 从 `scaffold_patents_evidence_workbook.xlsx` 保留实验明细和证据分级。其 `序列主表` 是旧副本，不覆盖 V3。
- `scaffold_patents_sequence_guide.tsv` 的中英文重复字段不保留；其中唯一的 `Potential application` 信息已翻译为中文并合入主表的 `潜在应用（中文整合）`。
- `scaffold_patents_experiment_details.tsv` 是英文实验副本，而且引号与制表符结构损坏，未直接导入；对应信息由证据工作簿中的中文实验表提供。
- 未取得可靠 FASTA、混合物、比较项及未列入白名单的记录均未进入新数据库。

## PDB/CIF 说明

本目录没有 PDB 或 CIF 文件，因此主数据库不设置 `PDB/CIF accession` 一栏，也不把结构条目视为本地可用文件。

历史来源曾记录 6A0A 和 6A0C，它们是与锦波构建体相关的约 30 aa 功能区三聚体结构，不是 HC8、HC16 或 480–501 aa 完整构建体的原子模型。实验说明中若出现这些编号，仅表示来源文献或数据库定位信息。

## 使用限制

- 监管信息的原始核查日为 2026-08-05；“未核实到”不等于不存在。
- 专利序列与商业产品或具体批次的对应关系，如未公开确认，仍按原始资料保留限定语。
- E1–E5 表示可核实的最高证据层级，不代表已完成其下或其上的全部实验。
- 标签字典中的英文标签是受控词表名称，不是与中文主表并列的翻译副本。

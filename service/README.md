# PeptiCraft 后端服务

一个架在 `igem_peptides` PostgreSQL 数据库之上的只读 FastAPI 服务。前端只与它通信：界面渲染的每一个值都经由 `/api` 下 19 个接口之一送达，浏览器中不计算任何分数、阈值或安全裁决。

## 运行

```bash
pip install -r requirements.txt
cp .env.example .env               # 然后填入 IGEM_PG_PASSWORD
python -m uvicorn app.main:app --port 8000
```

没有自动重载，改动之后需要重启。交互式文档在 `/docs`，OpenAPI 文档在 `/openapi.json`。

## 配置

配置从环境变量或 `.env` 读取。`service/.env.example` 是带注释的模板，包含全部键。

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `IGEM_PG_HOST`、`IGEM_PG_PORT`、`IGEM_PG_DB`、`IGEM_PG_USER`、`IGEM_PG_PASSWORD` | — | 连接参数。主机没有本机默认值：数据库运行在另一台机器上，按其 IP 访问。主机或密码缺失是硬错误。 |
| `IGEM_PG_DSN` | 未设置 | 完整的 libpq 连接串，作为上述分项的替代。 |
| `IGEM_PG_ALLOW_LOCALHOST` | `false` | 本机的 PostgreSQL 实例不带 `igem` 角色，指向 localhost 的连接串会被拒绝，除非设置此项。它为有意搭建的 SSH 隧道而存在。 |
| `IGEM_DB_BACKEND` | `auto` | `auto` 探测一次 PostgreSQL，探测失败时提供 SQLite 夹具；`postgres` 永不回退；`sqlite` 完全不碰 PostgreSQL。 |
| `IGEM_SQLITE_PATH`、`IGEM_SQLITE_FIXTURE` | `local/…` | 夹具数据库的写入位置，以及据以构建它的 SQL。 |
| `STATEMENT_TIMEOUT_MS` | `60000` | 单条语句的上限。`peptide_enrichment` 有 3.77 亿行、130 GB，规划器一旦失控，应当让这次请求失败，而不是占住一个工作进程。 |
| `PG_POOL_MIN_SIZE`、`PG_POOL_MAX_SIZE`、`PG_POOL_TIMEOUT_S` | `1`、`8`、`15` | 连接池上下限。 |
| `API_HOST`、`API_PORT` | `127.0.0.1`、`8000` | 绑定地址。 |
| `CORS_ORIGINS` | Vite 开发服务器 | 允许的来源，逗号分隔。 |
| `ANALYSIS_PROVIDER` | `template` | `template` 依据已存分数渲染确定性文字。`llm` 预留给接模型的生成器，尚未实现；`LLM_BASE_URL`、`LLM_API_KEY` 与 `LLM_MODEL` 属于它。 |

## 本地回退

数据库位于一台通过隧道访问的工作站上，并非始终在线，因此服务可以改为提供一份随仓库打包的 SQLite 夹具。夹具在首次使用时由 `local/fixture_local.sql` 构建，内含四条手工构造，其用途是走通代码路径，不是管线产出。它覆盖骨架绑定逻辑的两条分支——一条构造的存档绑定与真实 496 行携带的是同一个占位值，一条的绑定带真实序列——另加第二个设计方向与第二个连接片段，使多方向排序与逐行连接片段回落是可观察的，而不是假定的。

`/api/health` 会说明实际应答的是哪个数据源。`database.backend` 取 `postgres` 或 `sqlite`；当它取 `sqlite` 时，`database.fallback_reason` 说明回退为何启用。需要知道眼前是否真实数据的调用方，读这个字段，而不是从数字大小去推断。

改动夹具 SQL 之后重建：

```bash
python scripts/build_local_db.py --force
```

`app/sqlite_backend.py` 负责翻译各仓储所写的 PostgreSQL 方言——`%s` 占位符、`= ANY(%s)` 展开为 `IN` 列表、针对 `json_each` 的数组包含、`::text` 强制转换——遇到无法翻译的写法直接抛错。翻译覆盖不到的语句会以错误告终，而不是返回一个错误答案。

## 接口

全部位于 `/api` 之下。18 个读，1 个写。

| 方法 | 路径 | 返回 |
| --- | --- | --- |
| GET | `/api/health` | 存活状态与数据库可达性，以及实际应答的后端。 |
| GET | `/api/meta/reference` | 方向、路径、工具、管线轮次与参考库，一个响应装齐。 |
| GET | `/api/meta/directions` | 四个设计方向。 |
| GET | `/api/meta/routes` | 五条应用路径及其筛选档案。 |
| GET | `/api/meta/tools` | 每项分数一条定义：预测器、改进方向、阈值及其来源。 |
| GET | `/api/meta/pipeline` | 筛选管线的轮次与各自状态。 |
| GET | `/api/meta/coverage` | 每个工具对肽库的覆盖量。 |
| GET | `/api/constructs` | 分页的构造列表。筛选参数：`direction`、`channel`（`top` 或 `bottom`）、`status`、`route_id`；`limit` 最大 500，另有 `offset`。 |
| GET | `/api/constructs/{id}` | 单条构造及其全部九项分数。`route_id` 选择筛选档案；`scaffold_id` 与 `linker_id` 指定装配目标。 |
| GET | `/api/constructs/{id}/scaffolds` | 可用于装配这条构造的骨架。 |
| GET | `/api/constructs/{id}/peptide` | 功能肽及其分数行。 |
| GET | `/api/constructs/{id}/analysis` | 针对该构造生成的一段文字，按指定的 `route_id`。 |
| POST | `/api/constructs/{id}/chat` | 分析接口的对话形式。唯一会写入的接口。 |
| GET | `/api/build` | 为一个 `direction` 与 `route_id` 排序候选，并把每条装配成融合序列。`scaffold_id` 与 `linker_id` 可选，各自只改变序列，不改变排序。 |
| GET | `/api/scaffolds` | 骨架库。筛选参数：`route_id`、`category`。 |
| GET | `/api/scaffolds/{id}` | 单个骨架簇。 |
| GET | `/api/scaffolds/{id}/constructs` | 绑定到某个骨架的构造。 |
| GET | `/api/linkers` | 整理过的连接片段库。`include_placeholder` 控制样例表中的条目是否一并列出。 |
| GET | `/api/linkers/{id}` | 单条连接片段。 |

`/` 返回一小段服务描述，不纳入接口模式。

## 源码结构

```
app/
  main.py             应用本体、错误处理器与路由挂载
  config.py           配置，以及拒绝本机连接串的守卫
  db.py               连接池，以及 DatabaseUnavailable / QueryFailed 这一对异常
  sqlite_backend.py   为回退后端做的 PostgreSQL 到 SQLite 翻译
  models/             响应模型（pydantic v2），每个接口组一个模块
  repositories/       每个表组一个模块；唯一书写 SQL 的地方
  services/           各项判断：打分、安全、参考数据、装配
  routers/            只做 HTTP 绑定
```

后三层之间的分工是改动得以局限在一处的关键。仓储用行来作答；服务把行变成一项裁决或一段装配好的序列；路由校验输入并选定状态码。有两处模块收拢了本会在多个调用方之间重复的判断：`services/scoring.py` 负责综合分与安全裁决，`services/constructs.py` 负责 `assemble`，也就是把一条构造的各段拼到一起的唯一位置。

## 脚本

| 脚本 | 用途 |
| --- | --- |
| `scripts/migrate.py` | 应用 `sql/` 下的幂等、增量式迁移。 |
| `scripts/import_scaffold_library.py` | 把 `data/scaffold_database_2026-09-06/` 的整理骨架表导入 `scaffold_library` 与 `scaffold_library_sequences`。 |
| `scripts/import_linker_library.py` | 把连接片段库导入 `linker_library`。 |
| `scripts/extract_linkers.mjs` | 产出连接片段导入输入的那个配套脚本，输入取自前端。已废弃：它读取的文件前端已不再保留，因此按现状无法靠它重跑导入。 |
| `scripts/build_local_db.py` | 构建或重建 SQLite 夹具。 |

## 测试

```bash
python -m pytest tests
```

44 项测试，全部离线。`test_sqlite_dialect.py` 针对翻译必须覆盖的每一种写法，钉住 PostgreSQL 到 SQLite 的转换；`test_local_backend.py` 让每个接口经由真实应用打在夹具上；`test_build.py` 钉住排序与两个装配目标，包括指定目标只改变序列、不改变候选集这一条。

改动某个仓储、使它产出的语句落在翻译覆盖之外时，会在这套测试里失败，而不是在部署时失败——这正是让接口对着 SQLite 跑一遍的意义所在。

## 服务坚守的规则

**缺失的分数不是零。** 九项分数全部可空，`null` 表示预测器没有覆盖那条肽，`0` 表示覆盖了且返回零。界面把两者渲染得不同，每一个汇总值也一样。

**两个方向的分只能用于排序，不是概率。** 抗炎（iMFP-LG 的 AIP 通道）与抗黑素（TIPred）区分的是"像不像功能肽"，而不是测量活性，因此服务给这类分数打上 `ranking_only` 语义标记。这类分数可以排序，但绝不配概率配色或通过／不通过徽章。

**阈值只存在于这里，并随答案一同返回。** 三道安全门是毒性、溶血与免疫原性；B 细胞表位倾向是软信号，不是门。免疫原性没有全局阈值——创面敷料与注射填充为 0.35，面膜贴片与涂敷成膜为 0.50，毛发护理为 0.60——因此该门按路径档案施加，档案随响应一并返回。下游不会重新推导阈值，也不会重新加权任何分量。

**装配每次请求只解析一次。** `?scaffold=` 与 `?linker=` 相互独立，都可省略，省略时该零件回落到构造自身行所记录的值。两者分别报告各自出处，因为一次构建的骨架可以来自请求，而连接片段来自行。

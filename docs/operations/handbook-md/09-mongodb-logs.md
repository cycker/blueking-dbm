# 第 9 章 · MongoDB 日志（配置、排障与各版本差异）

> 本章说明 **mongod / mongos 进程日志**、**慢查询 / Profiler** 与 **复制 oplog** 的区别，并按 **2.4～8.0** 归纳配置形态与字段差异。蓝鲸 DBM 安装参数以 `dbactuator` 为准。

---

## 9.1 先分清三类「日志」


| 名称 | 本质 | 典型路径 / 位置 | 运维用途 |
| --- | --- | --- | --- |
| **Server Log（诊断日志）** | mongod/mongos 进程写的文本或 JSON 日志 | DBM 默认见 [§9.2](#9-2-蓝鲸-dbm-默认路径) | 启动失败、复制、选举、连接、断言、部分慢操作摘要 |
| **oplog（复制日志）** | 副本集变更流；**角色上相当于 MySQL 的 binlog** | `local.oplog.rs`（capped 集合） | 从节点复制、增量备份、PITR；与 server log **无关** |
| **Profiler / 慢查询** | 超过阈值的操作用文档或日志行记录 | `system.profile` 集合 + server log 中的 `COMMAND`/`planSummary` 等 | 性能排障、索引设计（见 [第 10 章 · 索引](10-indexes.md)） |

**MySQL 对照（便于迁移心智）**：

| MySQL | MongoDB | 说明 |
| --- | --- | --- |
| **binlog** | **oplog**（`local.oplog.rs`） | 记录变更、供复制与增量恢复；DBM 备份里的 INCR 产物即基于 oplog |
| **redo log** | （本章不展开） | 存储引擎层 WAL，与 oplog / `mongo.log` 不是同一类对象 |
| **slow log** | **server log** 中的 Slow query + `system.profile` | 见 §9.5、§9.8 |

---

## 9.2 蓝鲸 DBM 默认路径

安装时由 `dbactuator` 写入配置（3.0+ 为 YAML `systemLog.path`，更早为 INI `logpath`）：


| 角色         | 默认日志文件（示例）                              | 源码依据                |
| ---------- | --------------------------------------- | ------------------- |
| **mongod** | `{BackupDir}/mongolog/{port}/mongo.log` | `mongod_install.go` |
| **mongos** | `{DataDir}/mongolog/{port}/mongo.log`   | `mongos_install.go` |


常见安装参数（与日志相关）：

```yaml
systemLog:
  destination: file
  logAppend: true
  path: /data/.../mongolog/27017/mongo.log
operationProfiling:
  slowOpThresholdMs: 200   # 平台默认可配，见安装单据 / dbConfig
```

### bk-dbmon · parselog：旧版文本日志 → 统一 JSON

蓝鲸 **bk-dbmon** 内置 `logparser` 任务（集群配置段 `**parselog`**），在实例机上 **tail** 读取 `systemLog.path` 指向的 `**mongo.log`**，将各行解析为 **统一结构的 JSON 行** 写入同目录下的 `**jsonlog/`**，供日志平台 / 慢查询分析等下游采集。**不修改** mongod 原始 `mongo.log`。


| 项    | 说明                                                              |
| ---- | --------------------------------------------------------------- |
| 默认开关 | `parselog.enable = true`（`cluster-config` 默认项）                  |
| 源文件  | 与 mongod/mongos 配置一致，如 `{BackupDir}/mongolog/{port}/mongo.log`  |
| 输出目录 | `**{mongo.log 所在目录}/jsonlog/`**                                 |
| 输出文件 | `jsonlog/mongo.log.{YYYYMMDD-HHMM}`，约 **10 分钟** 切分，保留约 **4 小时** |
| 断点续读 | `jsonlog/.seek` 记录偏移与 inode，重启后接着读                              |
| 限流   | `parselog.max-record-per-second` 默认 **10000** 行/秒               |


**按 MongoDB 日志形态自动选解析器**（`dbmon/pkg/mongologparser`，与 server 大版本对应关系如下）：


| 解析器    | 适用 server 日志形态 | 行首特征                | parselog 行为                                              |
| ------ | -------------- | ------------------- | -------------------------------------------------------- |
| **V1** | 2.4 时代纯文本      | 非 `{`、非 `20xx-` 时间戳 | 解析时间、组件、慢查询等，**输出统一 JSON**                               |
| **V2** | 3.0～4.2 纯文本    | 以 `20xx-` 开头的时间戳行   | 同上，兼容 3.x/4.0～4.2 **未开 `logFormat: json`** 的集群           |
| **V3** | 4.4+ 原生 JSON 行 | 以 `{` 开头            | 解码后归一化为同一 `**MongoLogMsg`** 结构再写出（含慢查询 `id:51803` 等字段整理） |


因此：**4.4 之前仍是纯文本日志**，只要开启 parselog，下游仍可只消费 `**jsonlog/` 里的 JSON**，无需为每个大版本写一套正则。4.4+ 若已在 mongod 侧配置 `systemLog.logFormat: json`，parselog 会做 **二次归一化**（字段拉平、元数据注入），与旧版文本路径产出格式一致。

> ⚠️ **注意**
>
> - parselog **占用 CPU**（按行解析）；异常流量或 `profilingLevel=2` 导致日志暴增时，可临时关闭或调低 `max-record-per-second`。
> - **`jsonlog/`** 是 parselog 解析产物，与 **oplog** 无关；原始排障仍以 **`mongo.log`** 为准。
> - 输出文件仅保留数小时，**不能**当作长期归档；长期留存依赖平台侧采集与存储策略。

关闭示例（见 [第 6 章](06-bk-dbmon.md)）：

```bash
./bk-dbmon config set --port all -s parselog -k enable -V false
```

本地调试（读文件并写 jsonlog，见 `bk-dbmon debug parselog`）：

```bash
./bk-dbmon debug parselog --help
```

入库后的日志可在 DBM **mongo-log 性能视图** 中检索，见 [第 13 章](13-performance-views.md)。排障仍建议保留 **工单 Job 日志 + server log + DBMon 指标** 三件套（见 [第 15 章附录](15-appendix.md)）。

---

## 9.3 配置形态：INI（2.x～3.0） vs YAML（3.0+）


| 维度    | 2.4～3.0（EOL）                                          | 3.2+（YAML，DBM 现网主流）                                |
| ----- | ----------------------------------------------------- | -------------------------------------------------- |
| 配置文件  | `--config` 指向 **INI/旧式 key=value**                    | `--config` 指向 **YAML**                             |
| 日志路径键 | `logpath=`、`logappend=true`                           | `systemLog.path`、`systemLog.logAppend`             |
| 慢查询阈值 | `slowms`（INI）或 `operationProfiling.slowOpThresholdMs` | 以 `operationProfiling.slowOpThresholdMs` 为主        |
| 组件分级  | 主要靠 `-v` / `--verbose`                                | `systemLog.component.*.verbosity` + `setParameter` |


DBM 仓库中 INI 模板（仅 3.0 以下介质仍可能用到）：

```ini
logpath={{logpath}}
logappend=true
```

3.0+ 结构体字段见 `dbm-services/mongodb/db-tools/dbactuator/pkg/common/mongod_conf.go`（`systemLog`、`operationProfiling`）。

---

## 9.4 Server Log：按版本对比

下表聚焦 **运维最常碰到的差异**；EOL 版本仅作迁移读史。细节以 [MongoDB systemLog](https://www.mongodb.com/docs/manual/reference/configuration-options/#systemlog-options) 与各版本 Release Notes 为准。


| 版本段              | 配置 / 格式                                        | 内容与字段                            | 轮转与 verbosity                             | 备注                                                    |
| ---------------- | ---------------------------------------------- | -------------------------------- | ----------------------------------------- | ----------------------------------------------------- |
| **2.4～3.0** 🔴   | INI `logpath`；无 `logFormat`                    | 纯文本；组件信息较少                       | `logRotate` 能力弱；多用 OS `logrotate`         | MMAPv1 时代；**禁止新装**                                    |
| **3.2～3.6** 🔴   | YAML `systemLog` 成熟；`destination: file|syslog` | 文本；复制、选举、连接错误可读性提升               | `logRotate: rename|reopen`                | 3.6 起 **FTDC** 诊断数据（`diagnostic.data`，非替代 server log） |
| **4.0～4.2** 🔴   | 同上 + 事务/分片事务相关日志行增多                            | 慢操作、选举、**txn** 相关关键字增多           | `systemLog.component` 粒度扩展                | 4.0 起多文档事务日志需结合 `mongod.log` + `currentOp`            |
| **4.4** 🟡       | 引入 `**systemLog.logFormat: text | json`**      | JSON 行便于 ELK / Loki；`attr` 结构化字段 | 组件 verbosity 与 **慢查询日志字段**增强（如 plan 信息更全） | 升级后若采集规则按「行首时间戳」解析，需回归                                |
| **5.0** 🟡       | `logFormat`、Versioned API 并存                   | Time Series、resharding 相关新日志类型   | 弃用项见 5.0 Compatibility                    | 与 [第 7 章](07-versions.md) FCV 升级同步检查                  |
| **6.0** 🟢       | JSON 日志在可观测性场景更常见                              | 查询计划器变更可能导致 **慢日志形态变化**          | 部分 `setParameter` 日志级别调整                  | 升级后对比升级前后同一条 SQL 的慢日志                                 |
| **7.0～8.0** 🟢🟣 | Backward Incompatible 可能涉及日志字段                 | 监控指标与日志字段增减见 Release Notes       | Prometheus / Grafana 采集规则需回归              | 8.0 Queryable Encryption 等安全相关日志单独核对                  |


### 4.4+ JSON 日志示例（节选）

```json
{"t":{"$date":"2025-05-19T08:00:01.123+00:00"},"s":"I","c":"COMMAND","id":51803,
 "ctx":"conn42","msg":"Slow query","attr":{"type":"command","ns":"game.users",
 "durationMillis":312,"planSummary":"IXSCAN { _id: 1 }"}}
```

采集侧建议：按 **JSON 解析** `msg` / `attr.durationMillis` / `attr.ns`，勿再依赖 3.x 时代的固定列宽文本正则。

---

## 9.5 慢查询与 Profiler：按版本对比


| 能力              | 2.4～3.6                            | 4.0+                       | 5.0+            | 说明                                  |
| --------------- | ---------------------------------- | -------------------------- | --------------- | ----------------------------------- |
| **阈值配置**        | `slowms`（INI）或 `slowOpThresholdMs` | 同左                         | 同左              | DBM 安装常见 **200ms**                  |
| **Profiler 级别** | `db.setProfilingLevel(0|1|2)`      | 同左                         | 同左              | `1`=只记慢操作；`2`=全量（**生产慎用**）          |
| **落库位置**        | `system.profile`（固定大小 capped）      | 同左                         | 同左              | 与 server log 中 Slow query **可能重复**  |
| **分片 / mongos** | mongos 上慢查询行为与 mongod 不同           | 4.2+ 分片事务慢日志更复杂            | 以当前版本 manual 为准 | 案例见 [第 12 章](12-cases.md) 慢查询条目     |
| **索引隐藏**        | 无                                  | 4.4+ `hiddenIndex` 影响 plan | 6.0+ 计划器变更      | 慢日志里关注 `planSummary` 是否为 **COLLSCAN**，见 [§9.8](#9-8-慢日志中的-collscan-全表扫描) |


**推荐生产组合**（DBM 场景）：

1. `operationProfiling.slowOpThresholdMs` 与业务 SLA 对齐（100～500ms 常见）。
2. **不要**长期 `profilingLevel=2`。
3. 平台 **parselog + 慢查询分析** 与 `db.currentOp()` / `explain` 交叉验证。
4. 大版本升级后抽 10 条历史慢 SQL **对比升级前后日志字段**是否仍能被正则 / JSON 路径命中。

### 9.5.1 日志里的 `command` 与 `find` / `update` / `aggregate` 是什么关系

慢日志里经常出现 **`COMMAND` 组件**、字段 **`type: "command"`**，以及正文里的 **`command: find { ... }`**——三者层级不同，混用会导致「明明在查表，日志却全是 command」的误解。

#### 三层结构（由外到内）

| 层级 | 字段 / 位置 | 含义 | 示例 |
| --- | --- | --- | --- |
| **① 日志组件** | 文本行 `I COMMAND`；JSON `"c":"COMMAND"` | 本条日志由 **COMMAND 子系统**打出；慢查询（`id:51803`）几乎都归此类 | 不等于「业务指令名叫 command」 |
| **② 操作类型** | 文本 `command: find` 前的类别；JSON `attr.type` | MongoDB 对本次操作的 **粗分类** | `query`、`command`、`update`、`remove`、`insert`、`getmore` 等 |
| **③ 真实指令** | 文本 `command: find { find:"coll", ... }`；JSON `attr.command` 对象 **第一个业务键** | 应用实际下发的命令 | `find`、`aggregate`、`update`、`delete`、`getMore`、`count` … |

**记忆口诀**：`c=COMMAND` 是「柜台」；`type` 是「业务大类」；`command.find / command.aggregate` 才是「具体办了什么事」。

#### 业务操作 ↔ 日志对照（4.4+ JSON 慢日志为主）

| 应用层操作 | 常见 `attr.type` | 看 `attr.command` 里的键 | 是否常有 `planSummary` |
| --- | --- | --- | --- |
| `find()` | `query` **或** `command` | `find` | ✅ 读路径 |
| `aggregate()` | 多为 `command` | `aggregate`（管道在 `pipeline`） | ✅ 可能有 `hasSortStage` |
| `update()` / `updateMany()` | `update` | `update` + `q` / `u` | 一般无 COLLSCAN 指标时仍看 `docsExamined` |
| `delete()` / `remove()` | `remove` | `delete` + `deletes` | 写路径 |
| `insert()` / `insertMany()` | `insert` | `insert` + `documents` | 写路径 |
| 游标拉取下一批 | `command` | `getMore`；聚合慢时常带 **`originatingCommand.aggregate`** | 延续首包计划 |
| `createIndex` 等管理命令 | `command` | `createIndexes`、`dropIndexes` 等 | 与查询优化相关 |

> ⚠️ **`type: "command"` 不等于「非 find/update」**  
> 4.4+ 很多 **`find` 慢查询** 的 `attr.type` 仍是 `command`，真正类型要看 `attr.command.find`。parselog（V3）会把整条 `command` 对象保留在 JSON 输出里，便于平台检索。

#### 文本慢日志（3.0～4.2）长什么样

```log
2024-03-26T10:11:46.240+0800 I COMMAND  [conn652482] command bkrepo.node_247 command: find {
  find: "node_247", filter: { ... }, planSummary: IXSCAN { _id: 1 }, ... 46719ms
}
```

| 片段 | 含义 |
| --- | --- |
| `I COMMAND` | 组件 = COMMAND（①） |
| `command bkrepo.node_247` | 命名空间 `db.collection` |
| `command: find { find: "node_247", ... }` | ③ 真实指令是 **find**；`find:` 后重复集合名是协议字段，属正常 |

更早版本还可能见到 **`I QUERY ... query:`**（读）、**`I WRITE ... insert/update:`**（写），与 COMMAND 行并存；bk-dbmon 的 **V2 解析器** 从行尾向前解析，把 `find`/`delete` 等写入归一化字段 `type`（见 `mongologparser/v2.go`）。

**写操作文本示例**：

```log
I WRITE [conn191216] insert game.actor_data query: { _id: ObjectId('...') } ninserted:1 ... 1318ms
I COMMAND [conn190722] command game.$cmd command: delete { delete: "battle_data_restore", deletes: [ ... ] } ... 367ms
```

#### `getMore` 与 `aggregate` 的关系

聚合、大结果集 `find` 会拆成多条日志：

1. 首包：`command.aggregate` 或 `command.find` + 创建 `cursorid`
2. 后续包：`type: "command"` + `command.getMore`；慢聚合常在 **`originatingCommand`** 里保留原始 `aggregate` 管道

排障 **聚合慢** 时，若只搜 `aggregate` 漏掉 `getMore`，会低估问题；应连同 `originatingCommand.aggregate` 一并检索。

#### 版本差异（运维采集时注意）

| 版本段 | 组件划分 | `type` 字段 | 建议检索方式 |
| --- | --- | --- | --- |
| **2.4** | `getmore` 独立行较多 | 无统一 JSON | 搜 `getmore` / `query:` |
| **3.0～4.2** | `QUERY` / `WRITE` / `COMMAND` 并存 | 文本行内 `command: <op>` | 正则 `command: (find|aggregate|update|delete)` |
| **4.4+** | 慢查询多在 `c:COMMAND` | JSON `attr.type` + `attr.command` | JSON 路径 `command.find`、`command.aggregate`；勿只过滤 `type=query` |

#### 与 bk-dbmon parselog 的对应

| 解析器 | 如何抽出「真实指令」 |
| --- | --- |
| **V2**（3.0～4.2 文本） | 从 `command: find` 解析出 `type=find`，`ns=db.coll` |
| **V3**（4.4+ JSON） | 直接读 `attr.type`；复杂结构在 `attr.command`（`getMore` 时查 `originatingCommand`） |

平台做慢查询统计时，应以 **③ `command` 对象首键**（或 `originatingCommand`）作为「SQL 类型」维度，`attr.type` 仅作辅助。

#### 排障时怎么用

1. 先确认是慢查询行：`Slow query` / `id:51803` / `durationMillis` 超阈值。
2. 用 **③** 判断是读还是写：`find`/`aggregate` → 索引与 [§9.8 COLLSCAN](#9-8-慢日志中的-collscan-全表扫描)；`update`/`delete` → 锁、`writeConflicts`、批量大小。
3. 看到 **`type: "command"`** 不要跳过，展开 `command` 或文本里 `command:` 后的第一个动词。
4. 分片集群：同一逻辑查询在 **mongos** 与 **shard** 上各打一条，需结合 `nShards`、`mongos` 字段区分。

---

## 9.6 oplog 与 server log 的关系

**oplog** 是副本集复制日志（**≈ MySQL binlog**），存放在 `local.oplog.rs` capped 集合中，供从节点复制、增量备份与 PITR 使用。

它不写入 `mongo.log`，也不由 `systemLog.path` 控制；排查复制延迟、回滚风险或增量恢复窗口时，应关注 `rs.printReplicationInfo()`、`rs.printSecondaryReplicationInfo()`、oplog 窗口与节点复制状态。

**oplog** 配置仍按副本集常规处理（`oplogSizeMB`、`replSet` 等），与 server log、slow log、Profiler 的配置互不替代。

---

## 9.7 日志轮转与磁盘


| 方式               | 适用版本      | 做法                                                                                   |
| ---------------- | --------- | ------------------------------------------------------------------------------------ |
| **MongoDB 内置**   | 3.0+ YAML | `systemLog.logRotate: rename` + `db.adminCommand({ logRotate: 1 })` 或 SIGUSR1（见官方文档） |
| **OS logrotate** | 全版本       | 对 `mongo.log` 做 copytruncate / rename 后需 **reopen** 或发信号，避免 mongod 仍写已移走的 inode      |
| **logAppend**    | 全版本       | DBM 默认 `true`，避免重启覆盖历史                                                               |


磁盘满时 mongod 可能 **拒绝启动或变只读**；监控除数据盘外应包含 `mongolog` 分区。

---

## 9.8 慢日志中的 COLLSCAN（全表扫描）

**COLLSCAN**（collection scan）表示查询计划 **未有效使用索引**，需要扫描集合中大量文档才能返回结果。在慢查询日志、Profiler 与 `explain("executionStats")` 中都会出现；是线上性能问题里 **最高频** 的信号之一。

### 9.8.1 在日志里怎么认

| 来源 | 典型字段 | 说明 |
| --- | --- | --- |
| **3.0～4.2 文本慢日志** | `planSummary: COLLSCAN` | 常与 `docsExamined`、`durationMillis` 同现 |
| **4.4+ JSON 慢日志**（`id:51803`） | `attr.planSummary`、`attr.docsExamined`、`attr.durationMillis` | parselog 归一化后字段名可能为 `PlanSummary` 等，以实际 JSON 为准 |
| **Profiler** | `system.profile.planSummary` | 与 server log 可交叉核对 |
| **explain** | `executionStats.executionStages.stage: "COLLSCAN"` | 以日志为线索，**最终以 explain 为准** |

**文本慢日志示例**（案例 #09 · cmdb）：

```log
find { bk_agent_id: "02000000000c42a1ab9f3a169..." }
planSummary: COLLSCAN  docsExamined:345209  1457ms
```

**JSON 慢日志示例**（节选）：

```json
{"msg":"Slow query","attr":{"ns":"cmdb.cc_HostBase","planSummary":"COLLSCAN",
 "docsExamined":345209,"nreturned":1,"durationMillis":1457}}
```

### 9.8.2 先看的三个数

| 指标 | 健康参考 | 含义 |
| --- | --- | --- |
| `planSummary` | `IXSCAN { ... }` 等 | `COLLSCAN` = 当前计划全表扫 |
| `docsExamined` vs `nreturned` | 接近 1:1 或略大 | 扫 34 万行只返回 1 行 → 典型索引未命中或选择性极差 |
| `durationMillis` | 低于 `slowOpThresholdMs` 则不进慢日志 | 平台默认阈值常见 **200ms**（见 §9.2） |

mongos / 分片场景：explain 需看各 `shards.*` 子计划，单分片 COLLSCAN 也会导致整体变慢。

### 9.8.3 有索引仍出现 COLLSCAN 的常见原因

| 原因 | 日志 / 现象线索 | 处置 |
| --- | --- | --- |
| **缺索引** | 新查询、新集合 | 按 ESR 规则建索引；见 [第 10 章](10-indexes.md) |
| **partial index 条件未写入查询** | 等值查询却 COLLSCAN；`getIndexes()` 有 `partialFilterExpression` | 查询中 **显式带上** partial 过滤条件（案例 #09） |
| **查询形态无法用索引** | `$or`、`$nin`、非前缀正则、`$where` | 改写法或建复合/多键索引 |
| **类型不一致** | 字段存 number、查询传 string | 统一 BSON 类型 |
| **planCache 陈旧** | explain 为 IXSCAN，监控/日志仍为 COLLSCAN | `db.coll.getPlanCache().clear()`（案例 #11） |
| **集合过小** | 文档很少 | 优化器故意 COLLSCAN，可接受 |
| **分片 scatter-gather** | 无 shard key 过滤 | 查询带分片键；见索引章分片小节 |

### 9.8.4 标准处置步骤

1. 从慢日志取出 **`ns`**、过滤条件、**`docsExamined` / `durationMillis`**。
2. 在对应节点执行 **`db.collection.find(...).explain("executionStats")`**，确认 `winningPlan` 是否为 COLLSCAN。
3. **补索引或改查询**；partial index 必须同步规范查询模板。
4. 变更后对比慢日志：`planSummary` 应变为 **IXSCAN**（或 `FETCH` + `IXSCAN`），`docsExamined` 显著下降。
5. 持续告警时查 [第 12 章](12-cases.md) 案例 **#09**（partial index）、**#11**（planCache）；系统方法见 [第 10 章 · 索引体检](10-indexes.md)。

> 💡 **与 IXSCAN 对比**：`IXSCAN` 表示走 B-Tree 索引；理想慢日志里应看到 `IXSCAN { 字段: 1 }`，且 `docsExamined` 与 `nreturned` 数量级相当。

---

## 9.9 排障速查：常见日志关键字 → 处置建议

| 关键字 / 模式 | 可能原因 | 建议动作 |
| --- | --- | --- |
| **`COLLSCAN`** / `docsExamined` 极大 | 全表扫描、索引未命中 | 见 [§9.8](#9-8-慢日志中的-collscan-全表扫描)；`explain` + [第 10 章](10-indexes.md) |
| `IXSCAN` 但仍慢 | 索引选择性差、内存排序 | 看 `docsExamined` vs `nreturned`；查 `SORT` / `SORT_KEY_GENERATOR` |
| `replSetStepDown` / `election` | 选主、stepDown | 对照拓扑与 priority；见 [第 2 章](02-cluster-topology.md) |
| `Rollback` / `recovering` | 回滚、节点追赶 | 查 oplog 窗口、磁盘与网络；勿贸然 `rs.reconfig` |
| `TooManyLogicalSessions` | Session 表膨胀 / 错误 `clusterRole` | 见 [第 12 章](12-cases.md) 案例 #05 |
| `KeyNotFound` / `error 211` | 分片 config / 错误角色 | 见案例 #01、#04 |
| `Slow query` / `durationMillis` | 慢查询 | 先看 `planSummary` 是否 COLLSCAN；再 `explain` |
| `cannot open /dev/urandom` | 容器 / 内核权限 | 见案例 #02 |
| `WT` / `wiredTiger` | 存储引擎内部错误 | 结合 `mongo.log` 上下文；数据目录排障勿与 `mongolog` 日志路径混淆 |

---

## 9.10 版本差异对照总表（速查）


| 主题                  | 2.4～3.0 | 3.2～3.6 | 4.0～4.2 | 4.4           | 5.0～6.0 | 7.0～8.0 |
| ------------------- | ------- | ------- | ------- | ------------- | ------- | ------- |
| 配置格式                | INI 为主  | YAML    | YAML    | YAML          | YAML    | YAML    |
| JSON server log     | ❌       | ❌       | ❌       | ✅ `logFormat` | ✅ 常用    | ✅ 持续演进  |
| `slowOpThresholdMs` | 部分版本    | ✅       | ✅       | ✅             | ✅       | ✅       |
| FTDC 诊断包            | ❌       | 3.6+    | ✅       | ✅             | ✅       | ✅       |
| 事务相关日志行             | —       | —       | ✅ 增多    | ✅             | ✅       | ✅       |
| 升级后采集回归             | 仅读史     | 仅读史     | 建议      | **必须**        | **必须**  | **必须**  |


---

## 9.11 官方文档入口


| 入口                                | 链接                                                                                                                                                                               |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| systemLog 配置                      | [https://www.mongodb.com/docs/manual/reference/configuration-options/#systemlog-options](https://www.mongodb.com/docs/manual/reference/configuration-options/#systemlog-options) |
| 日志消息参考                            | [https://www.mongodb.com/docs/manual/reference/log-messages/](https://www.mongodb.com/docs/manual/reference/log-messages/)                                                       |
| Profiler / 慢查询                    | [https://www.mongodb.com/docs/manual/tutorial/manage-the-database-profiler/](https://www.mongodb.com/docs/manual/tutorial/manage-the-database-profiler/)                         |
| 日志轮转                              | [https://www.mongodb.com/docs/manual/tutorial/rotate-log-files/](https://www.mongodb.com/docs/manual/tutorial/rotate-log-files/)                                                 |
| Release Notes（按版本查 Compatibility） | [https://www.mongodb.com/docs/manual/release-notes/](https://www.mongodb.com/docs/manual/release-notes/)                                                                         |


---

⬅️ [上一章 · 第 8 章 MongoDB 工具集](08-mongo-tools.md) ｜ [📖 返回目录](README.md) ｜ [下一章 · 第 10 章 索引设计与优化 ➡️](10-indexes.md)
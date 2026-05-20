# 第 13 章 · DBM 性能视图（Grafana Dashboard）

> 蓝鲸 DBM 在集群详情中嵌入 **Grafana 性能视图**，大盘 JSON 由仓库预置、随版本发布。本章说明三张 MongoDB 相关 Dashboard 的**适用集群类型、变量、面板分区**及与日志/告警的对应关系。

---

## 13.1 大盘文件与集群类型

| Dashboard 文件 | Grafana `title` | `uid`（预置） | `tags` | 适用 `ClusterType` |
| --- | --- | --- | --- | --- |
| `mongoreplicaset.json` | `mongoreplicaset` | `MongoReplicaSet` | `MongoReplicaSet` | **MongoReplicaSet** |
| `mongoshardedcluster.json` | `mongoshardedcluster` | `mongodbCluster` | `MongoShardedCluster` | **MongoShardedCluster** |
| `mongo-log.json` | `MongoLog` | （实例 uid） | `MongoReplicaSet` · `MongoShardedCluster` · `MongoLog` | **副本集 + 分片**（日志类） |

仓库路径（维护/ diff 用）：

```text
dbm-ui/backend/bk_dataview/dashboards/json/
├── mongoreplicaset.json
├── mongoshardedcluster.json
└── mongo-log.json
```

常量 `DASHBOARD_JSON_PATH` 见 `dbm-ui/backend/bk_dataview/grafana/constants.py`；Grafana 路由前缀一般为平台内 **`/grafana/`**（与 `config/default.py` 中 `GRAFANA` 配置一致）。

> 📌 **与 bk-dbmon 的关系**：性能视图展示的多为 **蓝鲸监控（BK-Monitor）采集的指标** 与 **日志平台** 中的结构化日志；节点上的 **bk-dbmon** 负责备份、心跳、parselog 等，见 [第 6 章](06-bk-dbmon.md)。二者互补，不可替代。

---

## 13.2 公共变量与时间范围

### 变量（模板）

| 变量名 | 出现大盘 | 含义 |
| --- | --- | --- |
| **`app`** | 三张均有 | 业务（DBM 业务英文缩写），用于过滤指标/日志 |
| **`cluster_domain`** | 三张均有 | 集群入口域名（与元数据 `master_domain` / 连接域名一致），**下钻时的主键** |
| **`instance_role`** | 仅 `mongoreplicaset` | 副本集成员角色：`m1` / `m2` / `backup` 等，见 [第 2 章](02-cluster-topology.md) |
| **`query_string`** | 仅 `mongo-log` | 日志检索语法（类 Lucene），默认 `*`；可写 `attr.durationMillis > 200` 等 |

### 数据源

| 数据源插件 | 用途 |
| --- | --- |
| **蓝鲸监控 - 指标数据**（`bkmonitor-timeseries-datasource`） | CPU、内存、磁盘、MongoDB exporter 指标、复制延迟等 |
| **日志平台**（`bk_log_datasource`） | `mongo-log` 大盘中的日志条数、慢日志分布、日志明细 |

默认时间范围多为 **最近 1 小时**（`now-1h` ~ `now`），可在视图右上角调整；`mongoreplicaset` 顶部 **OS** 链可跳转 tag 为 `node-disk-performance` 的主机大盘。

---

## 13.3 副本集大盘 · `mongoreplicaset`

**行（Row）分区**与运维关注点：

| 分区 | 主要内容 | 排障时看什么 |
| --- | --- | --- |
| **OS** | 主机 CPU、内存、磁盘占用、网卡/流量/包量、磁盘读写 | 资源瓶颈、备份/索引构建导致的 IO |
| **Set Info** | 版本、存储引擎、副本集成员数、Up 成员、**ReplSet Lag**、**Oplog Window**、最近选举 | 复制健康、oplog 是否快满 |
| **QPS && CONN** | 副本集级 / 成员级 QPS、连接数、新建连接 | 连接泄漏、流量突增 |
| **WritedTiger** | WT 队列、Session、Dirty%、scan object、dataSize 等 | 缓存压力、刷盘、全表扫倾向 |

**典型面板（节选）**：`ReplicaSet Operations`、`connection`、`Replication Lag`、`Oplog Recovery Window`、`WiredTiger Dirty%` 等。

**使用建议**：

1. 先看 **Set Info** 确认成员齐全、**Lag** / **Oplog Window** 正常。
2. 慢查询怀疑索引问题时，结合 **mongo-log** 与 [第 10 章 · 索引](10-indexes.md)；指标侧可看 QPS、WT scan。
3. 用 **`instance_role`** 区分 **backup**（`priority=0`）与 m1/m2，避免把 backup 节点 IO 误判为业务主库问题。

---

## 13.4 分片集群大盘 · `mongoshardedcluster`

在副本集指标基础上，增加 **mongos / shard mongod** 分角色对比与 **分片元数据**。

| 分区 | 主要内容 | 排障时看什么 |
| --- | --- | --- |
| **OS** | **mongos** 与 **shardsvr** 分别的 CPU、内存、磁盘、网络 | 某一层是否打满 |
| **Resource** | 同上资源的汇总对比 | 快速对比接入层 vs 数据层 |
| **Cluster** | Version、Mongos/Shards 数量、**Balancer**、分片库/集合、**Chunks**、均衡状态 | 路由与 chunk 是否异常 |
| **QPS && CONN** | Mongos / Mongod 操作量、按地址拆分、连接与新建连接 | 热点 mongos、某 shard 连接异常 |
| **Replication** | 各 shard 副本集 **Replication Lag**、**Shard Elections** | 分片内复制问题 |
| **WiredTiger** | 分角色 WT 指标 | 与副本集 WT 解读相同 |
| **locks** | 锁相关指标 | 写冲突、长时间锁等待 |
| **Chunks** | Chunk 分布与迁移相关 | balancer、迁移窗口、热点分片 |

**典型面板（节选）**：`Mongos Operations`、`Shard Operations`（query/insert/update 拆分）、`Replication Lag by Set`、`Chunks Balanced`。

**使用建议**：

1. 业务延迟高时：先看 **mongos** 是否正常，再下钻 **Shard Operations** 找热点 shard。
2. 迁移/均衡问题：盯 **Balancer Enabled**、**Chunks** / **Chunks Balanced**。
3. 与 [第 11 章 · URI](11-uri-readpref.md)、[第 12 章 · 案例](12-cases.md) 中 mongos、StaleConfig、system.sessions 等条目对照。

---

## 13.5 日志大盘 · `mongo-log`（MongoLog）

面向 **parselog 归一化后写入日志平台** 的 MongoDB 诊断日志（见 [第 9 章](09-mongodb-logs.md)），**副本集与分片集群共用**。

| 分区 | 面板 | 说明 |
| --- | --- | --- |
| **汇总** | 日志数量、慢日志数量 | 所选时间范围内总量 |
| **按时间分布** | Log count by (id)、ErrorLog by (instance) | 按日志 id / 实例看趋势 |
| **SlowLog** | SlowLog by (ns)、by (instance)、by (queryHash)、**SlowQuery** 明细 | 慢查询下钻；`queryHash` 对应计划形态 |
| **Log** | 日志原文检索列表 | 配合 **`query_string`** 过滤 |

**`query_string` 示例**（大盘内嵌指引）：

```text
*                                    # 全部
attr.durationMillis > 200            # 慢于 200ms
app-cluster-s1 and attr.durationMillis > 200   # 某分片/集合相关
```

完整语法见蓝鲸日志检索文档（大盘「query_string 使用指引」面板中的链接）。

> ⚠️ **注意**：日志大盘依赖 **日志采集与索引** 是否接入；若集群未开 parselog 或日志未入库，面板为空。原始文件仍在节点 **`mongo.log`** / **`jsonlog/`**。

---

## 13.6 三张大盘怎么选（速查）

选择大盘时先看 **集群类型**：副本集打开 `mongoreplicaset`，分片集群打开 `mongoshardedcluster`。`mongo-log` 是日志类大盘，**兼容 `MongoReplicaSet` 与 `MongoShardedCluster` 两种集群类型**，用于慢日志、错误日志和原始日志检索。

| 集群类型 / 排查目标 | 优先打开 | 说明 |
| --- | --- | --- |
| `MongoReplicaSet` | **mongoreplicaset** | 看副本集 CPU、内存、磁盘、oplog、复制延迟、WT 指标 |
| `MongoShardedCluster` | **mongoshardedcluster** | 看 mongos、shard、configsvr、chunk、balancer、各 shard 复制延迟 |
| 两种集群的慢查询 / 错误日志 / 原始日志 | **mongo-log** | 日志类大盘，依赖 parselog 入库；可按 `cluster_domain`、`query_string` 下钻 |
| 主机层网络/磁盘（非 Mongo 专有） | `mongoreplicaset` 顶部 **OS** 外链，或监控侧主机视图 | 分片集群也可从对应主机维度继续下钻 |

---

## 13.7 与告警、工单排障的配合

| 层次 | 来源 | 说明 |
| --- | --- | --- |
| **告警** | [§13.9 告警策略模板](#139-mongodb-告警策略模板) | 与大盘指标同源，阈值触发后推送蓝鲸监控 |
| **性能视图** | 本章三张 JSON | 人工下钻、关联对比 |
| **单据 / Job** | DBM 工单、标准运维 | 变更与部署日志，见 [第 4 章](04-tickets.md) |
| **案例库** | [第 12 章](12-cases.md) | 已知问题的现象—根因—处置 |

推荐路径：**告警事件 → 对应 Dashboard 变量带上 `cluster_domain` → mongo-log 查慢日志 / COLLSCAN → 必要时 mongosh + explain**。

---

## 13.8 修改大盘时的注意点

1. JSON 在仓库中 **版本管理**；改完后需在测试环境导入 Grafana 验证变量与 PromQL 是否仍匹配当前 **dbm_system** / MongoDB exporter 指标名。
2. `editable: false` 表示默认不允许 UI 随意改面板（以发布包为准）；环境若允许编辑，勿与上游 JSON 长期分叉而不回仓。
3. 指标标签依赖 DBM 上报的 **`app`、`cluster_domain`、`instance_role`、`cluster_type`** 等，元数据不准会导致大盘无数据。

---

## 13.9 MongoDB 告警策略模板

DBM 为 MongoDB 预置一组 **蓝鲸监控告警策略** JSON，路径：

```text
dbm-ui/backend/db_monitor/tpls/alarm/mongodb/
```

平台按 **`db_type: mongodb`** 导入/下发到各业务（`bk_biz_id` 在模板中为 `0`，表示通用模板，实际绑定时落到具体业务）。策略分两类：

| 类型 | `scenario` | 数据来源 | 说明 |
| --- | --- | --- | --- |
| **主机资源** | `os` | Prometheus / `bkmonitor:dbm_system:*` | CPU、内存、磁盘、网络流量/包量 |
| **组件事件** | `component` | 自定义事件 `custom.event.*` | 登录失败、进程重启、DBHA 切 mongos |

### 告警级别（蓝鲸监控惯例）

| level | 常见含义 | 本目录策略中的用法 |
| --- | --- | --- |
| **1** | 致命 / 严重 | 磁盘 ≥90%、CPU ≥90%、登录失败 |
| **2** | 预警 | CPU ≥60%、磁盘 ≥80%、内存/网络 ≥90%、mongod 重启 warning |
| **3** | 提醒 / 信息 | DBHA 切换 mongos **成功**（告知性） |

触发条件多为：**连续 N 个检测周期** 满足阈值（如 `count: 2`、`check_window: 5` 分钟），以 JSON 内 `detects` 为准。

### 策略清单（仓库预置 9 条）

| 模板文件 | 监控项 | 阈值（摘要） | 级别 | 排障提示 |
| --- | --- | --- | --- | --- |
| `MongoDB主机CPU使用率.json` | `cpu_summary:usage` | ≥**90%**（致命）；≥**60%**（预警） | 1 / 2 | PromQL **排除 `instance_role=backup`**；对照 [§13.3](#133-副本集大盘--mongoreplicaset) OS 区 |
| `MongoDB主机内存使用率.json` | `mem:pct_used` | ≥**90%** | 2 | 备份/索引构建会抬内存，结合进程与 WT 面板 |
| `MongoDB主机磁盘容量使用率.json` | `disk:in_use` | ≥**90%**（致命）；≥**80%**（预警） | 1 / 2 | 关注 `mongolog`、`/data/dbbak`、数据目录；见 [第 6 章](06-bk-dbmon.md) 磁盘说明 |
| `MongoDB主机网络流量使用率.json` | `net:speed_recv/sent`（eth1） | ≥**90%** | 2 | 与 [§13.3](#133-副本集大盘--mongoreplicaset) / [§13.4](#134-分片集群大盘--mongoshardedcluster) 流量面板对照 |
| `MongoDB主机网络包量使用率.json` | `net:speed_packets_*`（eth1） | ≥**90%** | 2 | 小包风暴、连接数突增时易触发 |
| `MongoDB登录失败critical事件.json` | 事件 `mongo_login` | `warn_level` ∈ error/critical，计数 ≥1 | 1 | 账号密码、authSource、网络；见 [第 11 章](11-uri-readpref.md) |
| `MongoDB重启warning事件.json` | 事件 `mongo_restart` | `warn_level=warning`，计数 ≥1 | 2 | 计划内重启也会告警；维护前用 **shield**（见下） |
| `MongoDB dbha切换mongos失败策略.json` | 事件 `dbha_mongos_switch_err` | 计数 ≥1 | 1 | 分片接入层 HA 切换失败，见 [第 14 章](14-dbha-autofix.md) |
| `MongoDB dbha切换mongos成功策略.json` | 事件 `dbha_mongos_switch_succ` | 计数 ≥1 | 3 | 成功摘除故障 mongos，见 [第 14 章](14-dbha-autofix.md) |

**集群范围**：主机类 PromQL 与事件类 `agg_condition` 均限定 `cluster_type` 为 **`MongoReplicaSet` | `MongoShardedCluster`**。

### 与性能视图、bk-dbmon 的关系

| 能力 | 作用 |
| --- | --- |
| **本章 Grafana 大盘** | 告警后 **下钻** 看曲线与维度（`app`、`cluster_domain`、`instance_role`） |
| **告警策略** | **自动** 阈值/事件触发，推送值班 |
| **bk-dbmon `alarm shield`** | 变更窗口 **临时屏蔽** 本机告警，避免误报（平台升级脚本也会调用） |

```bash
./bk-dbmon alarm shield  --port all    # 维护开始
./bk-dbmon alarm unblock --port 27017  # 维护结束
```

维护窗口内若仍要盯复制与磁盘，应依赖大盘 + 工单，而非关闭监控采集。

### 收到告警后建议动作（简表）

| 告警族 | 建议 |
| --- | --- |
| CPU / 内存 / 磁盘 / 网络 | 打开对应集群 **mongoreplicaset** 或 **mongoshardedcluster** 大盘 → 定位 `bk_target_ip` / 角色 → 是否备份/迁移/全表扫导致 |
| 登录失败 | 核对最近账号变更、连接串、是否混用错误 `authSource` |
| 重启 warning | 对照是否正在发版；查 `mongo.log` 启动段与 [第 9 章](09-mongodb-logs.md) |
| DBHA mongos 切换失败 / 成功 | [第 14 章 · DBHA 与自愈](14-dbha-autofix.md) |

修改阈值或 PromQL 时，请与 `db_monitor` 模块及现网 **bkmonitor:dbm_system** 指标名一并回归，并与 [§13.8](#138-修改大盘时的注意点) 同样保持仓库单一来源。

---

⬅️ [上一章 · 第 12 章 业务案例集](12-cases.md) ｜ [📖 返回目录](README.md) ｜ [下一章 · 第 14 章 DBHA 与自愈 ➡️](14-dbha-autofix.md)

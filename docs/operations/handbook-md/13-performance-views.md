# 第 13 章 · DBM 性能视图（Grafana Dashboard）

> 蓝鲸 DBM 在集群详情中嵌入 **Grafana 性能视图**。本章说明三张 MongoDB 相关 Dashboard 的**适用集群类型、变量、面板分区**及与日志/告警的对应关系。

---

## 13.1 大盘与集群类型

| Dashboard | Grafana `title` | 适用集群类型 |
| --- | --- | --- |
| 副本集性能视图 | `mongoreplicaset` | **MongoReplicaSet** |
| 分片集群性能视图 | `mongoshardedcluster` | **MongoShardedCluster** |
| 日志性能视图 | `MongoLog` | **MongoReplicaSet + MongoShardedCluster** |

> 📌 **与 bk-dbmon 的关系**：性能视图展示的多为 **蓝鲸监控（BK-Monitor）采集的指标** 与 **日志平台** 中的结构化日志；节点上的 **bk-dbmon** 负责备份、心跳、parselog 等，见 [第 6 章](06-bk-dbmon.md)。二者互补，不可替代。

## 13.2 副本集大盘 · `mongoreplicaset`

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

## 13.3 分片集群大盘 · `mongoshardedcluster`

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

## 13.4 日志大盘 · `mongo-log`（MongoLog）

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

## 13.5 智能助手

排障时可以结合智能助手快速整理现象、指标、日志和下一步检查项。

| 入口 | 使用方式 | 说明 |
| --- | --- | --- |
| Mongo 智能助手 | [ai-mongodb-dba.bkapps-gz1.woa.com/page](https://ai-mongodb-dba.bkapps-gz1.woa.com/page) | 面向 MongoDB DBA 场景，可用于慢查询、复制、备份、告警等问题咨询 |
| Knot Agent 智能体广场 | [knot.woa.com](https://knot.woa.com) | 在智能体广场查找 `bkdbm-mongodb-expert`，收藏后下次默认可见 |

### 推荐提问方式

**方式 1：时间段 + 集群域名 + 分析目标**

```text
{{时间段}} {{cluster_domain}} 负载分析
{{时间段}} {{cluster_domain}} 慢日志分析
```

时间段可以写成：

```text
最近1小时
2026-05-21 00:00 - 01:00
2026-05-21 - 2026-05-22
```

**方式 2：直接粘贴告警内容**

把蓝鲸监控告警标题、告警时间、集群域名、IP、指标值等内容直接粘贴给智能助手，让它先做告警解读，再给出下一步排查建议。

> 💡 **使用建议**
>
> 使用 Knot Agent 时，选择 Claude 模型效果通常更好。提问时建议带上集群类型、现象时间、告警名、关键指标截图或 `mongo-log` 中的慢日志片段。

---

## 13.6 MongoDB 告警策略

DBM 为 MongoDB 预置一组 **蓝鲸监控告警策略**。策略分两类：

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

触发条件多为：**连续 N 个检测周期** 满足阈值，具体周期与检测次数以当前环境蓝鲸监控策略为准。

### 策略清单（9 条）

| 策略 | 监控项 | 阈值（摘要） | 级别 | 排障提示 |
| --- | --- | --- | --- | --- |
| MongoDB 主机 CPU 使用率 | `cpu_summary:usage` | ≥**90%**（致命）；≥**60%**（预警） | 1 / 2 | 对照 [§13.2](#132-副本集大盘--mongoreplicaset) OS 区 |
| MongoDB 主机内存使用率 | `mem:pct_used` | ≥**90%** | 2 | 备份/索引构建会抬内存，结合进程与 WT 面板 |
| MongoDB 主机磁盘容量使用率 | `disk:in_use` | ≥**90%**（致命）；≥**80%**（预警） | 1 / 2 | 关注 `mongolog`、`/data/dbbak`、数据目录；见 [第 6 章](06-bk-dbmon.md) 磁盘说明 |
| MongoDB 主机网络流量使用率 | `net:speed_recv/sent` | ≥**90%** | 2 | 与 [§13.2](#132-副本集大盘--mongoreplicaset) / [§13.3](#133-分片集群大盘--mongoshardedcluster) 流量面板对照 |
| MongoDB 主机网络包量使用率 | `net:speed_packets_*` | ≥**90%** | 2 | 小包风暴、连接数突增时易触发 |
| MongoDB 登录失败 critical 事件 | 事件 `mongo_login` | `warn_level` ∈ error/critical，计数 ≥1 | 1 | 账号密码、authSource、网络；见 [第 11 章](11-uri-readpref.md) |
| MongoDB 重启 warning 事件 | 事件 `mongo_restart` | `warn_level=warning`，计数 ≥1 | 2 | 计划内重启也会告警；维护前用 **shield**（见下） |
| MongoDB DBHA 切换 mongos 失败 | 事件 `dbha_mongos_switch_err` | 计数 ≥1 | 1 | 分片接入层 HA 切换失败，见 [第 14 章](14-dbha-autofix.md) |
| MongoDB DBHA 切换 mongos 成功 | 事件 `dbha_mongos_switch_succ` | 计数 ≥1 | 3 | 成功摘除故障 mongos，见 [第 14 章](14-dbha-autofix.md) |

**集群范围**：上述策略面向 **`MongoReplicaSet`** 与 **`MongoShardedCluster`**。

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

---

⬅️ [上一章 · 第 12 章 业务案例集](12-cases.md) ｜ [📖 返回目录](README.md) ｜ [下一章 · 第 14 章 DBHA 与自愈 ➡️](14-dbha-autofix.md)

# 第 15 章 · 附录：排障入口、FAQ 与术语表

> 把仓库内 MongoDB 相关源码索引、官方手册主题入口、常见 FAQ 与基础术语集中归档，便于二次跳转。

---

## A.1 仓库源码索引（排障入口）

| 说明 | 路径 |
| --- | --- |
| 节点执行（dbactuator） | `dbm-services/mongodb/db-tools/dbactuator/` |
| bk-dbmon 进程与配置 | `dbm-services/mongodb/db-tools/dbmon/` |
| DBHA（mongos） | `dbm-services/common/dbha/ha-module/dbmodule/mongodb/` |

> 📋 **排障原则**：日志与脚本细节随版本迭代；生产排障以 **工单详情 + Job 日志 + 集群监控（DBMon）** 三件套为准。

---

## A.2 官方主题手册入口

| 入口 | 链接 | 说明 |
| --- | --- | --- |
| 📚 MongoDB Manual | <https://www.mongodb.com/docs/manual/> | 官方手册总入口 |
| 🐚 mongosh | <https://www.mongodb.com/docs/mongodb-shell/> | 新一代 MongoDB Shell |
| 📝 Release Notes | <https://www.mongodb.com/docs/manual/release-notes/> | 所有版本发布说明 |
| 🧱 Sharding | <https://www.mongodb.com/docs/manual/sharding/> | 分片、Zones、balancer |
| 🔒 Transactions | <https://www.mongodb.com/docs/manual/core/transactions/> | 事务模型与限制 |
| 📡 Change Streams | <https://www.mongodb.com/docs/manual/changeStreams/> | 变更订阅 |
| 🧮 Aggregation | <https://www.mongodb.com/docs/manual/aggregation/> | 聚合管道 |
| 🛡️ Security | <https://www.mongodb.com/docs/manual/security/> | TLS、SCRAM、审计 |
| 🔐 Encryption | <https://www.mongodb.com/docs/manual/core/security-encryption/> | 含 Queryable Encryption |

---

## A.3 FAQ：MySQL/Redis 思维迁移到 MongoDB 的 5 个常见误区

### Q1. 「Mongo 也是 KV 数据库吧？」

- **误区**：把 MongoDB 当 Redis 那样的 KV / 数据结构服务来用。
- **正解**：MongoDB 是 **文档库**，支持丰富查询、二级索引、聚合管道、事务等。运维上更贴近「*库表 + 复制拓扑*」治理方式，而非简单 KV。

### Q2. 「物理备份直接拷贝数据目录就行？」

- **误区**：套用 MySQL `xtrabackup` 或 Redis `RDB` 文件复制思路。
- **正解**：在 DBM 中务必走 `MONGODB_FULL_BACKUP` / `MONGODB_BACKUP` / `MONGODB_PITR_RESTORE` 等工单；脱离平台拷贝 WiredTiger 数据目录极易因 checkpoint 不一致导致回档失败。

### Q3. 「分片集群扩容直接改个数就行？」

- **误区**：把 MySQL 加从库、Redis Cluster 加节点的简单流程套用过来。
- **正解**：先弄清 `mongos / config / shard` 三类角色，再选择对应工单（`MONGODB_ADD_MONGOS` / `MONGODB_ADD_SHARD` / `MONGODB_*_SHARD_NODES`）。balancer / chunk 迁移可能有 IO 压力，避免业务高峰盲操。

### Q4. 「直接用 mongosh 创用户最方便？」

- **误区**：登 mongosh 后 `db.createUser` 临时建账号绕过平台。
- **正解**：账号会与平台元数据脱节，影响审计与下次变更。请走 `MONGODB_AUTHORIZE_RULES` 或 `MONGODB_EXCEL_AUTHORIZE_RULES` 工单。

### Q5. 「跨大版本升级，平台允许就一定没问题？」

- **误区**：把 DBM「可升级版本列表」当成兼容性背书。
- **正解**：**平台允许的升级路径 ≠ 全部历史特性兼容**。跨大版本升级前必读官方 **Release Notes** + **Backward Incompatible Changes**，并在测试环境完整跑 *备份 → 升级 → 验活 → 应用回归*。详见 [§7.6 升级前检查清单](07-versions.md#76-升级前检查清单通用--checklist)。

---

## A.4 术语表（Glossary）

| 术语 | 含义 |
| --- | --- |
| **Replica Set (RS)** | 副本集；一组 mongod 通过复制协议组成的高可用单元。 |
| **Sharded Cluster** | 分片集群；由 mongos + config + 多个 shard 组成，支持横向扩展。 |
| **mongos** | 分片集群的接入与路由层，对应用屏蔽分片细节。 |
| **Config Server** | 分片集群的元数据节点，存储 chunk 路由信息。 |
| **Primary / Secondary** | 副本集主节点 / 从节点；通过选举决定。 |
| **oplog** | 副本集复制日志（operation log），从节点据此回放 Primary 的变更。 |
| **WiredTiger** | 3.0 引入、3.2 起为默认存储引擎；MMAPv1 已淘汰。 |
| **BSON** | Binary JSON；MongoDB 文档与网络协议的底层编码。 |
| **Namespace** | 命名空间，`database.collection` 形式。 |
| **FCV** | `featureCompatibilityVersion`；用于受控启用新版本特性的兼容标志。 |
| **Read / Write Concern** | 读 / 写关注；控制读写一致性级别。 |
| **Change Streams** | 变更流；订阅集合 / 库 / 部署的有序变更事件。 |
| **balancer** | 分片集群中的 chunk 自动均衡器。 |
| **resharding** | 5.0+ 提供的分片键变更能力，缓解分片键选错的固化问题。 |
| **bk-dbmon** | 蓝鲸 DBM 中部署在实例机上的本地守护进程，负责备份、心跳、健康检查等例行任务。 |
| **dbactuator** | 蓝鲸 DBM 中负责在节点上执行原子操作（atomjob）的执行器。 |

---

⬅️ [上一章 · 第 14 章 DBHA 与故障自愈](14-dbha-autofix.md) ｜ [📖 返回目录](README.md)

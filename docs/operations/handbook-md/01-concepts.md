# 第 1 章 · 导读与概念对照

> **读者：** MySQL/Redis 经验运维　**耗时：** 约 10 分钟　**难度：** ⭐ 入门

本章面向具备 **MySQL / Redis** 运维背景的同学，先把 MongoDB 的核心概念「翻译」回你熟悉的世界，再列举 3 类容易踩坑的运维差异，避免迁移思维到 MongoDB 时跑偏。

---

## 1.1 读者画像与全文目标

| 画像 | 推荐起点 | 路径 |
|------|----------|------|
| 🆕 从未部署过 MongoDB | 先看 [第 3 章 · 数据目录和配置文件](./03-first-deploy.md)，了解节点本地形态 | 然后走 [第 4 章工单](./04-tickets.md) 发起部署 |
| 🔍 需要查改数据 | 直达 [第 5 章 · mongosh 入门](./05-mongosh.md) | 含 SQL 对照表 |
| ⬆️ 评估大版本差异 | 直达 [第 7 章 · 版本特性](./07-versions.md) | 看 EOL 警示与升级清单 |

---

## 1.2 副本集（Replica Set）— 概念对照

类比来理解：

- **像什么**：MySQL *主从 / InnoDB Cluster 单写多读*、Redis *Sentinel 下一主多从* 的高可用思路。
- **核心机制**：基于 `Raft` 类协议的 **选举**；依赖 **多数派（majority）** 存活。
- **读**：默认常连 **Primary**；若使用 **Secondary 读**，需理解 `read concern` 与 lag 对一致性的影响。

> 💡 **提示**：复制协议、选举语义随版本演进，跨大版本部署前请回看 [版本特性章节](./07-versions.md) 的「副本集协议」部分。

---

## 1.3 分片集群（Sharded Cluster）— 概念对照

类比 MySQL **分库分表 + 中间代理**，或 Redis **Cluster 多分片** 的「横向扩展」思路。集群由 3 类角色组成：

| 角色 | 作用 | 类比 |
|------|------|------|
| `mongos` | 接入与路由，对应用暴露查询入口 | MySQL Proxy / Redis 集群代理 |
| `config server` | 集群元数据与 chunk 路由信息 | etcd / 元数据节点 |
| `shard` | 数据分片，每个分片通常为 **副本集** | MySQL 分片实例 / Redis 分片 |

> 🔗 元数据处理代码：`dbm-ui/backend/db_meta/api/cluster/mongocluster/handler.py` 中 `MongoClusterHandler`。

---

## 1.4 数据模型对照

| MongoDB | 可类比 | 说明 |
|---------|--------|------|
| `database` | MySQL database | 顶层命名空间 |
| `collection` | MySQL table | 无固定 schema，文档结构可不同 |
| `document` | 一行记录（row） | BSON / JSON，字段可嵌套 |
| `namespace` | — | 形如 `db.collection` |

> ✅ **记忆要点**：Redis 多为 KV / 数据结构服务；Mongo 为 **文档库 + 丰富查询与索引**，运维上更贴近「*库表 + 复制拓扑*」治理方式。

---

## 1.5 与 MySQL / Redis 运维习惯的差异提醒 ⚠ 易踩

### 💾 备份与回档

以 DBM 工单语义为准，**不要**默认等价于 MySQL `xtrabackup` 物理备份，或 Redis `RDB` / `AOF` 的同一套路径与文件布局。

### 🧱 分片集群变更

先弄清 `mongos / config / shard` 三类角色再执行扩缩容；**避免**在业务高峰盲目执行 balancer 相关操作（若平台暴露）。

### 🔐 权限模型

MongoDB 用户与角色模型与 MySQL `GRANT`、Redis `ACL` 不同；授权走 `MONGODB_AUTHORIZE_RULES` 等工单（详见第 4 章 §4.6）。

---

[⬅ 返回目录](./README.md) ｜ [下一章 · 集群拓扑与节点规范 ➡](./02-cluster-topology.md)

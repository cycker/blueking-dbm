# 第 3 章 · MongoDB 部署后的目录与配置文件

> 本章只说明 DBM 部署 MongoDB 后，节点上的实际工作目录、数据目录、日志目录、配置文件，以及 dbconfig 参数如何落盘到实例配置。

---

## 3.1 目录总览 `目录`

DBM 部署 MongoDB 时，目录一般按 **数据目录（DataDir）** 与 **备份/日志根目录（BackupDir）** 分开处理。现场排障时优先看节点上的 `mongo.conf`，以其中的 `storage.dbPath` 和 `systemLog.path` 为准。

| 类型 | 常见目录 / 文件 | 说明 |
| --- | --- | --- |
| **工作目录根** | `/data` | 安装包、脚本下发和运维工具使用的默认根目录，实际值以环境内 `osconf.file_path` 为准 |
| **mongod 数据目录** | `/data1/mongodata/{port}/db` 或 `/data/mongodata/{port}/db` | WiredTiger 数据文件所在目录 |
| **mongod 配置文件** | `/data1/mongodata/{port}/mongo.conf` 或 `/data/mongodata/{port}/mongo.conf` | 3.0+ 为 YAML；同目录通常还有 `noauth.conf`、`key_of_mongo`、`pid.{port}` |
| **mongod 日志** | `/data/mongolog/{port}/mongo.log` 或 `/data1/mongolog/{port}/mongo.log` | 跟随 `BackupDir/mongolog` |
| **mongos 日志** | `/data1/mongolog/{port}/mongo.log` 或 `/data/mongolog/{port}/mongo.log` | 跟随 `DataDir/mongolog` |
| **备份产物** | `/data/dbbak/mg/mongodump/` | bk-dbmon 日常 `mongodump` 产物目录，见 [第 6 章](06-bk-dbmon.md) |

目录选择习惯：

1. **DataDir**：优先 `/data1`；若已有 `/data/mongodata` 或环境指定 `MONGO_DATA_DIR`，以实际安装结果为准。
2. **BackupDir**：优先已有 `/data/dbbak` 的磁盘；否则按 `/data1/dbbak`、挂载点等规则选择。
3. **mongod 与 mongos 日志不完全一致**：mongod 的 `mongo.log` 跟随 `BackupDir/mongolog`；mongos 的 `mongo.log` 跟随 `DataDir/mongolog`。
4. **不要把 `/data/dbbak` 与 `mongolog` 混淆**：`/data/dbbak` 是备份/工具产物根目录，`mongolog/{port}/mongo.log` 才是 server log。

---

## 3.2 本机配置文件 `配置文件`

MongoDB 实例最终以节点上的 `mongo.conf` 为准。DBM 不要求在部署工单里手写完整配置文件，而是根据 dbconfig 模板、主机规格、端口、角色和少量提单参数生成实例配置。

| 文件 / 目录 | 作用 |
| --- | --- |
| `mongo.conf` | mongod / mongos 的主配置文件；3.0+ 通常为 YAML |
| `noauth.conf` | 无认证场景或初始化阶段使用的辅助配置 |
| `key_of_mongo` | 副本集 / 分片集群内部认证使用的 keyFile |
| `pid.{port}` | 实例进程 PID 文件 |

常见 `mongo.conf` 核心字段如下：

```yaml
storage:
  dbPath: {DataDir}/mongodata/{port}/db
  engine: wiredTiger
  wiredTiger:
    engineConfig:
      cacheSizeGB: 12
replication:
  replSetName: {set_id}
  oplogSizeMB: 51200
systemLog:
  destination: file
  logAppend: true
  path: {BackupDir}/mongolog/{port}/mongo.log
operationProfiling:
  slowOpThresholdMs: 200
net:
  port: {port}
  bindIp: 127.0.0.1,{本机IP}
```

其中 `dbPath`、`systemLog.path`、`security.keyFile` 等路径由安装时的目录规则生成，不在 `dbconf` 模板里逐项暴露。

---

## 3.3 dbconfig 模板 `dbconfig`

dbconfig 保存 MongoDB 的默认值、允许范围和重启属性。部署时平台读取模板，结合规格与提单参数计算出最终 `dbConfig`，再生成本机 `mongo.conf` 并把集群级配置写回配置库。

| 层级 | 说明 | 运维入口（以当前 DBM 为准） |
| --- | --- | --- |
| **plat / app / cluster** | 模板支持 `plat,app,cluster` 三级覆盖；版本化在 cluster 级 | 平台 **配置管理** / 集群 **配置项** |
| **部署工单** | 只暴露部分业务参数，如 `oplog_percent`、`spec_id`；其余走模板默认 + 自动计算 | 部署单据表单 |
| **实例文件** | 安装完成后生成节点上的 `mongo.conf` | SSH 到节点查看 |

| 集群类型 `namespace` | 配置类型 `conf_type` | 配置文件 `conf_file` | 适用 MongoDB 大版本 |
| --- | --- | --- | --- |
| `MongoReplicaSet` | `dbconf` | `Mongodb-3` / `4` / `6` / `7` | 主版本 3 / 4 / 6 / 7，与介质 `db_version` 对齐 |
| `MongoShardedCluster` | `dbconf` | 同上 + `config_` 前缀项 | shard 用 `cacheSizeGB` / `oplogSizeMB`；config 用 `config_cacheSizeGB` / `config_oplogSizeMB` |
| `MongoDBCommon` | `config` | `osconf` | 安装路径、OS 用户等，与 DB 大版本无关 |

选择版本时，平台取 `db_version` 的主版本号，例如 `4.4.25` 对应 `Mongodb-4`。未导入对应模板时，需要先在 dbconfig 侧补齐。

---

## 3.4 dbconfig 参数与落盘映射 `映射`

### 3.4.1 副本集参数

| 参数名 | 模板默认（示例） | 允许范围（示例） | 是否需重启 | 写入 `mongo.conf` | 说明 |
| --- | --- | --- | --- | --- | --- |
| `cacheSizeGB` | 10 | 10～80 | 是 | `storage.wiredTiger.engineConfig.cacheSizeGB` | WiredTiger 缓存；部署时会按内存重算 |
| `oplogSizeMB` | 10240 | 10240～81920 | 是 | `replication.oplogSizeMB` | 副本集 oplog 上限；部署时会按磁盘与 `oplog_percent` 重算 |
| `slowOpThresholdMs` | 200 | 100～2000 | 是 | `operationProfiling.slowOpThresholdMs` | 超过阈值记慢查询；见 [第 9 章 · 日志](./09-mongodb-logs.md) |
| `destination` | `file` | 仅 `file` | 是 | `systemLog.destination` | 日志输出到文件 |
| `key_file` | 空 | - | 是 | `security.keyFile` | 副本集认证；安装时由平台生成路径与内容 |

### 3.4.2 分片集群额外参数

| 参数名 | 作用 | 对应角色 |
| --- | --- | --- |
| `config_cacheSizeGB` | configsvr WT 缓存 | `mongo_config` |
| `config_oplogSizeMB` | configsvr oplog | `mongo_config` |
| `cacheSizeGB` / `oplogSizeMB` | 各 shard 副本集成员 | `mongodb`（shard 上的 mongod） |

`mongos` 使用精简 `dbConfig`，通常只包含 `slowOpThresholdMs`、`destination` 等参数，无 oplog 段。

### 3.4.3 自动计算参数

部署时会覆盖模板里的 `cacheSizeGB`、`oplogSizeMB`：

| 输出参数 | 计算公式（概念） | 关联输入 |
| --- | --- | --- |
| `cacheSizeGB` | `int(主机内存 MB × 0.65 / 单机部署实例数 / 1024)`，最小 1 | 主机规格、单机部署实例数 |
| `oplogSizeMB` | `int(数据盘 GB × 1024 × (oplog_percent ÷ 100) / 单机部署实例数)` | 数据盘容量、`oplog_percent`、单机部署实例数 |

说明：

- **单机部署实例数**：`node_replica_count`，即同一台机器上跑几个 mongod 端口。
- **数据盘**：优先 `/data1`，否则 `/data`，以节点实际目录为准。
- 模板中的 `value_default` 多用于配置中心校验和展示；新集群安装以计算值为准。

---

⬅️ [返回索引](./README.md) ｜ ➡️ [下一章：04 · 工单驱动的运维](./04-tickets.md)

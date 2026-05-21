# 第 3 章 · 数据目录和配置文件

> 本章只说明 DBM 部署 MongoDB 后，节点上的实际工作目录、数据目录、日志目录和配置文件。

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
| `mongo.conf` | mongod 的主配置文件；3.0+ 通常为 YAML |
| `mongos.conf` | mongos 的主配置文件；不包含 storage / replication / oplog 段 |
| `noauth.conf` | 无认证场景或初始化阶段使用的辅助配置 |
| `key_of_mongo` | 副本集 / 分片集群内部认证使用的 keyFile |
| `pid.{port}` | 实例进程 PID 文件 |

### 3.2.1 mongod 配置文件

常见 `mongo.conf` 核心字段如下：

```yaml
storage:
  dbPath: {DataDir}/mongodata/{port}/db
  engine: wiredTiger
  wiredTiger:
    engineConfig:
      cacheSizeGB: {cacheSizeGB}
replication:
  replSetName: {set_id}
  oplogSizeMB: {oplogSizeMB}
systemLog:
  destination: file
  logAppend: true
  path: {BackupDir}/mongolog/{port}/mongo.log
operationProfiling:
  slowOpThresholdMs: 200
net:
  port: {port}
  bindIp: 127.0.0.1,{本机IP}
security:
  keyFile: {DataDir}/mongodata/{port}/key_of_mongo
sharding:
  clusterRole: {clusterRole}
```

其中 `clusterRole` 按实例角色生成：普通副本集留空或不写；分片集群 shard 节点为 `shardsvr`；configsvr 节点为 `configsvr`。`dbPath`、`systemLog.path`、`security.keyFile` 等路径由安装时的目录规则生成，不在 `dbconf` 模板里逐项暴露。

### 3.2.2 mongos 配置文件

常见 `mongos.conf` 核心字段如下：

```yaml
systemLog:
  destination: file
  logAppend: true
  path: {DataDir}/mongolog/{port}/mongo.log
operationProfiling:
  slowOpThresholdMs: 200
net:
  port: {port}
  bindIp: 127.0.0.1,{本机IP}
security:
  keyFile: {DataDir}/mongodata/{port}/key_of_mongo
sharding:
  configDB: {configReplSetName}/{configsvr1}:{configsvrPort},{configsvr2}:{configsvrPort},{configsvr3}:{configsvrPort}
```

`mongos` 是无状态路由层，不保存数据文件，也没有 `oplogSizeMB`；它通过 `sharding.configDB` 连接 config server 副本集获取分片元数据。

---

⬅️ [返回索引](./README.md) ｜ ➡️ [下一章：04 · 工单驱动的运维](./04-tickets.md)

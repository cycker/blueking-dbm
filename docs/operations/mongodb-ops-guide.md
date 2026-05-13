# MongoDB 运维指南（蓝鲸 DBM）

面向 **具备 MySQL、Redis 运维经验**、需要在 **蓝鲸智云 DBM（BK-DBM）** 中管理 MongoDB 的运维人员。本文以 **平台工单与控制台** 为主；通用 Shell 语法见姊妹篇。

**相关文档**：[Shell 语法入门](./mongodb-shell-primer.md) · [版本特性概览 2.4～8.0](./mongodb-version-features-2.4-8.md) · [bk-dbmon 使用指引](./mongodb-bk-dbmon-guide.md) · [可升级版本 API](../api/mongodb_list_available_versions.md)

---

## 1. 读者与目标

- **从未部署过 MongoDB** 的读者：请先阅读 **「4. 首次部署 MongoDB」**，再浏览工单全景。  
- **需要查改数据**：见 [Shell 入门](./mongodb-shell-primer.md)。  
- **评估大版本差异**：见 [版本特性概览](./mongodb-version-features-2.4-8.md)。
- **本地监控与 bk-dbmon**：见 [bk-dbmon 使用指引](./mongodb-bk-dbmon-guide.md)。

仓库组件概览见根目录 [`CLAUDE.md`](../../CLAUDE.md)。

---

## 2. MySQL / Redis → MongoDB 概念对照（运维视角）

### 2.1 副本集（Replica Set）

- **像什么**：MySQL **主从 / InnoDB Cluster 单写多读**、Redis **Sentinel 下一主多从** 的高可用思路。  
- **核心机制**：基于 Raft 类协议的 **选举**；依赖 **多数派（majority）** 存活。  
- **读**：默认常连 **Primary**；若使用 **Secondary 读**，需理解 **read concern / lag** 与业务一致性要求。

### 2.2 分片集群（Sharded Cluster）

- **像什么**：MySQL **分库分表 + 中间代理**、或 Redis **Cluster 多分片** 的「横向扩展」思路。  
- **角色**（与元数据处理代码注释一致，见 `dbm-ui/backend/db_meta/api/cluster/mongocluster/handler.py` 中 `MongoClusterHandler`）：  
  - **mongos**：接入与路由，对应用暴露查询入口。  
  - **config server**：集群元数据与 chunk 路由信息。  
  - **shard**：数据分片，每个分片通常为 **副本集**。

### 2.3 数据模型

| MongoDB | 可类比 |
|---------|--------|
| database | MySQL database |
| collection | MySQL table（无固定 schema） |
| document | 一行记录（BSON，可嵌套） |
| namespace | `db.collection` |

Redis 多为 KV/数据结构服务；Mongo 为 **文档库 + 丰富查询与索引**，运维上更贴近 **「库表 + 复制拓扑」** 的治理方式。

---

## 3. DBM 中的集群形态

平台支持两类 MongoDB 集群（见 `dbm-ui/frontend/src/services/model/mongodb/mongodb.ts` 等前端模型与元数据 `ClusterType`）：

| 类型常量 | 说明 |
|----------|------|
| **MongoReplicaSet** | 副本集集群 |
| **MongoShardedCluster** | 分片集群（mongos + config + shard） |

**集群列表/详情**中常见拓扑字段含义（便于对照 UI）：

| 字段/分组 | 含义 |
|-----------|------|
| **mongos** | 分片集群接入层实例 |
| **mongo_config** | Config Server 角色实例 |
| **mongodb** | 存储节点（副本集成员或 shard 上的 mongod） |
| **master_domain / cluster_entry** | 访问入口（域名、端口等，以界面为准） |

前端功能模块目录：`dbm-ui/frontend/src/views/db-manage/mongodb/`（含 `replica-set-instance-list`、`shared-cluster-instance-list`、`toolbox` 等）。

---

## 4. 首次部署 MongoDB（面向从未部署过的用户）

### 4.1 范围说明

本章描述在 **蓝鲸 DBM 内首次创建 MongoDB 集群** 的路径：通过 **标准化工单** 驱动安装与元数据注册。  
**不**等同于在裸机上手工执行 `mongod` 与手工改配置；若脱离 DBM，请参考 MongoDB 官方「Install」与生产 checklist。

### 4.2 前置条件（与 MySQL/Redis 在 DBM 提单类似）

- 已选 **蓝鲸业务**、**云区域（bk_cloud_id）**。  
- **DB 模块**、**城市/容灾亲和** 等平台配置项按企业规范填写。  
- **主机来源**：资源池或指定机器（`IpSource`，见工单详情序列化）。  
- **MongoDB 安装包**：在平台「介质」中已启用对应 **db_version**（与 [可升级版本 API](../api/mongodb_list_available_versions.md) 同源逻辑：以 `Package` 表为准）。  
- **权限**：部署类工单在代码中注册为 `ActionEnum.MONGODB_APPLY`（见 `mongo_replicaset_apply.py` / `mongo_shard_apply.py` 的 `@builders.BuilderFactory.register`）；实际菜单名以当前环境 **IAM / 蓝鲸权限中心** 为准。

### 4.3 选型：副本集 vs 分片集群

| 维度 | 副本集 | 分片集群 |
|------|--------|----------|
| **适用** | 数据量与写入可在单机群集内横向到「多副本」即满足 | 数据量或写入需 **多分片** 线性扩展 |
| **组件** | mongod 副本 | mongos + config + 多个 shard（每片多为副本集） |
| **运维复杂度** | 相对较低 | 更高（路由、均衡、分片键与扩容策略） |

不确定时优先 **副本集**；确需水平分片再选 **分片集群**。

### 4.4 工单类型与代码常量

| 界面/单据名称（来自 `TicketType` 中文描述） | 常量 |
|---------------------------------------------|------|
| MongoDB 副本集集群部署 | `MONGODB_REPLICASET_APPLY` |
| MongoDB 分片集群部署 | `MONGODB_SHARD_APPLY` |

定义位置：`dbm-ui/backend/ticket/constants.py`（`MONGODB_*` 段）。

### 4.5 提单时需准备的关键参数（与序列化器对齐）

以下字段来自工单 Builder 的 **DetailSerializer**，实际表单以当前版本 **DBM 前端** 为准；升级 UI 后请以 `dbm-ui/backend/ticket/builders/mongodb/mongo_replicaset_apply.py` 与 `mongo_shard_apply.py` 为准核对。

**副本集部署（`MongoReplicaSetApplyDetailSerializer`）要点**：

- `bk_cloud_id`、`db_app_abbr`、`cluster_type`、`db_version`、`start_port`  
- `replica_count`、`node_count`、`node_replica_count`、`replica_sets`（含 `set_id`、`name`、`domain`）  
- `spec_id`、`oplog_percent`、`ip_source`、`nodes`（若选手动指定机器）  
- `disaster_tolerance_level`、`city_code`（可选）

**分片集群部署（`MongoShardedClusterApplyDetailSerializer`）要点**：

- `bk_cloud_id`、`db_app_abbr`、`cluster_type`、`cluster_name`、`cluster_alias`、`db_version`、`start_port`、`oplog_percent`  
- `shard_machine_group`、`shard_num`、`resource_spec`、`ip_source`、`nodes`（可选）  
- `disaster_tolerance_level`、`city_code`（可选）

### 4.6 提交后如何跟进

1. 打开 **工单中心**，查看流水线节点是否全部成功。  
2. 失败时：在单据详情中查看 **标准运维 / Job 平台** 返回的脚本日志（与 MySQL/Redis 排障路径一致）。  
3. 常见方向：**资源规格不足**、**亲和与可用区冲突**、**端口占用**、**安装包缺失或未启用**（具体以校验错误信息为准）。

### 4.7 交付与验活

1. 在 **集群详情** 取得访问入口（域名、端口、连接串说明以界面为准）。  
2. 使用 **mongosh** 连接后执行：

```javascript
db.runCommand({ ping: 1 })
// 或（与服务器握手/查看连接信息）
db.runCommand({ hello: 1 })
```

3. **副本集**可执行 `rs.status()`；**分片集群**可执行 `sh.status()`。  
   命令说明见 [Shell 入门](./mongodb-shell-primer.md)。

---

## 5. 控制台与工单：日常运维路径

工单中文名与分组以下表为准；**权威枚举**见 `dbm-ui/backend/ticket/constants.py` 中 `TicketType` 的 `MONGODB_*` 定义（约 616～656 行）。第三列为代码中的工单类型常量。

### 5.1 部署与生命周期

| 中文名 | 常量 |
|--------|------|
| MongoDB 副本集集群部署 | `MONGODB_REPLICASET_APPLY` |
| MongoDB 分片集群部署 | `MONGODB_SHARD_APPLY` |
| MongoDB 集群启用 | `MONGODB_ENABLE` |
| MongoDB 集群禁用 | `MONGODB_DISABLE` |
| MongoDB 集群删除 | `MONGODB_DESTROY` |
| MongoDB 临时集群销毁 | `MONGODB_TEMPORARY_DESTROY` |

### 5.2 备份与回档

| 中文名 | 常量 |
|--------|------|
| MongoDB 全库备份 | `MONGODB_FULL_BACKUP` |
| MongoDB 库表备份 | `MONGODB_BACKUP` |
| MongoDB 定点回档 | `MONGODB_RESTORE` |
| MongoDB Pitr回档 | `MONGODB_PITR_RESTORE` |
| MongoDB 副本集集群迁移 | `MONGODB_REPLICASET_MIGRATE` |
| MongoDB 分片集群迁移 | `MONGODB_SHARD_MIGRATE` |

### 5.3 扩缩容与拓扑变更

| 中文名 | 常量 |
|--------|------|
| MongoDB 扩容接入层 | `MONGODB_ADD_MONGOS` |
| MongoDB 缩容接入层 | `MONGODB_REDUCE_MONGOS` |
| MongoDB 增加分片数 | `MONGODB_ADD_SHARD` |
| MongoDB 扩容分片集群shard节点数 | `MONGODB_SHARD_ADD_SHARD_NODES` |
| MongoDB 扩容副本集集群shard节点数 | `MONGODB_REPLICA_ADD_SHARD_NODES` |
| MongoDB 扩容shard节点数 | `MONGODB_ADD_SHARD_NODES` |
| MongoDB 缩容shard节点数 | `MONGODB_REDUCE_SHARD_NODES` |
| MongoDB 集群容量变更 | `MONGODB_SCALE_UPDOWN` |

### 5.4 主机与实例维护

| 中文名 | 常量 |
|--------|------|
| MongoDB 分片集群整机替换 | `MONGODB_SHARD_CUTOFF` |
| MongoDB 副本集整机替换 | `MONGODB_REPLICASET_CUTOFF` |
| MongoDB 整机替换 | `MONGODB_CUTOFF` |
| MongoDB 实例重启 | `MONGODB_INSTANCE_RELOAD` |
| MongoDB 实例下架 | `MONGODB_INSTANCE_DEINSTALL` |
| MongoDB 节点状态修复 | `MONGODB_INSTANCE_FIX_STATUS` |
| MongoDB 集群标准化 | `MONGODB_CLUSTER_STANDARDIZE` |

### 5.5 数据与脚本

| 中文名 | 常量 |
|--------|------|
| MongoDB 清档 | `MONGODB_REMOVE_NS` |
| MongoDB 数据导出 | `MONGODB_DATA_EXPORT` |
| MongoDB 数据导入 | `MONGODB_IMPORT` |
| MongoDB 变更脚本执行 | `MONGODB_EXEC_SCRIPT_APPLY` |

### 5.6 权限

| 中文名 | 常量 |
|--------|------|
| MongoDB 授权 | `MONGODB_AUTHORIZE_RULES` |
| MongoDB Excel授权 | `MONGODB_EXCEL_AUTHORIZE_RULES` |

### 5.7 插件与观测

| 中文名 | 常量 |
|--------|------|
| MongoDB 创建CLB | `MONGODB_PLUGIN_CREATE_CLB` |
| MongoDB 删除CLB | `MONGODB_PLUGIN_DELETE_CLB` |
| MongoDB 安装DBMon | `MONGODB_INSTALL_DBMON` |
| MongoDB 故障自愈 | `MONGODB_AUTOFIX` |

**bk-dbmon 详解**（安装路径、启停、`meta`/`alarm`/`config`、与蓝鲸监控对接、Flow 入参）：见 [MongoDB bk-dbmon 使用指引](./mongodb-bk-dbmon-guide.md)。

### 5.8 工单详情展示

单据执行过程可在 **工单中心** 查看；部分类型有专用展示组件，路径位于 `dbm-ui/frontend/src/views/ticket-center/common/ticket-detail/components/task-info/com-factory/mongodb/`。

---

## 6. 与 MySQL / Redis 运维习惯的差异提醒

- **备份与回档**：以 DBM 工单语义为准，不要默认等价于 MySQL 物理备份（如 xtrabackup）或 Redis RDB/AOF 的同一套路径与文件布局。  
- **分片集群变更**：先弄清 **mongos / config / shard** 再执行扩缩容；避免在业务高峰盲目 **balancer** 相关操作（若平台暴露）。  
- **权限**：MongoDB 用户与角色模型与 MySQL `GRANT`、Redis ACL 不同；授权走 **`MONGODB_AUTHORIZE_RULES`** 等工单。

---

## 7. 版本与介质

- **查询可升级版本列表**（HTTP API）：见 [mongodb_list_available_versions.md](../api/mongodb_list_available_versions.md)（`ToolboxViewSet.list_available_versions` → `ToolboxHandler.list_available_versions`）。  
- **升级链常量**：`dbm-ui/backend/flow/engine/bamboo/scene/mongodb/mongodb_upgrade_version.py` 中 `MONGODB_MAJOR_MINOR_UPGRADE_CHAIN`。  
- **各版本新特性与破坏性变更**：见 [版本特性概览](./mongodb-version-features-2.4-8.md)，避免在本指南重复维护长列表。

---

## 8. 排障与深入阅读（附录）

| 说明 | 路径 |
|------|------|
| 编排控制器 | `dbm-ui/backend/flow/engine/controller/mongodb.py` |
| 场景与子流程 | `dbm-ui/backend/flow/engine/bamboo/scene/mongodb/` |
| 节点执行（dbactuator） | `dbm-services/mongodb/db-tools/dbactuator/` |

**说明**：日志与脚本细节随版本迭代；生产排障以 **工单详情 + Job 日志 + 集群监控（DBMon）** 为准。

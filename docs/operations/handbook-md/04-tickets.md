# 第 4 章 · 控制台与工单：日常运维路径

> 工单中文名与分组以本章为准；具体常量定义以 DBM 平台工单枚举为准。

## 工单全景概览

| 分组 | 数量 | 关键词 |
|------|------|--------|
| 🚀 部署生命周期 | 6 | 部署 / 启用 / 禁用 / 删除 |
| 💾 备份回档 | 6 | 全备 / 库表备份 / PITR / 迁移 |
| 📈 扩缩容拓扑 | 8 | mongos / shard / 节点数 / 容量 |
| 🔧 主机与实例维护 | 7 | 替换 / 重启 / 下架 / 标准化 |
| 📦 数据与脚本 | 4 | 清档 / 导入 / 导出 / 脚本 |
| 🔐 权限 | 2 | 授权 / Excel 授权 |
| 🔌 插件与观测 | 4 | CLB / DBMon / 自愈 |

---

## 4.1 部署与生命周期（6 项）

| 中文名 | 常量 |
|--------|------|
| MongoDB 副本集集群部署 | `MONGODB_REPLICASET_APPLY` |
| MongoDB 分片集群部署 | `MONGODB_SHARD_APPLY` |
| MongoDB 集群启用 | `MONGODB_ENABLE` |
| MongoDB 集群禁用 | `MONGODB_DISABLE` |
| MongoDB 集群删除 | `MONGODB_DESTROY` |
| MongoDB 临时集群销毁 | `MONGODB_TEMPORARY_DESTROY` |

---

## 4.2 备份与回档（6 项）

| 中文名 | 常量 |
|--------|------|
| MongoDB 全库备份 | `MONGODB_FULL_BACKUP` |
| MongoDB 库表备份 | `MONGODB_BACKUP` |
| MongoDB 定点回档 | `MONGODB_RESTORE` |
| MongoDB Pitr 回档 | `MONGODB_PITR_RESTORE` |
| MongoDB 副本集集群迁移 | `MONGODB_REPLICASET_MIGRATE` |
| MongoDB 分片集群迁移 | `MONGODB_SHARD_MIGRATE` |

> ⚠ **易踩坑**：以 DBM 工单语义为准；**不要**默认等价 MySQL `xtrabackup` 或 Redis RDB/AOF 的同一套路径与文件布局。

---

## 4.3 扩缩容与拓扑变更（8 项）

| 中文名 | 常量 |
|--------|------|
| MongoDB 扩容接入层 | `MONGODB_ADD_MONGOS` |
| MongoDB 缩容接入层 | `MONGODB_REDUCE_MONGOS` |
| MongoDB 增加分片数 | `MONGODB_ADD_SHARD` |
| MongoDB 扩容分片集群 shard 节点数 | `MONGODB_SHARD_ADD_SHARD_NODES` |
| MongoDB 扩容副本集集群 shard 节点数 | `MONGODB_REPLICA_ADD_SHARD_NODES` |
| MongoDB 扩容 shard 节点数 | `MONGODB_ADD_SHARD_NODES` |
| MongoDB 缩容 shard 节点数 | `MONGODB_REDUCE_SHARD_NODES` |
| MongoDB 集群容量变更 | `MONGODB_SCALE_UPDOWN` |

---

## 4.4 主机与实例维护（7 项）

| 中文名 | 常量 |
|--------|------|
| MongoDB 分片集群整机替换 | `MONGODB_SHARD_CUTOFF` |
| MongoDB 副本集整机替换 | `MONGODB_REPLICASET_CUTOFF` |
| MongoDB 整机替换 | `MONGODB_CUTOFF` |
| MongoDB 实例重启 | `MONGODB_INSTANCE_RELOAD` |
| MongoDB 实例下架 | `MONGODB_INSTANCE_DEINSTALL` |
| MongoDB 节点状态修复 | `MONGODB_INSTANCE_FIX_STATUS` |
| MongoDB 集群标准化 | `MONGODB_CLUSTER_STANDARDIZE` |

---

## 4.5 数据与脚本（4 项）

| 中文名 | 常量 |
|--------|------|
| MongoDB 清档 | `MONGODB_REMOVE_NS` |
| MongoDB 数据导出 | `MONGODB_DATA_EXPORT` |
| MongoDB 数据导入 | `MONGODB_IMPORT` |
| MongoDB 变更脚本执行 | `MONGODB_EXEC_SCRIPT_APPLY` |

---

## 4.6 权限（2 项）

| 中文名 | 常量 |
|--------|------|
| MongoDB 授权 | `MONGODB_AUTHORIZE_RULES` |
| MongoDB Excel 授权 | `MONGODB_EXCEL_AUTHORIZE_RULES` |

> 💡 **权限模型差异**：MongoDB 的用户与角色模型与 MySQL `GRANT`、Redis `ACL` 不同；授权请走上述工单，不要试图用 mongosh 直接 `db.createUser` 绕过平台。

---

## 4.7 插件与观测（4 项）

| 中文名 | 常量 |
|--------|------|
| MongoDB 创建 CLB | `MONGODB_PLUGIN_CREATE_CLB` |
| MongoDB 删除 CLB | `MONGODB_PLUGIN_DELETE_CLB` |
| MongoDB 安装 DBMon | `MONGODB_INSTALL_DBMON` |
| MongoDB 故障自愈 | `MONGODB_AUTOFIX` |

> ⚠ **`MONGODB_INSTALL_DBMON` 的实际触发入口**：日常并非作为独立菜单暴露，bk-dbmon 的安装 / 更新走 §4.4 的「集群标准化」(`MONGODB_CLUSTER_STANDARDIZE`)；新部署、扩缩容、整机替换等场景会自动顺带安装，不必单独提单。详见 [第 6 章 §6.2](06-bk-dbmon.md)。

> 🔗 **DBHA / 自愈**：mongos 接入层 DBHA 与 `MONGODB_AUTOFIX` 触发链路见 [第 14 章](14-dbha-autofix.md)。  
> 🔗 **bk-dbmon 详解**（安装路径、启停、`meta`/`alarm`/`config`、与蓝鲸监控对接、Flow 入参）：见 [第 6 章](06-bk-dbmon.md)。

---

[← 第 3 章 数据目录和配置文件](03-first-deploy.md) | [↑ 返回目录](README.md) | [第 5 章 mongosh →](05-mongosh.md)

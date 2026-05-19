# 第 3 章 · 首次部署 MongoDB

> 面向**从未部署过 MongoDB** 的同学，介绍如何在蓝鲸 DBM 中通过**标准化工单**驱动安装与元数据注册。
> 本章**不**等同于在裸机上手工 `mongod` + 改配置。

---

## 3.1 范围说明 `边界`

- 本章描述 **在 DBM 内首次创建 MongoDB 集群** 的路径，通过工单驱动安装。
- **不**等同于在裸机执行 `mongod` 与手工改配置。
- 若脱离 DBM，请参考 MongoDB 官方「Install」与生产 checklist。

---

## 3.2 前置条件（Checklist） `Checklist`

| 类别 | 必备项 |
| --- | --- |
| 🏢 **业务与云区域** | 已选 **蓝鲸业务**；已选 **云区域**（`bk_cloud_id`） |
| ⚙️ **平台配置** | **DB 模块**（按企业规范填写）；**城市 / 容灾亲和** 等参数 |
| 🖥️ **主机来源** | `IpSource`：资源池 / 指定机器；详见工单详情序列化 |
| 📦 **MongoDB 安装包** | 「介质」中已启用对应 `db_version`；逻辑同 `list_available_versions` API（以 `Package` 表为准） |
| 🔐 **权限** | 部署类工单注册为 `ActionEnum.MONGODB_APPLY`（见 `mongo_replicaset_apply.py` / `mongo_shard_apply.py` 的 `@builders.BuilderFactory.register`）；实际菜单名以当前环境 **IAM / 蓝鲸权限中心** 为准。 |

---

## 3.3 选型：副本集 vs 分片集群 `决策`

| 维度 | 副本集 | 分片集群 |
| --- | --- | --- |
| **适用** | 数据量 / 写入在「多副本」内可满足 | 需 **多分片** 线性扩展 |
| **组件** | `mongod` 副本 | `mongos` + `config` + 多个 shard（每片多为副本集） |
| **运维复杂度** | 相对较低 | 更高（路由、均衡、分片键与扩容策略） |

> ✅ **建议**：不确定时优先 **副本集**；确需水平分片再选 **分片集群**。

---

## 3.4 工单类型与代码常量 `常量`

| 界面 / 单据名称 | 代码常量 |
| --- | --- |
| MongoDB 副本集集群部署 | `MONGODB_REPLICASET_APPLY` |
| MongoDB 分片集群部署 | `MONGODB_SHARD_APPLY` |

🔗 定义位置：`dbm-ui/backend/ticket/constants.py`（`MONGODB_*` 段，约 616~656 行）。

---

## 3.5 提单关键参数（Serializer 对齐） `字段`

> 以下字段来自工单 Builder 的 `DetailSerializer`。表单以当前 DBM 前端为准；升级 UI 后请以 `mongo_replicaset_apply.py` 与 `mongo_shard_apply.py` 为准核对。

### 3.5.1 副本集（`MongoReplicaSetApplyDetailSerializer`）

| 字段 | 说明 |
| --- | --- |
| `bk_cloud_id` | 云区域 ID |
| `db_app_abbr` | 业务英文缩写 |
| `cluster_type` | 集群类型常量 |
| `db_version` | MongoDB 大版本（介质中启用） |
| `start_port` | 起始端口 |
| `replica_count` / `node_count` / `node_replica_count` | 副本与节点数 |
| `replica_sets` | 包含 `set_id` / `name` / `domain` |
| `spec_id` / `oplog_percent` | 规格与 oplog 百分比 |
| `ip_source` / `nodes` | 资源池 / 手动指定机器 |
| `disaster_tolerance_level` / `city_code` | 容灾级别 / 城市（可选） |

### 3.5.2 分片集群（`MongoShardedClusterApplyDetailSerializer`）

| 字段 | 说明 |
| --- | --- |
| `bk_cloud_id` | 云区域 ID |
| `db_app_abbr` | 业务英文缩写 |
| `cluster_type` | 集群类型常量 |
| `cluster_name` / `cluster_alias` | 集群名 / 别名 |
| `db_version` / `start_port` | 版本 / 起始端口 |
| `oplog_percent` | oplog 百分比 |
| `shard_machine_group` | 分片机器分组 |
| `shard_num` | 分片数 |
| `resource_spec` | 资源规格 |
| `ip_source` / `nodes` | 资源池 / 手动指定机器 |
| `disaster_tolerance_level` / `city_code` | 容灾级别 / 城市（可选） |

---

## 3.6 提交后跟进 `排障`

1. **查看流水线节点**：打开 **工单中心**，确认所有节点状态为成功。
2. **查看脚本日志**：失败时进入单据详情，查看 **标准运维 / Job 平台** 返回的脚本日志（路径与 MySQL/Redis 一致）。
3. **常见失败方向**：资源规格不足、亲和与可用区冲突、端口占用、安装包缺失或未启用 …… 具体以校验错误信息为准。

---

## 3.7 交付与验活 `✅ Verify`

取得访问入口后，使用 **mongosh** 连接执行以下命令验活：

```javascript
// 通用握手 / ping
db.runCommand({ ping: 1 })

// 查看连接信息（替代旧版 isMaster）
db.runCommand({ hello: 1 })
```

```javascript
// 副本集：查看成员状态
rs.status()

// 分片集群：查看分片与块分布摘要
sh.status()
```

> 📖 **命令详解**：见 [第 5 章 · mongosh Shell 入门](./05-mongosh.md)。

---

⬅️ [返回索引](./README.md) ｜ ➡️ [下一章：04 · 工单驱动的运维](./04-tickets.md)

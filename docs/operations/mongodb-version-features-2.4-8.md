# MongoDB 2.4～8.0 版本特性概览（运维向）

本文按 **主次版本线** 归纳对运维、备份回档、升级、安全、存储与复制/分片影响较大的变化，便于与 MySQL/Redis 背景同事建立「大版本差异」心智。

**相关文档**：[运维指南](./mongodb-ops-guide.md) · [bk-dbmon 使用指引](./mongodb-bk-dbmon-guide.md) · [Shell 入门](./mongodb-shell-primer.md) · [DBM 可升级版本 API](../api/mongodb_list_available_versions.md)

---

## 文首必读

1. **MongoDB 2.4～4.0 及更早系列已 EOL（生命周期结束）**  
   以下内容中涉及老版本的描述 **仅作迁移与读史**，**禁止在新环境部署** EOL 版本。

2. **事实来源**  
   特性与兼容性以 **MongoDB 官方手册 Release Notes / Compatibility Changes** 为准。编写本文时以各版本官方页面为纲；若你所在环境为定制发行版，以厂商说明为准。

3. **与蓝鲸 DBM 的关系**  
   平台「可升级版本列表」由介质包与代码中的升级链决定，见 [list_available_versions](../api/mongodb_list_available_versions.md) 及 `MONGODB_MAJOR_MINOR_UPGRADE_CHAIN`。  
   **平台允许的升级路径 ≠ 全部历史特性**；跨大版本升级前务必同时阅读官方的 **Release Notes** 与 **Backward Incompatible Changes**。

4. **维护方式**  
   各章仅列 **少量代表项**；细节、小版本补丁与弃用时间表请以对应官方 Release Notes 为准。

---

## 官方 Release Notes 索引（建议收藏）

| 版本线 | 手册入口（MongoDB Docs） |
|--------|-------------------------|
| 8.0 | <https://www.mongodb.com/docs/manual/release-notes/8.0/> |
| 7.0 | <https://www.mongodb.com/docs/manual/release-notes/7.0/> |
| 6.0 | <https://www.mongodb.com/docs/manual/release-notes/6.0/> |
| 5.0 | <https://www.mongodb.com/docs/manual/release-notes/5.0/> |
| 4.4 | <https://www.mongodb.com/docs/manual/release-notes/4.4/> |
| 4.2 | <https://www.mongodb.com/docs/manual/release-notes/4.2/> |
| 4.0 | <https://www.mongodb.com/docs/manual/release-notes/4.0/> |
| 3.6 | <https://www.mongodb.com/docs/manual/release-notes/3.6/> |
| 3.4 | <https://www.mongodb.com/docs/manual/release-notes/3.4/> |
| 3.2 | <https://www.mongodb.com/docs/manual/release-notes/3.2/> |
| 3.0 | <https://www.mongodb.com/docs/manual/release-notes/3.0/> |
| 更早 | 见手册 [Release Notes 总目录](https://www.mongodb.com/docs/manual/release-notes/) |

---

## 2.4～3.0（合并简述）

- **存储**：长期以 **MMAPv1** 为主；**WiredTiger** 在 3.0 作为可选存储引擎引入，为后续默认引擎奠基。
- **复制集**：副本集能力逐步成熟（选举、多数派等语义随版本演进）；升级到老版本集群时需查当时手册的 **replica set configuration** 限制。
- **查询与索引**：文本索引、地理空间等能力在 2.x～3.0 期间逐步扩展，具体以当时 Release Notes 为准。

**运维提示**：仅遗留系统可能接触；若仍见 MMAPv1，应规划迁移到 WiredTiger 支持的版本（见 3.2+）。

---

## 3.2

（详见 [Release Notes 3.2](https://www.mongodb.com/docs/manual/release-notes/3.2/)）

- **存储引擎**：新部署默认 **WiredTiger**（仍支持 MMAPv1 的升级路径需单独评估）；影响备份体积、缓存与并发行为。
- **复制集选举**：选举与心跳参数随版本调整，跨版本升级需对照 **replication** 兼容性说明。
- **索引**：引入 **partial index（部分索引）** 等能力，利于缩小索引体积与写放大。
- **运维**：`mongo` shell 仍为当时主流客户端；后续版本逐步过渡到 **mongosh**（见下文「运维工具链」）。

## 3.4

（详见 [Release Notes 3.4](https://www.mongodb.com/docs/manual/release-notes/3.4/)）

- **数据类型**：**Decimal128** 满足金融等精确小数场景，避免仅用 Double 带来的误差。
- **排序与比较**：**Collation** 可在集合/索引/查询层统一语言规则，对多语言业务与索引选择有影响。
- **聚合**：**`$facet`** 等阶段增强，便于在一个管道内做多路聚合（运维报表类场景会用到）。
- **读Concern**：**linearizable** 等级等与强一致读相关的语义扩展，与跨机房延迟权衡相关。
- **分片**：balancer 与 chunk 迁移行为持续调优，升级前后建议关注 **sharding** 章节中的行为变化。

## 3.6

（详见 [Release Notes 3.6](https://www.mongodb.com/docs/manual/release-notes/3.6/)）

- **变更流（Change Streams）**：对集合/库/部署提供有序变更订阅，依赖 **WiredTiger** 与 **副本集协议版本 1（pv1）** 等前提（见 [Change Streams 手册](https://www.mongodb.com/docs/manual/changeStreams/)）。
- **可重试写入（retryable writes）**：网络闪断时由驱动在限定条件下自动重试写操作，需 **驱动版本** 支持。
- **数组更新**：**arrayFilters** 使多元素定位更新更可控，减少「整条文档替换」带来的并发冲突。
- **安全**：SCRAM 认证与 TLS 配置在 3.x 持续强化，升级需核对客户端与驱动。

## 4.0

（详见 [Release Notes 4.0](https://www.mongodb.com/docs/manual/release-notes/4.0/)）

- **多文档事务（副本集）**：在副本集上提供跨文档 ACID 能力（集合级/库级限制、与 oplog 大小等相关，以官方限制为准）。
- **聚合**：**`$lookup`** 与 **`$convert`** 等增强，影响离线分析与数据校验类任务。
- **删除与回收**：**TTL 删除**与孤儿文档清理等行为有调整，运维需关注 **compatibility** 中的存储与复制章节。
- **升级路径**：从 3.6 等版本升级通常需 **二进制升级 + FCV 分步**，勿跳步。

## 4.2

（详见 [Release Notes 4.2](https://www.mongodb.com/docs/manual/release-notes/4.2/)）

- **通配符索引（wildcard index）**：为半结构化文档提供较灵活的索引策略，需结合查询模式评估写放大。
- **聚合 `$merge`**：将管道结果写入目标集合，常用于 ETL/物化视图类流水线。
- **分布式多文档事务**：扩展至 **分片集群**（有路由、chunk 迁移与性能限制；务必读官方 **transactions** 说明）。
- **字段级加密（客户端 Field Level Encryption）**：敏感字段加解密在驱动侧完成，与密钥管理流程相关。

## 4.4

（详见 [Release Notes 4.4](https://www.mongodb.com/docs/manual/release-notes/4.4/)）

- **对冲读（hedged reads）**：对跨地域读延迟有优化潜力，需结合 read preference 与拓扑理解副作用。
- **流式复制（streamable oplog cursor）**：副本集同步路径优化，影响拖从/追平速度（以官方描述为准）。
- **隐藏索引（hidden indexes）**：索引对规划器不可见但仍维护，适合「生产验证索引收益」。
- **聚合 `$unionWith`**：跨集合管道组合能力增强。

## 5.0

（详见 [Release Notes 5.0](https://www.mongodb.com/docs/manual/release-notes/5.0/)）

- **时间序列集合（Time Series）**：专用建表方式与索引策略，适合监控与 IoT 类写入高、查询按时间窗口的场景。
- **版本化 API（Versioned API）**：应用绑定服务器 API 版本，减轻升级对应用的影响（需驱动配合）。
- **分片**：**live resharding / reshardCollection** 等能力减轻「分片键选错」后的迁移成本（权限、窗口与资源开销需评估）。
- **版本字段**：`featureCompatibilityVersion` 与升级步骤在 5.x 文档中有明确清单，升级前后务必备份。

## 6.0

（详见 [Release Notes 6.0](https://www.mongodb.com/docs/manual/release-notes/6.0/)）

- **查询与索引计划器**：优化器与索引行为有增量变化，升级后建议抓 **慢查询 + explain** 做回归。
- **时序与聚合**：时间序列、聚合与 `$lookup` 等继续演进，报表与归档任务需回归。
- **安全与默认行为**：默认绑定、日志与弃用项以 **Compatibility** 为准逐项勾选。
- **平台行为**：若使用 Atlas Search 等周边能力，需单独核对其版本矩阵（社区版/企业版差异以厂商为准）。

## 7.0

（详见 [Release Notes 7.0](https://www.mongodb.com/docs/manual/release-notes/7.0/)）

- **Backward Incompatible Changes**：作为升级前主检查清单（驱动、配置、脚本、监控采集项）。
- **性能与可观测性**：监控指标与日志字段可能有增减，Prometheus/Grafana 等采集规则需回归。
- **分片与副本集**：路由、选举与 balancer 相关参数若有弃用，以 Release Notes 为准替换。

## 8.0

（详见 [Release Notes 8.0](https://www.mongodb.com/docs/manual/release-notes/8.0/)）

- **性能与扩展**：官方在 8.0 强调吞吐、复制与扩展效率等方向改进；**具体数值与场景以 Release Notes 为准**，勿脱离文档硬背营销口径。
- **Queryable Encryption**：服务端查询与加密组合能力持续演进（例如范围类查询支持度，以 [Query Encryption 文档](https://www.mongodb.com/docs/manual/core/queryable-encryption/) 为准）。
- **升级核对**：**驱动**、**FCV**、**config server 拓扑**、**备份/回档工具** 与 DBM 介质是否覆盖目标版本。

---

## 按主题查阅官方手册（与上表互补）

下列为主题级手册入口，便于「横向查一类能力」而非按版本重读：

| 主题 | MongoDB Manual 入口（示例） |
|------|----------------------------|
| 存储引擎 / WiredTiger | [Storage](https://www.mongodb.com/docs/manual/core/wiredtiger/) |
| 读关注 / 写关注 | [Read Concern](https://www.mongodb.com/docs/manual/reference/read-concern/) / [Write Concern](https://www.mongodb.com/docs/manual/reference/write-concern/) |
| 副本集协议 | [Replica Set Configuration](https://www.mongodb.com/docs/manual/reference/replica-configuration/) |
| 分片 / Zones / balancer | [Sharding](https://www.mongodb.com/docs/manual/sharding/) |
| 事务 | [Transactions](https://www.mongodb.com/docs/manual/core/transactions/) |
| 变更流 | [Change Streams](https://www.mongodb.com/docs/manual/changeStreams/) |
| 聚合 | [Aggregation](https://www.mongodb.com/docs/manual/aggregation/) |
| 安全 / TLS / SCRAM | [Security](https://www.mongodb.com/docs/manual/security/) |
| 加密（含 Queryable Encryption） | [Encryption](https://www.mongodb.com/docs/manual/core/security-encryption/) |

---

## 跨版本主题速查（避免重复阅读各章）

| 主题 | 建议动作 |
|------|----------|
| 存储引擎 | 3.x 起重点关注 WiredTiger；升级时核对 `storage.engine` 与数据目录兼容性。 |
| 事务 | 4.0 副本集多文档事务 → 4.2+ 分片场景扩展；应用与驱动需对齐。 |
| 读Concern / 写Concern | 与因果一致性、多数派读写相关，跨版本语义有增量调整，以手册为准。 |
| 分片键与 balancer | 5.x 起 **refineShardKey**、**reshard** 等能力减轻分片键固化问题，具体操作以官方文档为准。 |
| 变更流（Change Streams） | 跨版本 API 与集群范围有演进，升级后需回归依赖变更流的应用。 |
| 客户端 | **mongo shell → mongosh**；旧 shell 已弃用，与入门文档一致。 |

---

## 升级前检查清单（通用）

1. 阅读目标版本的 **Release Notes** + **Compatibility Changes**。  
2. 在测试环境跑通：**备份 → 升级 → 验活（读写、副本集/分片状态）→ 应用回归**。  
3. 核对 **featureCompatibilityVersion（FCV）** 升级步骤（若适用）。  
4. 核对 **驱动与 BI/工具链** 的兼容性矩阵。  
5. 在蓝鲸 DBM 中：介质包是否已上架、升级链是否包含目标主次版本，见 API 文档与运维指南「版本与介质」一节。

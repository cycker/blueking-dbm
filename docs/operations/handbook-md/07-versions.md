# 第 7 章 · MongoDB 2.4 ~ 8.0 版本特性概览（运维向）

> 按主次版本线归纳对**运维、备份回档、升级、安全、存储与复制/分片**影响较大的变化，帮助你建立「大版本差异」心智，规避升级踩坑。

---

## 7.0 文首必读 ⚠ 重要

| 主题 | 说明 |
| --- | --- |
| ⛔ **EOL 警示** | MongoDB **2.4 ~ 4.0 及更早系列已 EOL**（生命周期结束）。老版本描述**仅作迁移与读史**，**禁止**在新环境部署。 |
| 📚 **事实来源** | 特性与兼容性以 **MongoDB 官方手册 Release Notes / Compatibility Changes** 为准。定制发行版以厂商说明为准。 |
| 🔗 **与蓝鲸 DBM 关系** | 「可升级版本列表」由介质包 + `MONGODB_MAJOR_MINOR_UPGRADE_CHAIN` 决定。**平台允许 ≠ 全部历史特性**。 |
| 📝 **维护方式** | 本章仅列**少量代表项**；细节、小版本补丁与弃用时间表请以官方 Release Notes 为准。 |

---

## 7.1 官方 Release Notes 索引（建议收藏）

| 状态 | 版本 | 链接 | 关键词 |
| --- | --- | --- | --- |
| 🟣 最新 | **8.0** | [release-notes/8.0](https://www.mongodb.com/docs/manual/release-notes/8.0/) | 性能扩展 · Queryable Encryption |
| 🟢 维护中 | **7.0** | [release-notes/7.0](https://www.mongodb.com/docs/manual/release-notes/7.0/) | Backward Incompatible Changes |
| 🟢 维护中 | **6.0** | [release-notes/6.0](https://www.mongodb.com/docs/manual/release-notes/6.0/) | 查询计划器 / 时序聚合 |
| 🟡 已老 | **5.0** | [release-notes/5.0](https://www.mongodb.com/docs/manual/release-notes/5.0/) | Time Series · live resharding |
| 🟡 已老 | **4.4** | [release-notes/4.4](https://www.mongodb.com/docs/manual/release-notes/4.4/) | hedged reads · hidden indexes |
| 🔴 EOL | **4.2** | [release-notes/4.2](https://www.mongodb.com/docs/manual/release-notes/4.2/) | 通配符索引 · 分片事务 |
| 🔴 EOL | **4.0** | [release-notes/4.0](https://www.mongodb.com/docs/manual/release-notes/4.0/) | 副本集多文档事务 |
| 🔴 EOL | **3.6** | [release-notes/3.6](https://www.mongodb.com/docs/manual/release-notes/3.6/) | Change Streams · retryable writes |
| — | 3.0 / 3.2 / 3.4 等 | [release-notes 总目录](https://www.mongodb.com/docs/manual/release-notes/) | 官方 Release Notes 总目录 |

---

## 7.2 2.4 ~ 4.x 版本线（EOL 区段，仅作读史）🔴 EOL

### 🔴 2.4 ~ 3.0 — EOL

- **存储**：长期以 **MMAPv1** 为主；**WiredTiger** 在 3.0 作为可选引擎引入。
- **复制集**：副本集能力逐步成熟（选举、多数派语义随版本演进）。
- **查询与索引**：文本索引、地理空间能力在 2.x ~ 3.0 期间逐步扩展。

### 🔴 3.2 — EOL · [官方 ↗](https://www.mongodb.com/docs/manual/release-notes/3.2/)

- **存储引擎**：新部署默认 **WiredTiger**。
- **索引**：引入 **partial index（部分索引）**。
- **运维**：`mongo` shell 仍为主流；后续逐步过渡到 **mongosh**。

### 🔴 3.4 — EOL · [官方 ↗](https://www.mongodb.com/docs/manual/release-notes/3.4/)

- **数据类型**：**Decimal128** 满足金融等精确小数场景。
- **排序与比较**：**Collation** 可在集合 / 索引 / 查询层统一语言规则。
- **聚合**：**`$facet`** 等阶段增强。
- **读 Concern**：**linearizable** 等强一致读语义。

### 🔴 3.6 — EOL · [官方 ↗](https://www.mongodb.com/docs/manual/release-notes/3.6/)

- **变更流（Change Streams）**：对集合 / 库 / 部署提供有序变更订阅。
- **可重试写入（retryable writes）**：网络闪断时由驱动自动重试。
- **arrayFilters**：使多元素定位更新更可控。
- **安全**：SCRAM 认证与 TLS 配置持续强化。

### 🔴 4.0 — EOL · [官方 ↗](https://www.mongodb.com/docs/manual/release-notes/4.0/)

- **多文档事务（副本集）**：跨文档 ACID 能力。
- **聚合**：**`$lookup`** 与 **`$convert`** 等增强。
- **升级路径**：从 3.6 升级通常需**二进制升级 + FCV 分步**，勿跳步。

### 🔴 4.2 — EOL · [官方 ↗](https://www.mongodb.com/docs/manual/release-notes/4.2/)

- **通配符索引（wildcard index）**。
- **聚合 `$merge`**：常用于 ETL / 物化视图类流水线。
- **分布式多文档事务**：扩展至**分片集群**。
- **客户端字段级加密（FLE）**：在驱动侧完成加解密。

### 🟡 4.4 — 已老 · [官方 ↗](https://www.mongodb.com/docs/manual/release-notes/4.4/)

- **对冲读（hedged reads）**：跨地域读延迟优化潜力。
- **流式复制（streamable oplog cursor）**：副本集同步路径优化。
- **隐藏索引（hidden indexes）**：对规划器不可见但仍维护，适合「生产验证索引收益」。
- **聚合 `$unionWith`**：跨集合管道组合。

---

## 7.3 5.0 ~ 8.0 版本线（维护中）🟢 推荐

### 🟡 5.0 — 已老 · [官方 ↗](https://www.mongodb.com/docs/manual/release-notes/5.0/)

- **时间序列集合（Time Series）**：监控与 IoT 类高写场景专用。
- **版本化 API（Versioned API）**：减轻升级对应用的影响。
- **分片**：**live resharding / reshardCollection** 减轻分片键选错的迁移成本。
- **FCV 升级**：`featureCompatibilityVersion` 升级步骤明确，前后务必备份。

### 🟢 6.0 — 维护中 · [官方 ↗](https://www.mongodb.com/docs/manual/release-notes/6.0/)

- **查询与索引计划器**：升级后建议抓**慢查询 + explain** 做回归。
- **时序与聚合**：报表与归档任务需回归。
- **安全与默认行为**：默认绑定、日志与弃用项以 Compatibility 为准。
- **Atlas Search** 等周边能力需单独核对版本矩阵。

### 🟢 7.0 — 维护中 · [官方 ↗](https://www.mongodb.com/docs/manual/release-notes/7.0/)

- **Backward Incompatible Changes**：升级前主检查清单（驱动、配置、脚本、监控）。
- **性能与可观测性**：监控指标与日志字段可能有增减，Prometheus / Grafana 采集规则需回归。
- **分片与副本集**：路由、选举与 balancer 参数若有弃用，以 Release Notes 为准替换。

### 🟣 8.0 — 最新 · [官方 ↗](https://www.mongodb.com/docs/manual/release-notes/8.0/)

- **性能与扩展**：吞吐、复制与扩展效率方向改进；具体数值以 Release Notes 为准。
- **Queryable Encryption**：服务端查询与加密组合能力持续演进。
- **升级核对**：驱动、FCV、config server 拓扑、备份 / 回档工具与 DBM 介质是否覆盖目标版本。

---

## 7.4 按主题查阅官方手册（横向速查）

| 主题 | MongoDB Manual 入口 |
| --- | --- |
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

## 7.5 跨版本主题速查

| 主题 | 建议动作 |
| --- | --- |
| 存储引擎 | 3.x 起重点关注 WiredTiger；升级时核对 `storage.engine` 与数据目录兼容性。 |
| 事务 | 4.0 副本集多文档事务 → 4.2+ 分片场景扩展；应用与驱动需对齐。 |
| 读 / 写 Concern | 与因果一致性、多数派读写相关，跨版本语义有增量调整。 |
| 分片键与 balancer | 5.x 起 **refineShardKey**、**reshard** 等能力减轻分片键固化问题。 |
| 变更流（Change Streams） | 跨版本 API 与集群范围有演进，升级后需回归依赖变更流的应用。 |
| 客户端 | **mongo shell → mongosh**；旧 shell 已弃用。 |

---

## 7.6 升级前检查清单（通用） ✅ Checklist

1. **阅读 Release Notes**
   - 目标版本的 **Release Notes** + **Compatibility Changes** 全文细读。
2. **测试环境演练**
   - **备份 → 升级 → 验活**（读写、副本集 / 分片状态）**→ 应用回归**。
3. **核对 FCV 步骤**
   - 核对 `featureCompatibilityVersion` 升级步骤（若适用）。
4. **核对驱动与工具链**
   - 驱动、BI / 工具链兼容性矩阵全部核对一遍。
5. **DBM 介质核对**
   - 介质包是否已上架、升级链是否包含目标主次版本，见 [第 3 章 · 首次部署](03-first-deploy.md)。

---

📖 **导航**：[← 第 6 章 · bk-dbmon](06-bk-dbmon.md) ｜ [📚 返回首页](README.md) ｜ [第 8 章 · MongoDB 工具集 →](08-mongo-tools.md)

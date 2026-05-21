# 第 7 章 · MongoDB 2.4 ~ 8.0 版本特性概览（运维向）

> 按主次版本线归纳对**运维、备份回档、升级、安全、存储与复制/分片**影响较大的变化，帮助你建立「大版本差异」心智，规避升级踩坑。

---

## 7.0 文首必读 ⚠ 重要

| 主题 | 说明 |
| --- | --- |
| ⛔ **EOL 警示** | MongoDB **2.4 ~ 4.0 及更早系列已 EOL**（生命周期结束）。老版本描述**仅作迁移与读史**，**禁止**在新环境部署。 |
| 📚 **事实来源** | 特性与兼容性以 **MongoDB 官方手册 Release Notes / Compatibility Changes** 为准。定制发行版以厂商说明为准。 |
| 🔗 **与蓝鲸 DBM 关系** | 「可升级版本列表」由介质包与平台升级链决定。**平台允许 ≠ 全部历史特性**。 |
| 🛡️ **DBA 版本策略** | **一般不建议业务方自行推动或随意申请大版本升级**（此处指主次版本 **x.y**，如 4.4 → 5.0、5.0 → 6.0，**不含**同一 x.y 线下的补丁 **x.y.z**）。须在评估驱动/工具链、FCV、备份回档与回滚方案后，由 **DBA + 平台工单** 统一排期实施；EOL 强制迁移、安全漏洞等除外。 |
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

#### 2.4 存量 · GCS 平台（尚未迁入 DBM）

> 📌 **现网说明**  
> 除已纳入 **蓝鲸 DBM** 的集群外，**GCS（旧游戏云 / 存量平台）上仍有一部分 MongoDB 2.4 实例尚未迁移到 DBM**。  
> 这类实例**不能**按本手册中「DBM 工单 + dbactuator + bk-dbmon」路径理解运维，排障与变更仍以 **GCS 单据 / 平台能力** 为主。

| 维度 | GCS 存量 2.4 | 已迁入 DBM 的集群 |
| --- | --- | --- |
| **配置形态** | 多为 INI `logpath` / `nssize` 等（见 [第 9 章 · 日志 §9.3](09-mongodb-logs.md)） | 3.0+ YAML `mongod.conf`，由 dbconfig 模板下发 |
| **部署 / 扩容** | GCS 安装、单进程回档等单据 | `MONGODB_REPLICASET_APPLY` 等 DBM 工单（见 [第 4 章 §4.1](04-tickets.md#41-部署与生命周期6-项)；节点本地目录形态见 [第 3 章](03-first-deploy.md)） |
| **备份回档** | GCS 全量 / 部分回档流程 | bk-dbmon + mongo-toolkit / 工单回档（[第 6 章](06-bk-dbmon.md)、案例 #17） |
| **版本策略** | **禁止新装 2.4**；存量只做收缩与迁移 | 新环境走 DBM 支持版本（通常 ≥ 4.x） |

**运维建议**：

1. **识别归属**：接单先确认集群在 **GCS 还是 DBM**（域名、工单入口、监控标签），避免把 DBM 操作手册套在 GCS 实例上。
2. **规划迁出**：2.4 已 EOL，无安全补丁；优先评估 **logical 迁移**（`mongodump`/`mongorestore` 或业务双写切换）到 DBM 上新版本副本集，而非在 GCS 上原地升大版本。
3. **已知踩坑**：namespace 过多与 `nssize`、MMAPv1 复制异常等见 [第 12 章 · 案例 #14](12-cases.md)；GCS 安装 / 回档单据见案例 **#22、#23**。
4. **与本章关系**：下文 2.4 特性描述用于**读史与迁移评估**；**§7.6 升级清单、§7.7 驱动说明**面向 DBM 纳管后的目标版本，不直接适用于 GCS 上未迁移的 2.4 实例。

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

> ⚠️ **DBA 惯例**：**不建议**为「追新特性」或未经评估的需求做 **x.y 大版本**（主次版本）升级；业务侧应优先稳定运行，补丁级（**x.y.z**）修复在风险可控时再议。确需跨 x.y 时，走 DBM **版本升级类工单**，勿在实例上手工换包。

1. **阅读 Release Notes**
   - 目标版本的 **Release Notes** + **Compatibility Changes** 全文细读。
2. **测试环境演练**
   - **备份 → 升级 → 验活**（读写、副本集 / 分片状态）**→ 应用回归**。
3. **核对 FCV 步骤**
   - 核对 `featureCompatibilityVersion` 升级步骤（若适用）。
4. **核对驱动与工具链**
   - 驱动、BI / 工具链兼容性矩阵全部核对一遍。
5. **DBM 介质核对**
   - 介质包是否已上架、升级链是否包含目标主次版本，以平台「DBM 介质管理」为准（参见 [第 6 章 §6.2](06-bk-dbmon.md) 介质下发说明）。

---

## 7.7 MongoDB 客户端驱动（Client Driver）版本说明

应用连接 MongoDB 使用的是 **各语言官方 Driver**（或基于 Driver 的 ODM/框架），与 **mongosh**、**Database Tools**（`mongodump` 等）不是同一套组件。升级 Server 大版本时，**必须单独核对驱动兼容矩阵**，不能只看 DBM 介质是否支持。

### 7.7.1 三类「客户端」别混用

| 类型 | 代表 | 用途 | 版本对照对象 |
| --- | --- | --- | --- |
| **应用 Driver** | Java Sync、PyMongo、Node.js Driver、Go Driver … | 业务代码读写 MongoDB | [Driver Compatibility](https://www.mongodb.com/docs/drivers/compatibility/) |
| **Shell** | **mongosh**（`mongo` 已弃用） | 运维交互、脚本 | [mongosh 兼容说明](https://www.mongodb.com/docs/mongodb-shell/#compatibility)（支持 3.6+ Server） |
| **Database Tools** | `mongodump` / `mongorestore` / `mongoexport` … | 备份、迁移、批处理 | 工具主版本 ≥ Server 大版本更稳妥，见 [第 8 章](08-mongo-tools.md) |

### 7.7.2 选型原则（运维给研发的检查项）

1. **以官方矩阵为准**：各驱动文档中的 **「Compatibility」** 表列出「Driver 版本 × Server 版本」；升级前在测试环境用**目标 Server 版本**跑一轮读写、事务、Change Stream（若使用）。
2. **驱动大版本跟 Server 大版本走**：Server 4.2 → 4.4 → 6.0 每跨一档，至少确认驱动 Release Notes 无 **Breaking Change**（如默认 `retryWrites`、TLS、OCSP、SRV 等）。
3. **同一应用内只保留一条驱动栈**：例如 Java 不要混用已废弃的 **`mongo-java-driver`（legacy）** 与 **`mongodb-driver-sync` 4.x+**；Python 区分 **PyMongo** 与 **Motor**（异步封装，底层仍受 PyMongo 版本约束）。
4. **框架版本 = 驱动版本 + 一层**：Spring Data MongoDB、Mongoose、ODM 等需同时满足其对底层 Driver 的最低要求。
5. **功能开关与 Server 对齐**：`retryWrites`、`retryReads`、事务、Change Streams、Versioned API（5.0+）等，旧驱动连接新 Server 可能**静默降级**或运行时报错。

### 7.7.3 按 Server 大版本：驱动最低档参考（速查）

> 下表为 **运维沟通用的起点**，不是替代官方矩阵。具体小版本、语言、同步/异步分支以各驱动 Compatibility 页为准（[总入口](https://www.mongodb.com/docs/drivers/compatibility/)）。

| Server | Java（Sync） | Python（PyMongo） | Node.js | Go |
| --- | --- | --- | --- | --- |
| **4.2** 🔴 EOL | 4.0+（建议 4.2+ 修 4.2.x bug） | 3.10+ | 3.5+ | 1.1+ |
| **4.4** 🟡 | 4.1+ | 3.11+ / 4.x | 3.6+ / 4.x | 1.4+ |
| **5.0** 🟡 | 4.3+ | 4.0+ | 4.0+ / 5.x | 1.8+ |
| **6.0** 🟢 | 4.8+ | 4.3+ | 5.6+ / 6.x | 1.11+ |
| **7.0** 🟢 | 4.10+ | 4.5+ | 6.x | 1.13+ |
| **8.0** 🟣 | 5.x 系列 | 4.6+ | 6.x | 2.x |

**常用官方文档入口**：

| 语言 / 组件 | 文档 |
| --- | --- |
| Java Sync Driver | <https://www.mongodb.com/docs/drivers/java/sync/current/compatibility/> |
| PyMongo | <https://www.mongodb.com/docs/drivers/pymongo/current/compatibility/> |
| Node.js Driver | <https://www.mongodb.com/docs/drivers/node/current/compatibility/> |
| Go Driver | <https://www.mongodb.com/docs/drivers/go/current/compatibility/> |
| C# / .NET Driver | <https://www.mongodb.com/docs/drivers/csharp/current/compatibility/> |
| C Driver | <https://www.mongodb.com/docs/drivers/c/current/compatibility/> |
| PHP、Rust、Ruby 等 | [Drivers 总览](https://www.mongodb.com/docs/drivers/) |

### 7.7.4 与 Server 特性绑定的驱动能力

| Server 能力 | 驱动侧要求（概念） |
| --- | --- |
| **Retryable writes**（3.6+） | 驱动默认开启 `retryWrites`（Java 4.x+、PyMongo 3.11+ 等）；主从切换相关，见 [第 11 章](11-uri-readpref.md) |
| **多文档事务**（4.0+ 副本集，4.2+ 分片） | 驱动 4.x 档 + 会话 API；分片事务还需 mongos 路由 |
| **Change Streams**（3.6+） | 驱动需实现 Change Stream API；升级后回归消费端 |
| **Versioned API**（5.0+） | 驱动显式声明 `serverApi`；未声明则按传统命令交互 |
| **Queryable Encryption / FLE**（4.2+ FLE，8.0 QE 演进） | **必须**使用支持加密功能的驱动版本 +  mongocryptd / crypt_shared 等旁路组件 |
| **SCRAM-SHA-256**（4.0+ 默认倾向） | 旧驱动若仅 SHA-1，需在 Server 或账号侧兼容配置（新环境不推荐） |

### 7.7.5 升级 Server 时的驱动检查清单

1. 在 [Compatibility](https://www.mongodb.com/docs/drivers/compatibility/) 查到 **目标 Server 行** 对应的 **最低驱动版本**。
2. 阅读驱动该大版本的 **Release Notes / Upgrade Guide**（API 删除、默认 URI 参数变化）。
3. 在测试环境验证：**连接串**（`replicaSet`、`authSource`、`readPreference`）、**事务**、**聚合管道**、**批量写**、**Change Stream**（如有）。
4. 观察应用日志是否出现 **`not primary`**、**`KeyNotFound` 211**、**`Wire version`** 等（部分与驱动过旧或角色配置有关，案例见 [第 12 章](12-cases.md)）。
5. 与 [§7.6 升级前检查清单](#76-升级前检查清单通用--checklist) 合并执行，勿只做二进制升级不做应用回归。

### 7.7.6 蓝鲸 DBM 现网额外注意

| 场景 | 说明 |
| --- | --- |
| **Java monitor 线程** | 旧版 **mongo-java-driver** 对分片 / 认证行为与 4.2.x 组合有已知问题；建议统一到 **MongoDB Java Driver 4.x+**，并避免业务账号绑定 `anyResource + anyAction`（案例 #04） |
| **连接串** | 副本集务必带 `replicaSet`；从读需 `readPreference`；详见 [第 11 章](11-uri-readpref.md) |
| **平台账号** | 通过 DBM 下发的 `app` / `monitor` 等账号，应用应使用**业务专用账号**，不要用带过高权限的模板账号连库 |
| **运维脚本** | 值班脚本优先 **mongosh**；批备、回档用 **Database Tools**，版本要求见 [第 8 章](08-mongo-tools.md) |

---

📖 **导航**：[← 第 6 章 · bk-dbmon](06-bk-dbmon.md) ｜ [📚 返回首页](README.md) ｜ [第 8 章 · MongoDB 工具集 →](08-mongo-tools.md)

# 第 2 章 · 蓝鲸 DBM 中的集群形态

平台支持两类 MongoDB 集群类型，对应 `ClusterType` 中的两个常量。本章帮助你**把 UI 字段、代码常量和真实拓扑对应起来**，便于在控制台一眼看懂角色分布。

---

## 2.1 类型一：MongoReplicaSet（副本集集群）

典型副本集拓扑（蓝鲸 DBM **现网最常见**）：**m1 + m2 + backup** 三节点 PSS——**m1、m2 的 `priority` 同时为 1**，均可参与选主、均可承接读；**backup 为 `priority = 0` 且 `hidden = true`**，永不当选 Primary，专跑日常备份。

```
         ┌─────────────────────┐         ┌─────────────────────┐
         │  m1 · mongod        │         │  m2 · mongod        │
         │  priority = 1       │◄───────►│  priority = 1       │
         │  hidden = false     │  选举   │  hidden = false     │
         │  （运行时其一为      │  心跳   │  （均可当选 Primary）│
         │   Primary）         │         │                     │
         └──────────┬──────────┘         └──────────┬──────────┘
                    │         oplog 复制            │
                    └──────────────┬────────────────┘
                                   ▼
                    ┌─────────────────────┐
                    │  backup · mongod    │
                    │  priority = 0       │
                    │  hidden = true      │
                    │  仅备份 · 不当主     │
                    └─────────────────────┘
```

> 🛡 **部署原则（蓝鲸 DBM 默认规范）**
>
> 除单节点测试场景外，**生产副本集至少 3 节点**：**m1、m2**（`priority=1`）+ **backup**（`priority=0`）。  
> 平台初始化逻辑（`get_replicaset_init_kwargs`）对**除最后一个成员外**均赋 `priority=1`，**最后一个成员**（对应 `backup` 槽位）赋 `priority=0` + `hidden=true`。

> 📌 **元数据角色名 vs MongoDB 运行时 Primary**
>
> - DBM 控制台里 **m1** 常标为「主」、**m2** 标为「从」，这是**命名槽位 / 域名规划**（`m1.*.db` 等多作集群入口），**不等于** m1 的 `priority` 必须高于 m2。
> - **现网标准配置下 m1、m2 的 `priority` 均为 1**，谁当 Primary 由副本集**选举**决定；故障切换后 Primary 可能在 m1 或 m2 上。
> - 首次 `rs.initiate` 时，执行 init 的节点可能**临时**被脚本 `priority+1` 以稳定首次选主（`initiate_replicaset`）；稳态配置仍以平台下发的 **m1/m2=1、backup=0** 为准。

### 节点角色矩阵（三节点标准形态）

| DBM 槽位 | MongoDB 运行时角色 | 典型 `priority` / `hidden` | 说明 |
|----------|-------------------|---------------------------|------|
| **m1** | Primary 或 Secondary | `1` / `false` | 与 m2 **同权**选主；产生或回放 oplog；可写（当其为 Primary 时） |
| **m2** | Primary 或 Secondary | `1` / `false` | 与 m1 **同权**选主；可承接 `readPreference=secondary` 读 |
| **backup** | Secondary（备份专用） | `0` / `true` | **永不当选 Primary**；客户端路由不可见；bk-dbmon 在此节点跑 mongodump |

| 抽象角色 | 关键属性 | 说明 |
|----------|----------|------|
| **可选举成员**（m1、m2） | `priority = 1` · `votes = 1` · `hidden = false` | 参与选举；任一可成为 Primary |
| **Backup 成员** | `priority = 0` · `votes = 1` · `hidden = true` | 仅复制 + 备份，不抢主、不承接业务读 |

### 关键属性

- 常量：`MongoReplicaSet`
- 访问入口：通常以 **主域名 / cluster_entry** 暴露；连接串可包含 `replicaSet` 参数。
- 适用：数据量与写入可在单集群「多副本」满足时优先选用。
- 容灾：3 节点架构允许任意 1 节点宕机仍可正常读写；如需更高可用性可扩展至 5/7 节点（奇数）。

> ⚠ **为什么 backup 节点要 priority=0？**
>
> 备份过程会消耗大量磁盘 IO 与 CPU。如果 backup 节点保留选主资格，一旦 Primary 故障被选为新主，正在执行的备份任务会与突增的线上流量竞争资源，导致业务抖动。`priority=0` 从制度上杜绝了这一风险。

---

## 2.2 节点命名规范

蓝鲸 DBM 在元数据层为副本集每个成员定义了固定的**角色名（instance_role）**与**子域名前缀**，二者一一对应。代码常量见：

- `backend/db_meta/enums/instance_role.py` 中的 `InstanceRole`
- `backend/flow/consts.py` 中的 `MongoDBDomainPrefix`

```
m1 (Primary)  m2 (Secondary)  m3 (Secondary)  m4..m10 (扩展位)  backup (备份从)
```

| 角色名 | InstanceRole 常量 | 子域名前缀 | 典型 priority | 说明 |
|--------|-------------------|------------|---------------|------|
| `m1` | `MONGO_M1` | `m1.<set>.<app>.db` | **1** | 规划上的「主」槽位；**与 m2 同 priority**，运行时谁为 Primary 由选举决定 |
| `m2 ~ m10` | `MONGO_M2 ~ MONGO_M10` | `m{2..10}.<set>.<app>.db` | **1**（可选举成员） | 普通从节点，可被选主、可承接读；`m4~m10` 为扩展位（5/7/9 节点架构） |
| `backup` | `MONGO_BACKUP` | `backup.<set>.<app>.db` | **0** | `hidden=true`，专跑日常备份，不参与选主 |

> 📌 **命名约束**
> - 当前 DBM 每个副本集**最多支持 11 个成员**：`m1 + m2~m10 + backup`，对应 `calculate_cluster.py` 中 `domain_prefix` 的 11 个槽位。
> - 子域名前缀和角色名严格一一对应，**不可自定义**；例如不能把 `m3` 写成 `m_3` 或 `node3`。
> - 分片集群的 shard 内部同样沿用这套命名（每个 shard 是一个独立副本集）；config server 副本集成员同样用 `m1/m2/m3/backup`。
> - 分片集群的接入层 `mongos` 不属于副本集成员，使用独立子域名 `mongos.<cluster>.<app>.db`。

---

## 2.3 按节点数量分类的部署形态

同一套命名规则下，副本集会根据节点数量呈现三类形态。生产场景**必须**选用 3 节点及以上方案。

### ① 单节点（Standalone）— 仅测试 / POC

仅 1 个 mongod 实例，**没有高可用、没有数据冗余**。DBM 中通过集群标签 `single_node:true` 标识，巡检会跳过成员数检查。

```
┌──────────────┐
│ m1 (Primary) │
└──────────────┘
```

- 计费用最低，但宕机即整集群不可用
- **禁止**承载生产业务，不跑日常备份
- 典型用途：开发联调、临时压测环境

> 🏷 标签：`无 backup 节点` · ⚠ `不可生产`

### ② 三节点 PSS（推荐）— 生产标准最小部署

蓝鲸 DBM **默认且推荐**的副本集形态：**m1 + m2 + backup**（允许 1 节点宕机仍可读写）。

```
m1 (priority=1)  ─  m2 (priority=1)  ─  backup (priority=0, hidden)
        └──────── 二者均可当选 Primary ────────┘
```

| 成员 | priority | hidden | 说明 |
|------|----------|--------|------|
| m1 | **1** | false | 与 m2 同权；常为集群入口域名所在槽位 |
| m2 | **1** | false | 与 m1 同权；故障时可接替 Primary |
| backup | **0** | true | 仅备份；bk-dbmon 只在此节点发起 mongodump |

- 选举仲裁需要奇数票，3 节点天然满足（m1、m2、backup 各 1 票）
- **不要**误以为必须「m1 priority 高于 m2」；现网以 **双 1 + backup 0** 为主
- 巡检要求：`set` 至少 3 个成员（`check_affinity` 中 `min_members=3`）

> 🏷 标签：✅ `高可用` · ✅ `日常备份` · `性价比最佳`

### ③ 多节点（5/7/…，最大 11）— 读扩展 / 跨城多副本

在 3 节点基础上扩容至 **5 / 7 / 9 / 11** 个成员（建议奇数），增加只读副本承接读流量或满足跨城容灾。

```
m1  m2  m3  m4  ……  backup
```

- 新增成员依次占用 `m4 → m10` 槽位；`backup` 始终保留 1 个
- 票数过多会增加选举开销，非必要不建议超过 7 节点
- 跨城副本可设 `priority=0 + hidden=true` 仅作灾备从

> 🏷 标签：`读扩展` · `跨城容灾` · ⚠ `上限 11`

> ⚠ **蓝鲸 DBM 的硬性约束**
> - 副本集成员数最多 **11 个**（`m1~m10` + `backup`），由代码 `domain_prefix` 数组写死。
> - 除带 `single_node:true` 标签的测试集群外，每个副本集 / shard **必须 ≥ 3 个**成员，且至少包含 1 个 `backup` 节点。
> - 分片集群中 `mongos` 接入层至少 **2 个**实例（`min_members=2`），避免单点。故障 mongos 可由 **DBHA** 从 DNS/CLB 摘除，详见 [第 14 章](14-dbha-autofix.md)。

---

## 2.4 类型二：MongoShardedCluster（分片集群）

由 **3 类角色** 协同工作：

```
            ┌─────────────┐    ┌─────────────┐
            │  mongos #1  │    │  mongos #2  │   路由 / 接入层
            └──────┬──────┘    └──────┬──────┘
                   └──────────┬───────┘
                              ▼
                   ┌──────────────────────┐
                   │ config server (RS)   │   元数据 / chunk 路由
                   └──────────┬───────────┘
                              ▼
       ┌──────────────┬──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
 ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
 │ Shard 1  │   │ Shard 2  │   │   ...    │   │ Shard N  │
 │  (RS)    │   │  (RS)    │   │          │   │  (RS)    │
 └──────────┘   └──────────┘   └──────────┘   └──────────┘
```

- 常量：`MongoShardedCluster`
- 每个 shard 通常本身就是一个 **副本集**，配合 config server 提供高可用 + 横向扩展。
- 适用：单集群容量 / 写入需多分片线性扩展时。

> ⚠ **选型不确定时的建议**
>
> 优先选 **副本集**；确需水平分片再迁分片集群。详见 [§3.3 选型决策](./03-first-deploy.md)。

---

## 2.5 Shard Key（分片键）

**Shard Key** 是分片集群最重要的设计点：MongoDB 根据集合的分片键把文档划分为多个 **chunk**，再把 chunk 分布到不同 shard。选错 shard key，会直接影响写入是否打满单 shard、查询是否 scatter-gather、后续扩容是否均衡。

### 基本概念

| 概念 | 说明 |
|------|------|
| **Shard Key** | 一个字段或复合字段，例如 `{ user_id: 1 }`、`{ tenant_id: 1, created_at: 1 }` |
| **Chunk** | 按 shard key 范围切出来的数据区间，是 balancer 迁移的基本单位 |
| **Balancer** | 在 shard 间迁移 chunk，让数据和负载尽量均衡；迁移会带来 IO / 网络 / 锁等待等额外开销 |
| **Targeted Query** | 查询条件包含 shard key，`mongos` 能定位到少数 shard |
| **Scatter-Gather** | 查询条件不含 shard key，`mongos` 需要广播到多个 shard，延迟和资源消耗更高 |

### 常见分片键类型

| 类型 | 例子 | 适合场景 | 风险 |
|------|------|----------|------|
| **范围型** | `{ user_id: 1 }` | 常按区间查询，且 key 分布较均匀 | 单调递增字段（如纯时间、自增 ID）容易写热点 |
| **哈希型** | `{ user_id: "hashed" }` | 写入分布优先，按等值查询为主 | 范围查询无法天然按区间命中 |
| **复合型** | `{ tenant_id: 1, user_id: 1 }` | 多租户、业务维度明确 | 前缀字段低基数会造成大租户热点 |

### 选择原则

1. **高基数**：取值要足够多，避免大量数据落在少数 key 上。
2. **分布均匀**：写入不能长期集中在同一个 shard。
3. **查询常带**：核心查询最好带上 shard key，减少 scatter-gather。
4. **避免纯单调递增**：如只用 `created_at`、自增 ID，新增数据容易持续打到最后一个 chunk。
5. **和唯一约束一起设计**：分片集合上的唯一索引通常需要包含 shard key，否则约束语义会受限。

### Scatter-Gather是什么

在分片集群里，`mongos` 负责根据查询条件决定请求发到哪些 shard。如果查询条件包含 shard key，`mongos` 通常可以定位到一个或少数 shard，这叫 **Targeted Query**。当一个查询无法通过分片键或索引直接定位到具体的某个 shard 时，路由节点就会采用 **Scatter-Gather**：

- **Scatter（分散）**：把查询请求同时发送到所有相关 shard 上。
- **Gather（聚集）**：等待各 shard 返回结果后，由 `mongos` 汇总、排序和合并，最后返回给客户端。

```javascript
// 推荐：带 shard key，mongos 可以按 user_id 路由到目标 shard
db.orders.find({ user_id: 10001, status: "paid" })

// 风险：不带 shard key，可能广播到所有 shard
db.orders.find({ status: "paid" })
```

| 项目 | Targeted Query | Scatter-Gather |
|------|----------------|----------------|
| 路由方式 | 命中一个或少数 shard | 广播到多个 shard |
| 资源消耗 | 只消耗目标 shard | 所有参与 shard 都要扫描/计算 |
| 延迟表现 | 通常更稳定 | 受最慢 shard 影响，容易抖动 |
| 排障信号 | 慢日志中 `nShards` 较小 | 慢日志中 `nShards` 接近 shard 总数 |

运维上看到“单个 shard 数据量不大但查询仍慢”时，要优先检查查询条件是否缺少 shard key。业务侧应尽量让核心查询带上 shard key，或让复合 shard key 的前缀字段与高频查询条件对齐。

### 当前最佳实践：hashed shard key + 关闭 balancer

蓝鲸 DBM MongoDB 分片集群的稳态建议是：**优先使用 hashed shard key，并默认关闭 balancer**。

| 项目 | 建议 | 原因 |
|------|------|------|
| **分片键类型** | 优先 `{ biz_key: "hashed" }` | 写入按 hash 均匀打散，降低单调递增字段造成的热点风险 |
| **业务查询** | 关键等值查询带上 shard key | 让 `mongos` 能 targeted routing，避免广播到所有 shard |
| **Balancer** | 稳态默认关闭 | 避免业务高峰后台 chunk migration 带来 IO、网络、锁等待和跨 shard 抖动 |
| **开启窗口** | 仅在维护窗口短期开启 | 用于扩容后重均衡、人工 chunk 迁移、系统集合初始化等受控场景 |

示例（以 `user_id` 为业务分布键）：

```javascript
sh.shardCollection("app.orders", { user_id: "hashed" })
sh.setBalancerState(false)
```

> ⚠ **为什么不是一直开 balancer？**
>
> Balancer 的目标是让 chunk 分布更均衡，但迁移本身不是“零成本”：会消耗源/目标 shard 的磁盘 IO、网络带宽和复制资源。DBM 运维侧更关注稳定性，因此建议**平时关闭**，需要均衡时在低峰/维护窗口有计划地打开。

> ⚠ **也不要永久从不打开**
>
> 某些系统集合初始化、扩容后的数据摊平、历史 chunk 倾斜修复仍然需要 balancer 或手工迁移。若看到 `config.system.sessions` 未初始化、chunk 长期倾斜等问题，应在 DBA 评估后短期开启，而不是把“关闭 balancer”理解成绝对禁用。

### Balancer 运维口径

| 场景 | 建议 |
|------|------|
| 新建分片集合 | 优先先定 hashed shard key；是否预拆分视版本与数据导入方式评估 |
| 日常运行 | `sh.setBalancerState(false)`，保持路由稳定 |
| 扩容 shard 后 | 低峰期短期开启或手工迁移 chunk，观察 [第 13 章](13-performance-views.md) 的 `Chunks` / `Chunks Balanced` |
| 发现 jumbo chunk | 先判断 shard key 是否导致不可拆分；不要只靠 balancer 反复重试 |
| 业务高峰 | 不建议开启 balancer，也不建议做大规模 chunk migration |

### 运维侧判断

| 现象 | 可能原因 | 建议 |
|------|----------|------|
| 某个 shard QPS / CPU 长期高于其他 shard | shard key 分布不均或热点 key | 看 [第 13 章](13-performance-views.md) 分片大盘的 `Shard Operations` / `Chunks` |
| 查询慢但单 shard 数据量不大 | 查询未带 shard key，触发 scatter-gather | 查 `mongo-log` 慢日志中的 `nShards`、`planSummary`，必要时让业务补 shard key 条件 |
| 扩容 shard 后数据没有明显摊开 | chunk 不均、jumbo chunk 或 balancer 处于关闭状态 | 维护窗口短期开启 balancer 或评估手工迁移 |
| 大租户持续打满一个 shard | 分片键前缀低基数（如只按 `tenant_id`） | 评估复合键或二级维度拆分 |

> ⚠ **DBA 提醒**
>
> Shard key 是**业务建模决策**，不是单纯的运维参数。DBM 可以部署分片集群、扩容 shard、观察 chunk / balancer 状态，但不应替业务随意决定集合分片键。生产集合分片前，建议先基于真实查询、写入分布、数据增长模型做评审。

MongoDB 5.0+ 提供 **resharding** 能力，但迁移成本仍然不低；不要把它当成“分片键选错也没关系”的兜底方案。相关排障可结合 [第 9 章慢日志](09-mongodb-logs.md) 与 [第 13 章分片大盘](13-performance-views.md)。

---

[⬅ 上一章](./01-concepts.md) ｜ [返回目录](./README.md) ｜ [下一章 ➡](./03-first-deploy.md)

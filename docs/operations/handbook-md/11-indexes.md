# 第 11 章 · MongoDB 索引设计与优化

> 索引是 MongoDB 性能优化的**第一抓手**。一条没有命中索引的全表扫描，足以让一个看似毫不起眼的 SQL 把整套副本集拖成 P0。
> 本章从 **B-Tree 物理结构 → 索引家族 → ESR 黄金法则 → explain 解读 → 真实业务踩坑** 一站式串通，所有案例均来自 IegMongoTeam 知识库与蓝鲸生产现场。

---

## 12.1 为什么必须建索引

把表想成一摞 **无序卡片**：

| 对比维度 | 📚 无索引：COLLSCAN（全表扫描） | 🌳 有索引：IXSCAN（B-Tree） |
|---|---|---|
| 算法复杂度 | **O(N)** 逐张翻牌 | **O(log N)** 千万行 4~5 层定位 |
| 千万级查询 | 需扫 1000 万次 | 通常 <1 ms |
| 资源消耗 | CPU、内存（page-in WT cache）、IO 全吃 | 叶子节点存「`indexedField` → `RecordId`」对，命中后再 FETCH 文档 |
| 底层结构 | — | WiredTiger 维护 B-Tree（默认 B+Tree 变体） |

### 一个直观对比

```javascript
// mongosh
// 假设 cmdb.cc_HostBase 共 345209 行
db.cc_HostBase.find({ bk_agent_id: "02000..." }).explain("executionStats")
// 无索引：
//   stage: "COLLSCAN", docsExamined: 345209, executionTimeMillis: 1457
// 有索引（IXSCAN）：
//   stage: "FETCH" -> "IXSCAN", keysExamined: 1, docsExamined: 1, time: 0~3ms
```

> 💡 **建索引的代价**
> ① 写入额外维护索引页 → INSERT/UPDATE 变慢；
> ② 占用磁盘（每个索引一份独立 B-Tree）；
> ③ WiredTiger Cache 中索引也要常驻热数据。
> 所以「**有用就建、无用即删**」是铁律，不要无脑加。

---

## 12.2 索引家族全景

MongoDB 把索引按**结构**与**修饰属性**两条线划分，下表是蓝鲸场景下最常见的 12 种。

| 类型 | 起始版本 | 说明 |
|---|---|---|
| 🔑 **Single Field** | v1.0+ | 最基础的单字段索引，`{ field: 1 }` 升序、`-1` 降序。`_id` 默认就是单字段唯一索引。 |
| 🧩 **Compound 复合索引** | v1.0+ | 多字段联合：`{ a:1, b:1, c:-1 }`。顺序敏感，遵循 **ESR 法则**（见 12.4）。 |
| 🪢 **Multikey 数组索引** | v1.0+ | 字段为数组时自动展开建索引；**每个数组元素一条索引项**，膨胀风险大。 |
| 📝 **Text 全文索引** | v2.4+ | `{ content: "text" }`，支持分词与权重；同一集合**只能有一个**。 |
| 🗺 **2dsphere 地理索引** | v2.4+ | GeoJSON 经纬度球面索引，`$near / $geoWithin` 查询必备。 |
| 🎯 **Hashed Index** | v2.4+ | Hash(field) 建索引，**分片键打散**常用；不支持范围查询。 |
| 🧤 **Partial 部分索引** | v3.2+ | `partialFilterExpression` 只对满足条件的文档建索引；**查询条件必须重复表达式**才能命中（见 12.7 案例）。 |
| 🚿 **Sparse 稀疏索引** | v1.8+ | 字段不存在的文档不入索引；**大多数场景已被 Partial 取代**。 |
| 🦋 **Wildcard Index** | v4.2+ | `{ "$**": 1 }` 对任意（动态）字段建索引；**动态 Schema 救命稻草**，但代价高。 |
| ⏳ **TTL 过期索引** | v2.2+ | `expireAfterSeconds`，到点后台删除；**session/log/缓存**清理利器。 |
| 🔒 **Unique 唯一** | v1.0+ | 字段属性，可叠加在 Single/Compound 上。**分片表唯一约束需含分片键**。 |
| 🎯 **Clustered 簇集索引** | v5.3+ | `clusteredIndex: {key:{_id:1}}` 数据按 _id 物理排序；**时序集合的特殊用法**。 |

---

## 12.3 建 / 看 / 删 索引 · 速查

### 创建

```javascript
// 单字段（升序）
db.users.createIndex({ uid: 1 })

// 复合 + 命名 + 后台（4.2+ 已统一为非阻塞，参数保留兼容）
db.orders.createIndex(
  { uid: 1, status: 1, createTime: -1 },
  { name: "idx_uid_status_ts", background: true }
)

// 唯一
db.users.createIndex({ email: 1 }, { unique: true })

// Partial（只对 active=true 建索引）
db.tasks.createIndex(
  { status: 1 },
  { partialFilterExpression: { active: true } }
)

// TTL：会话超时 30 天自动删
db.sessions.createIndex({ lastSeen: 1 }, { expireAfterSeconds: 2592000 })

// Text + 权重
db.posts.createIndex(
  { title: "text", body: "text" },
  { weights: { title: 10, body: 1 }, default_language: "none" }
)
```

### 查看

```javascript
// 看所有索引
db.orders.getIndexes()

// 看大小（哪个索引最占空间）
db.orders.stats().indexSizes

// 整库索引大小
db.runCommand({ dbStats: 1, scale: 1024*1024 }).indexSize

// 索引使用统计（最关键！未使用的索引是债务）
db.orders.aggregate([{ $indexStats: {} }])

// 看某条 SQL 走哪条索引
db.orders.find({ uid:1, status:"PAID" }).explain("executionStats")
```

### 删除

```javascript
// 按名删（推荐：getIndexes 里看到的 name）
db.orders.dropIndex("idx_uid_status_ts")

// 按 spec 删
db.orders.dropIndex({ uid:1, status:1 })

// 一次性删全部（保留 _id）—— 高危，仅维护期使用
db.orders.dropIndexes()
```

### 隐藏 / 唤醒

```javascript
// 4.4+ 隐藏索引：暂不让查询计划用，但仍维护写入
// 适合「我打算删某索引但不放心」的灰度演练
db.orders.hideIndex("idx_legacy")
db.orders.unhideIndex("idx_legacy")

// 等同 collMod
db.runCommand({
  collMod: "orders",
  index: { name: "idx_legacy", hidden: true }
})
```

> 🧪 **灰度删索引最佳路径**：先 `hide` → 观察一周慢日志 → 无影响再 `dropIndex`，避免误删导致 P0。

### 重建

```javascript
// 整体重建（线上慎用，会持锁；副本集滚动 reIndex 才安全）
db.orders.reIndex()

// 标准做法：drop + create，副本集逐节点滚动
db.orders.dropIndex("idx_old")
db.orders.createIndex({ uid:1, ts:-1 }, { name: "idx_uid_ts" })
```

---

## 12.4 复合索引黄金法则 · ESR

多字段复合索引**顺序至关重要**。MongoDB 官方推荐 **ESR 顺序**：

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│      E      │ →  │      S      │ →  │      R      │
│  Equality   │    │    Sort     │    │   Range     │
│  等值匹配   │    │  排序字段   │    │  范围 / IN  │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 用一条 SQL 演示

```javascript
// 需求
db.orders.find(
  { uid: 12345, status: "PAID", amount: { $gt: 100 } }
).sort({ createTime: -1 })
```

**❌ 错误顺序 → SORT_IN_MEMORY**

```javascript
{ amount: 1, createTime: -1, uid: 1, status: 1 }
```
> 把 Range（amount）放最前，索引前缀直接被范围扫描破坏；后续 uid/status 的等值匹配也无法收敛。

**✅ ESR 顺序 → IXSCAN + 索引排序**

```javascript
{ uid: 1, status: 1, createTime: -1, amount: 1 }
```
> E（uid+status）先收敛 → S（createTime 倒序）天然有序无需 SORT 阶段 → R（amount > 100）走范围。

> ⚠ **排序方向也要匹配**
> 索引若是 `createTime: -1`，`sort({ createTime: 1 })` 也能反向扫描；
> 但 **多字段**排序方向不一致时（如 `{a:1,b:-1}`），索引顺序必须严格匹配查询。

---

## 12.5 覆盖查询 · Covered Query

当查询**所需字段全部包含**在索引内时，MongoDB 跳过 FETCH 阶段，**只扫索引**，性能极佳。

```javascript
// 索引
db.users.createIndex({ city: 1, age: 1 })

// ✅ 覆盖查询：projection 只取索引字段，并显式排除 _id
db.users.find(
  { city: "SH", age: { $gt: 18 } },
  { _id: 0, city: 1, age: 1 }
).explain("executionStats")
// stage: PROJECTION_COVERED -> IXSCAN，没有 FETCH

// ❌ 多取一个字段就破坏覆盖
db.users.find(
  { city: "SH" },
  { _id: 0, city: 1, name: 1 }   // name 不在索引里，必须 FETCH
)
```

> 🎯 **判断技巧**
> explain 里看到 `PROJECTION_COVERED` 而**没有 FETCH**，就是覆盖查询；
> `totalDocsExamined: 0` 也是同样信号。

---

## 12.6 读懂 explain 输出

慢查询排障的**第一动作**：拿到原始 SQL 加 `.explain("executionStats")` 跑一遍。

### 三种 verbosity 怎么选

| 模式 | 等价于 | 含义 | 使用场景 |
|---|---|---|---|
| `queryPlanner` | 默认 | 只给执行计划，不真跑 | 看「会走哪条索引」 |
| `executionStats` | 常用 | 真跑一次并返回统计 | 看「扫了多少键、花了多少 ms」 |
| `allPlansExecution` | 调优 | 所有候选计划都跑一遍 | 怀疑选错索引时，对比候选计划耗时 |

### 关键字段意义

**📊 查询规划区**

- `winningPlan.stage`：`COLLSCAN` = 全表，`IXSCAN` = 走索引，`FETCH` = 拿文档；理想链路 `FETCH → IXSCAN`。
- `indexName` / `keyPattern`：实际命中的索引。
- `rejectedPlans`：被淘汰的候选计划，调优可参考。
- `queryHash` / `planCacheKey`：相同查询形态的指纹，慢日志里能看到。

**⏱ 执行统计区**

- `nReturned`：实际返回行数。
- `totalKeysExamined`：扫了多少索引键。
- `totalDocsExamined`：FETCH 了多少文档。
- `executionTimeMillis`：总耗时。

> 🚨 **三个红色信号 = 该建索引**
> ① `stage: COLLSCAN`；
> ② `totalDocsExamined ≫ nReturned`（如返回 1 条扫了 30 万）；
> ③ 慢日志里出现 `SORT_KEY_GENERATOR` + `SORT`（排序无法走索引，内存排序）。
> 蓝鲸 **慢查询分析工具**（IegMongoTeam 自研）正是基于这套规则自动生成索引建议（参考 [iwiki/278981241](https://iwiki.woa.com/p/278981241)）。

### 实例：从慢日志反推 explain

```text
// 真实日志（cmdb.cc_HostBase）：
command: find { find: "cc_HostBase", filter: { bk_agent_id: "02000..." } }
planSummary: COLLSCAN
keysExamined: 0  docsExamined: 345209  nreturned: 0
queryHash: 6F57AF1A  planCacheKey: 28CE231C
1457ms

// 解读：表上明明有 bk_agent_id 唯一索引却走 COLLSCAN，
//       keysExamined=0 说明索引根本没参与，
//       立刻怀疑 partialFilterExpression / 数据类型不匹配（见 12.7 CASE-1）。
```

---

## 12.7 真实业务案例

> 以下案例全部来自 IegMongoTeam 知识库，是 SQL 命中失败的**典型陷阱**。

### CASE-1 · cmdb：partialFilter 索引未命中

```javascript
// 索引
{ key:{bk_agent_id:1}, unique:true,
  partialFilterExpression:{ bk_agent_id:{$type:"string",$gt:""} } }

// 查询
db.cc_HostBase.find({ bk_agent_id: "0200..." })
// 结果：COLLSCAN，扫 345209 行，1457ms
```

- **原因**：partialFilter 里有 `$type`，查询条件没显式声明 type 时驱动判定不匹配。
- **修复**：把查询写成 `{ bk_agent_id:{ $type:"string", $eq:"0200..." } }` 即可走 IXSCAN。
- **启示**：**partial 索引的代价是查询必须重复 filter 表达式**。线上谨慎使用，或建一份普通索引兜底。

### CASE-2 · 3.6：planCache 缓存了错的执行计划

3.6 集群上 explain 显示走对了索引，**实际执行**却没走，慢得离谱。

```javascript
// 1. 看 plan cache
db.coll.getPlanCache().listQueryShapes()
// 2. 清缓存
db.coll.getPlanCache().clear()
```

- **原因**：3.x planCache 在数据分布发生大变化时不会自动失效，老计划继续被命中。
- **启示**：批量 import / 业务数据骤变后主动 `planCache.clear()`；4.2+ 已显著改善但仍偶发。

### CASE-3 · cmdb：$or 1500 等值条件 → 10s 超时

```javascript
// 差
find({ $or:[ {ip:"a"}, {ip:"b"}, ...1500 个 ] })

// 优
find({ ip:{ $in:["a","b",...1500] } })
```

- **原因**：`$or` 多分支被规划成**多次子查询**且每个分支独立选择索引；`$in` 是一次范围扫描。
- **提速**：从 5~10s → 30ms。
- **规则**：**同字段等值集合用 $in，不同字段才用 $or**。

### CASE-4：排序内存爆炸：超过 32MB 限制

```text
// 报错
Sort operation used more than the maximum 33554432 bytes
of RAM. Add an index, or specify a smaller limit.
```

- **查询**：`find({gid:{$in:[...]}}).sort({t_42_0:1})`，无 `t_42_0` 索引。
- **修复 1（推荐）**：`db.coll.createIndex({t_42_0:1})`，让排序走索引。
- **修复 2（治标）**：调大参数 `internalQueryExecMaxBlockingSortBytes`（仅过渡）。
- **启示**：**带 sort 的查询，排序字段也属于 ESR 中的 S，必须落在索引上**。

### CASE-5：NumberLong vs Number——类型不一致让索引"形同虚设"

数据写入时是 `NumberLong("11028583789246293")`，业务用 `Number(11028583789246293)` 查询，**查不到**。索引虽然存在，但 BSON 类型不匹配 → 走索引但 keysExamined 后一条都不命中。

- **排查**：`db.coll.findOne({})` 看真实类型，或 `typeof doc.field`。
- **修复**：driver / shell 用 `NumberLong("...")` 显式构造；或用 `{$in:[ x, NumberLong(x) ]}` 兜底。
- **启示**：MongoDB 索引**区分 BSON 类型**，跟 MySQL 的隐式转换完全不同。

---

## 12.8 反模式 vs 最佳实践

### ❌ 反模式（Anti-pattern）

- 每个字段都建一条索引（"上帝索引"），写入压垮 WT cache。
- 把 **Range / 数组字段**放复合索引最前。
- 对**低基数**字段（如 status 只有 2 个值）建索引。
- 同一前缀建多条复合：`{a:1}`、`{a:1,b:1}`、`{a:1,b:1,c:1}` —— 后两者已涵盖第一者。
- 用 `$ne` / `$nin` / `$not` / 取反正则做主条件 —— 走不了索引。
- partial 索引**查询不带 filter 表达式** → 命中不了（见 CASE-1）。
- 分片表的**唯一约束不含分片键** → mongos 直接拒绝。
- 无脑 `reIndex()` 线上 → 持锁阻塞业务。

### ✅ 最佳实践

- 遵循 **ESR 法则**：等值 → 排序 → 范围。
- 能用**覆盖查询**的就建到正好覆盖，少一次 FETCH。
- 用 `$indexStats` 周期清理「**从未被使用**」的索引。
- 线上加索引：副本集 **4.2+ 默认非阻塞**，仍建议低峰执行。
- 删索引前先 `hideIndex` 灰度 1~2 周。
- 大集合的索引建议命名（`name:"idx_uid_status_ts"`），便于运维定位。
- 批量 import 后调用 `planCache.clear()` 防止脏计划。
- TTL 索引的 `expireAfterSeconds` 通过 `collMod` 在线调整，无需重建。

### 索引能力矩阵 · 一眼速查

| 索引类型 | 等值 | 范围 | 排序 | 覆盖 | 前缀匹配 | 能否唯一 |
|---|---|---|---|---|---|---|
| Single Field | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Compound（ESR） | ✓ | 部分 | ✓ | ✓ | ✓ | ✓ |
| Multikey | ✓ | 部分 | ✗ | ✗ | ✓ | 需谨慎 |
| Hashed | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Text | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 2dsphere | ✗ | ✓地理 | ✗ | ✗ | ✗ | ✗ |
| Wildcard | ✓ | ✓ | 受限 | ✗ | ✗ | ✗ |
| TTL（基于 Single） | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |

---

## 12.9 分片集群里的索引特殊性

### 🔑 分片键 = 强制索引

- shard key 必须有**对应索引**（Hashed 或 Range），否则 `shardCollection` 失败。
- 蓝鲸 GCS 工单创建分片表时会**自动建好**。

### 🚫 唯一约束 = 必含分片键

- 例：分片键 `{tenant:1}`，想保证 `email` 唯一，必须建 `{tenant:1, email:1}` 唯一索引。
- 否则 mongos 无法跨分片做全局唯一性校验。

### 📡 查询是否「定向」

- 带分片键的查询 → mongos **直接路由到目标 shard**。
- 不带 → **scatter-gather**，所有 shard 都扫一遍，索引再好也慢。
- explain 关注 `shards.{shard0,shard1,...}` 是否只有一项。

### 🧱 chunk 分布 vs 索引选择

- balancer 移动 chunk 时不影响索引结构。
- 但**新增分片**后大量 chunk 迁移，要观察 WT cache 命中率，避免索引页冷启动雪崩。

---

## 12.10 索引体检 Checklist

| 步骤 | 操作 | 说明 |
|---|---|---|
| **1. 找慢查询源** | 蓝鲸**慢查询分析工具**（IegMongoTeam）按业务 → 集群 → 实例下钻 | 或直接 `db.system.profile` + `currentOp({secs_running:{$gt:1}})` |
| **2. 看是否走索引** | `.explain("executionStats")` | 盯紧 `COLLSCAN`、`totalDocsExamined ≫ nReturned`、`SORT` 三个红色信号 |
| **3. 列已有索引、判重复** | `db.coll.getIndexes()` + `$indexStats` | 找出从未使用 / 被前缀涵盖的冗余索引 |
| **4. 按 ESR 设计新索引** | 等值字段 → 排序字段 → 范围字段 | 优先**覆盖查询** |
| **5. 低峰建索引 + 验证** | `createIndex` 4.2+ 默认非阻塞 | 执行后再跑一次 explain 对比 `executionTimeMillis` |
| **6. 下线旧索引（灰度）** | `hideIndex` 一周 → 慢日志无变化 → `dropIndex` | 避免误删 |
| **7. 清 planCache** | 批量数据/索引变更后 `db.coll.getPlanCache().clear()` | 避免老计划被命中（见 CASE-2） |

> 🔗 **关联章节**
> ① [§5.6 索引入门](05-mongosh.md)（基本命令）
> ② [第 9 章 · 业务案例](09-cases.md)（更多索引相关 P0/P1 实战）
> ③ [§10.3 readPreference](10-uri-readpref.md)（从读慢查询打到主：从节点必须有相同索引）


---

⬅️ [上一章 · 第 10 章 URI 与 readPreference](10-uri-readpref.md) ｜ [📖 返回目录](README.md) ｜ [下一章 · 第 12 章 附录 ➡️](12-appendix.md)

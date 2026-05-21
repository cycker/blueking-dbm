# 第 12 章 · 业务案例集（IegMongoTeam 实战）

> 汇总来自 **IegMongoTeam iWiki 知识库** 的真实业务案例，按 **故障 / 性能 / 拓扑 / 备份回档 / 迁移扩缩容 / 工具 / 单据指引** 七大主题分类。每个案例都包含 **背景 → 现象 → 定位 → 解决 → 经验** 五段式，便于按图索骥。

## 案例总览


| 指标              | 数值  | 对应小节 |
| --------------- | --- | --- |
| 📂 案例总数         | 24  | §12.1 ~ §12.7 |
| 🐛 Bug & 故障     | 7   | §12.1（#01~#07） |
| 🐌 性能 / 慢查询     | 5   | §12.2（#08~#12） |
| 🧩 拓扑 / 分片      | 4   | §12.3（#13~#16） |
| 💾 备份 / 回档      | 1   | §12.4（#17） |
| 🚚 迁移 / 扩缩容     | 3   | §12.5（#18~#20） |
| 🛠 工具集          | 1   | §12.6（#21） |
| 📋 单据指引         | 3   | §12.7（#22~#24） |


---

## 12.1 Bug & 故障类

### 案例 #01 · 4.2.0~4.2.5 KeyNotFound · config 会话缓存爆 100w 〔P0〕

- **业务**：job MongoDB 集群（2021-06）
- **版本**：4.2.5
- **标签**：`SERVER-42827` `KeyNotFound` `HMAC` `分片集群`
- **iWiki**：[https://iwiki.woa.com/p/924427245](https://iwiki.woa.com/p/924427245)

**摘要**：Java driver monitor 线程报 `error 211 KeyNotFound`，Cache Reader No keys found for HMAC，分片命令失败、chunk 迁移失败、无法访问 config primary。

**📖 背景**：域名 `mongos.joblog.bk.db#27000`，版本 4.2.5。

**🔎 现象**：

```log
com.mongodb.MongoCommandException: Command failed with error 211 (KeyNotFound):
'Cache Reader No keys found for HMAC that is valid for time: { ts: Timestamp(1624503733, 20) } with id: 0'
```

**🧪 定位 / 原因**：命中 MongoDB 官方 [SERVER-42827](https://jira.mongodb.org/browse/SERVER-42827)：受影响版本 **4.2.0 ~ 4.2.5**。当 config server primary 的 `connXXX` 达到 **100 万**（默认 `maxSessions`）即触发。

**🛠 解决方案**：

- **临时**：config 切主 → 重启 → 再切回，释放连接缓存
- **临时 2**：把 `maxSessions` 调到 100w 之上，延后触发
- **长期**：升级到 **4.2.6+**（修复版本）

> 💡 **经验**：分片集群部署 4.2.x 时，**禁止**停留在 4.2.5 及更早小版本；同时密切关注 config primary 的会话/连接数。

---

### 案例 #02 · 内核 / Docker urandom 导致 mongos crash 〔P0〕

- **版本**：任意
- **标签**：`Docker` `urandom` `内核` `crash`
- **iWiki**：[https://iwiki.woa.com/p/948332906](https://iwiki.woa.com/p/948332906)

**摘要**：mongod/mongos 崩溃，日志关键字 `cannot open /dev/urandom Operation not permitted`，与特定 Docker / 内核版本相关。

**📖 背景**：某些 Docker 版本会定期刷新 `/cgroup/devices` 信息，导致 `/dev/urandom` 在该时间点出现异常。

**🔎 现象**：mongod 或 mongos 进程 crash；日志含 `cannot open /dev/urandom Operation not permitted`；创建连接时较易触发。

**🧪 定位 / 原因**：受影响内核（黑名单）：

- `3.10.107-1-tlinux2-0048` ❌
- `5.4.87-19-0002_plusbeta5` ❌
- `3.10.107-1-tlinux2-0054` ✅

**🛠 解决方案**：避免使用黑名单内的内核版本，或直接使用 **CVM**（非容器）；现网升级到 `docker 1.12.10-a43b581+`。

> 💡 **经验**：容器化部署 MongoDB 时，**底层内核 + Docker 版本**本身就是风险面，要纳入兼容矩阵管控。

---

### 案例 #03 · 4.2.x session 不释放 〔P1〕

- **版本**：4.2.0 / 4.2.1 / 4.2.2 / 4.2.3 / 4.2.4 / 4.2.5
- **标签**：`session 泄漏` `LogicalSession`
- **iWiki**：[https://iwiki.woa.com/p/948332906](https://iwiki.woa.com/p/948332906)

**摘要**：4.2 系列且 ≤ 4.2.5 的版本存在 session 不释放问题，会逐步耗尽资源。

**📖 背景**：参考社区文章：[https://mongoing.com/archives/73811](https://mongoing.com/archives/73811)

**🔎 现象**：连接数持续累积，session 不被回收；最终影响新连接建立。

**🧪 定位 / 原因**：4.2 早期小版本 session 生命周期管理 bug。

**🛠 解决方案**：升级至 **4.2.6+**。

> 💡 **经验**：4.2.x 是高密度 bug 区，所有 4.2.0~4.2.5 集群都应排查升级计划。

---

### 案例 #04 · mongo-java-driver KeyNotFound · anyAction 角色异常 〔P1〕

- **版本**：任意
- **标签**：`Java driver` `anyAction` `签名` `keyId=0`
- **iWiki**：[https://iwiki.woa.com/p/948332906](https://iwiki.woa.com/p/948332906)

**摘要**：monitor 线程每 10s 一次 isMaster，偶发 `error 211 KeyNotFound`。根因是账号配置了 **anyResource + anyAction** 角色。

**📖 背景**：mongo-java-driver 的 monitor thread 周期性执行 `isMaster`。

**🔎 现象**：

```log
Exception in monitor thread while connecting to server mongos.stress.ccxt.db:27000
error 211 (KeyNotFound): 'Cache Reader No keys found for HMAC...'
```

**🧪 定位 / 原因**：`system.roles` 内存在带 `anyResource:true` + `actions:["anyAction"]` 的角色；这导致 **mongos 跳过签名**，返回客户端 `keyId=0`，引发后续访问异常。

**🛠 解决方案**：回收带 `anyAction` 的角色：

```javascript
// mongosh
db.system.roles.find()
db.system.roles.deleteOne({_id:"admin.applyOps"})
```

> 💡 **经验**：避免把 `anyResource + anyAction` 这种"上帝角色"赋给业务账号。

---

### 案例 #05 · 副本集模式却配置了 shardsvr · TooManyLogicalSessions 〔P2〕

- **版本**：≥ 3.6
- **标签**：`副本集` `shardsvr` `LogicalSessions`
- **iWiki**：[https://iwiki.woa.com/p/948332906](https://iwiki.woa.com/p/948332906)

**摘要**：连接数不多却返回 `TooManyLogicalSessions`，根因是 RS 模式下错误启用了 `clusterRole: shardsvr`。

**📖 背景**：replicaset 模式部署，但 `mongod.conf` 配置了 `sharding.clusterRole: shardsvr`。

**🔎 现象**：连接数远低于阈值时已收到 `TooManyLogicalSessions` 错误。

**🧪 定位 / 原因**：≥ 3.6 版本下，RS 模式不应当声明 `shardsvr`；该错误配置导致 session 缓存逻辑异常。

**🛠 解决方案**：从配置文件中删除整个 `sharding` 段后重启实例。

> 💡 **经验**：集群类型与 `clusterRole` 必须严格匹配；配置模板要按集群类型分开维护。

---

### 案例 #06 · config.system.sessions 未分片 · balancer 关闭过严 〔P2〕

- **版本**：任意
- **标签**：`system.sessions` `balancer`
- **iWiki**：[https://iwiki.woa.com/p/948332906](https://iwiki.woa.com/p/948332906)

**摘要**：`config.session` 表始终不开启 sharding，间歇性产生热点。

**📖 背景**：参考 [SERVER-46797](https://jira.mongodb.org/browse/SERVER-46797)。

**🔎 现象**：`sh.status()` 显示 `config.system.sessions` 未分片或仅在单 shard。

**🧪 定位 / 原因**：balancer 长期关闭，导致 system.sessions 集合无法被自动分片初始化。

**🛠 解决方案**：临时打开 balancer **一段时间**即可让其完成分片初始化；4.4 版本可解决（待确认）。

> 💡 **经验**：变更窗口前后人为关 balancer 是常态，但要留出一个"开放窗口"让系统集合完成自我分片。

---

### 案例 #07 · mongodb_exporter 无法采集 hidden 节点 〔P2〕

- **版本**：任意
- **标签**：`exporter` `监控` `hidden`
- **iWiki**：[https://iwiki.woa.com/p/948332906](https://iwiki.woa.com/p/948332906)

**摘要**：mongodb_exporter 访问 hidden 节点失败，导致 hidden 节点性能数据缺失。

**📖 背景**：hidden 节点（隐藏成员）通常用于备份与离线分析，但仍需可观测。

**🔎 现象**：监控面板上 hidden 节点指标全部为 0/无数据。

**🧪 定位 / 原因**：旧版 percona mongodb_exporter 不识别 hidden 节点。

**🛠 解决方案**：升级 exporter（2023 年已合并最新 percona mongodb_exporter）。同时区分版本：`prome_mongodb_exporter_v42`（4.2/4.4/6.0）与 `prome_mongodb_exporter`（≤ 4.0）。

> 💡 **经验**：监控组件本身的版本兼容性同样需要随集群版本演进而升级。

---

## 12.2 性能 / 慢查询类

### 案例 #08 · `$or` vs `$in` · cmdb 10s 超时 〔P1〕

- **业务**：bk-cloud-cmdb (蓝鲸)（2021-10）
- **版本**：4.2.x
- **标签**：`$or` `$in` `慢查询` `索引`
- **iWiki**：[https://iwiki.woa.com/p/1283428328](https://iwiki.woa.com/p/1283428328)

**摘要**：cmdb 查询大量 IP 列表用 `$or + $and` 拼接，**10 秒超时**；改写为 `$in` 后耗时降至 **0.03s**。

**📖 背景**：`cc_HostBase` 集合，按 1500 个 IP 列表查询，请求体 ~400KB。

**🔎 现象**：

```log
command cmdb.cc_HostBase command: find {
  filter: { bk_supplier_account: { $in: [...] },
    $and: [{ $or: [
      { $and:[{bk_host_innerip:"9.79.163.116"}, {bk_cloud_id:0}] },
      { $and:[{bk_host_innerip:"9.68.79.98"},  {bk_cloud_id:0}] },
      ...  // 1500 个 IP
    ]}]}
}  numYields:345  10511ms  ClientDisconnect
```

**🧪 定位 / 原因**：对**同一字段**等值检查使用 `$or`，等价于发起多次独立查询，无法走单一索引；`$or` 的条目数 ≈ 1500 时性能崩塌。

**🛠 解决方案**：

```javascript
// 优化前 (10s+)
db.cc_HostBase.find({
  $or:[ {bk_host_innerip:"a"}, {bk_host_innerip:"b"}, ... ]
})

// 优化后 (0.03s)
db.cc_HostBase.find({
  bk_host_innerip: { $in: ["a","b",...] },
  bk_supplier_account: { $in: ["0","tencent"] }
})
```

> 💡 **经验**：**同字段等值列表必须用 `$in`**，禁止用 `$or`；官方文档明确建议（`[$or` vs `$in](https://docs.mongodb.com/manual/reference/operator/query/or/)`）。

---

### 案例 #09 · partialFilterExpression 误用 · 等值查询全表扫描 〔P1〕

- **业务**：bk-cloud-cmdb（2023-11）
- **版本**：4.2.5
- **标签**：`partialIndex` `COLLSCAN` `索引未命中`
- **iWiki**：[https://iwiki.woa.com/p/4009224534](https://iwiki.woa.com/p/4009224534)

**摘要**：`cc_HostBase` 简单等值 `find({bk_agent_id:"..."})` 走 COLLSCAN 扫 34w 行；根因是 partial index 的过滤条件需要在查询中显式重述。

**📖 背景**：索引存在 `bkcc_unique_bkAgentID`，含 `partialFilterExpression: { bk_agent_id: { $type: "string", $gt: "" } }`。

**🔎 现象**：

```log
find { bk_agent_id: "02000000000c42a1ab9f3a169..." }
planSummary: COLLSCAN  docsExamined:345209  1457ms
```

**🧪 定位 / 原因**：partial index 仅为满足 `$type:"string"` + `$gt:""` 条件的文档建索引；查询若不**显式包含**这些条件，规划器认为索引可能不完整，**退回全表扫描**。参考 [官方社区讨论](https://www.mongodb.com/community/forums/t/unique-index-with-partial-filter-is-not-being-used-by-mongodb/120478/3)。

**🛠 解决方案**：

```javascript
// 改写后走 IXSCAN
db.cc_HostBase.find({
  bk_agent_id: { $type:"string", $eq:"02000000000c42a1ba2d7a..." }
})
```

同时建议开发降低相同 `bk_agent_id` 的请求频率。

> 💡 **经验**：设计 partial index 时必须同步公布"查询模板"；DBA 评审上线索引时要把 `partialFilterExpression` 对应的查询写法写进规范。

---

### 案例 #10 · 压测首查 3 秒 · mongos→shardsvr 连接池冷启动 〔P2〕

- **业务**：璀璨星途
- **版本**：≥ 4.4
- **标签**：`warmMinConnections` `连接池` `冷启动`
- **iWiki**：[https://iwiki.woa.com/p/1283429950](https://iwiki.woa.com/p/1283429950)

**摘要**：压测启动后第一波 DB 查询 ≥ 3s，后续恢复正常；与 mongos→shardsvr 连接池建立有关。

**📖 背景**：各节点负载均很低，硬件性能不是瓶颈。

**🔎 现象**：压测首批请求 300ms ~ 3s 慢查询，后续无问题。Redis 路径正常 3-5ms。

**🧪 定位 / 原因**：mongos 与 shardsvr 之间需要建立连接池，第一次访问时同步等待。

**🛠 解决方案**：从 4.4 起开启参数：`warmMinConnectionsInShardingTaskExecutorPoolOnStartupWaitMS`，启动期预热连接池。

> 💡 **经验**：生产环境上线/扩容后，建议主动 **warm up**，或调大该参数让 mongos 启动期完成池预热。

---

### 案例 #11 · 3.6 计划缓存陈旧 · 查询不走正确索引 〔P2〕

- **版本**：3.6
- **标签**：`planCache` `索引` `explain`
- **iWiki**：[https://iwiki.woa.com/p/4008458397](https://iwiki.woa.com/p/4008458397)

**摘要**：explain 显示走索引，**实际执行**却没有；清空计划缓存后恢复。

**📖 背景**：某 3.6 集群上同一查询 explain 与实际执行计划不一致。

**🔎 现象**：explain → IXSCAN ✅；实际执行 → COLLSCAN（监控视角）。

**🧪 定位 / 原因**：`planCache` 缓存了旧的次优计划。

**🛠 解决方案**：

```javascript
// mongosh
db.collection.getPlanCache().listQueryShapes()
db.collection.getPlanCache().clear()
```

> 💡 **经验**：数据分布发生明显变化（大量写入/删除）后，主动 `clear()` planCache，避免次优计划"卡顿"残留。

---

### 案例 #12 · klbqpc · 跨日刷新任务 OPS 飙升 〔P2〕

- **业务**：klbqpc 卡拉比丘端游
- **版本**：4.2.15
- **标签**：`周期性高峰` `分片键` `广播查询`

**摘要**：每天早上 6 点跨天玩家任务刷新，**OPS 与 CPU 使用率显著上升**；同时复制集→分片迁移后出现广播查询。

**📖 背景**：分片集群版本 4.2.15。

**🔎 现象**：① 每日 06:00 OPS/CPU 高峰；② 部分集合不带分片键导致**广播查询**；③ 小数据量分片集合不带分片键的范围查询耗时 200+ms。

**🧪 定位 / 原因**：分片键选择不当：未按业务真实查询模式选；小集合分片反而带来路由开销。

**🛠 解决方案**：

- 对小数据量集合 **取消分片**，改为普通集合 + 范围字段索引，耗时下降明显
- 大集合按业务高频查询字段重新选分片键

> 💡 **经验**：分片不是越多越好；**小集合保持单 shard 反而更快**，分片键必须围绕"高频查询模式"设计。

---

## 12.3 拓扑 / 分片类

### 案例 #13 · tetris · system.sessions 未分片造成单点 〔P1〕

- **业务**：tetris 俄罗斯方块环游记（2021-08）
- **版本**：4.2.x
- **标签**：`system.sessions` `分片` `热点`
- **iWiki**：[https://iwiki.woa.com/p/931103071](https://iwiki.woa.com/p/931103071)

**摘要**：分片集群中 `config.system.sessions` 仅在单 shard，mongos 周期性同步导致单节点 CPU 飙高。

**📖 背景**：分片集群部署后未观察到 system.sessions 分片初始化。

**🔎 现象**：

```log
command config.$cmd update { update: "system.sessions",
  bypassDocumentValidation: false, ordered: false, updates: 1000, ... } 214ms
```

日志显示 mongos 每 5 分钟把未过期 sessions 同步到 shard 的 system.sessions 表。

**🧪 定位 / 原因**：`config.system.sessions` shard key 仅 `{_id:1}`，单 chunk 全部落在 `tetris-prod-s1`，造成单节点压力。

**🛠 解决方案**：

- **方案 1**：调大 mongos 的 `logicalSessionRefreshMillis`（默认 300000ms / 5min → 30min）
- **方案 2**：对 `config.system.sessions` 真正做分片初始化（开 balancer 一段时间）

> 💡 **经验**：部署完分片集群后，必须验证 `config.system.sessions` 已被均匀分布。

---

### 案例 #14 · 2.4 · collection 过多导致复制异常 〔P1〕

- **版本**：2.4
- **标签**：`nssize` `复制` `STARTUP2`
- **iWiki**：[https://iwiki.woa.com/p/4014259309](https://iwiki.woa.com/p/4014259309)

**摘要**：backup 节点不断 resync，状态卡在 STARTUP2；日志报 `too many namespaces/collections`。

**📖 背景**：2.4 老版本 MMAPv1 引擎下，namespace 数量受 `nssize` 限制。

**🔎 现象**：

```log
[rsSync] error building index: 10081 too many namespaces/collections
[rsSync] ERROR: error: exception cloning object in dynamic.system.indexes
   too many namespaces/collections
replSet initial sync exception: 10081 too many namespaces/collections
```

**🧪 定位 / 原因**：`mongo.conf` 中 `nssize=16` 已无法容纳全部 namespace。

**🛠 解决方案**：调整 `nssize=32`（**注意单位为 MB**），重启实例后同步恢复。

> 💡 **经验**：2.4 是 EOL 版本；新部署绝对不要用，存量集群务必规划迁移。

---

### 案例 #15 · mongodump 域名连接报 CursorNotFound 〔P2〕

- **版本**：4.2 / 100.7.1
- **标签**：`mongodump` `CLB` `会话保持`
- **iWiki**：[https://iwiki.woa.com/p/4008173577](https://iwiki.woa.com/p/4008173577)

**摘要**：通过**域名 / VIP** 连 mongos 跑 mongodump 报 `CursorNotFound`；直连 mongos IP 不报错。

**📖 背景**：4.2 分片集群，mongodump 4.2 / 100.7.1 均复现。

**🔎 现象**：

```log
Failed: error writing data for collection `2.ds_info_13` to disk:
error reading collection: (CursorNotFound) Cursor not found
(namespace: '2.ds_info_13', id: 5838431923177422211).
```

**🧪 定位 / 原因**：mongodump 会发起 **2 个连接**，两个连接落在不同 mongos 时 cursor 失效。

**🛠 解决方案**：

- 方案 1：腾讯云 CLB 启用 **会话保持**（同源 IP → 同 mongos）
- 方案 2：直接连 mongos 物理 IP

> 💡 **经验**：分片集群 + LB 部署形态下，所有**多连接客户端**（mongodump、mongorestore、自定义脚本）都要确认 LB 的会话保持设置。

---

### 案例 #16 · configsvr + mongos 整体替换流程 〔P2〕

- **版本**：任意
- **标签**：`configsvr` `mongos` `替换`
- **iWiki**：[https://iwiki.woa.com/p/4006818693](https://iwiki.woa.com/p/4006818693)

**摘要**：分片集群中 configsvr 与 mongos 的"无中断"替换 5 步法。

**📖 背景**：机器搬迁、机型升级、机房迁移等场景。

**🔎 现象**：需要替换 configsvr 与 mongos 而保持业务无感知。

**🧪 定位 / 原因**：configsvr 是分片元数据核心；替换不当会导致路由错乱。

**🛠 解决方案**：

1. 新的 configsvr 上架，并替换其中 2 个节点
2. 修改配置项指向**新的 3 个节点**
3. 上架新 mongos 并激活；此时新旧 mongos 都正常服务
4. 下架旧 mongos
5. 最后一个 configsvr `stepDown` 并替换

> 💡 **经验**：configsvr 替换的核心是"先扩后缩 + stepDown"，**永远不能同时替换 majority 节点**。

---

## 12.4 备份 / 回档类

### 案例 #17 · 4.2 分片集群 Restore 完整流程 〔P1〕

- **版本**：4.2
- **标签**：`mongodump` `mongorestore` `clusterId`
- **iWiki**：[https://iwiki.woa.com/p/4010429492](https://iwiki.woa.com/p/4010429492)

**摘要**：官方未提供基于 mongodump/mongorestore 的分片集群备份方案；本案例摸索出 **standalone → 维护元数据 → 启动** 的完整路径。

**📖 背景**：相比副本集 restore，分片集群多出 **configsvr ↔ shardsvr 元数据维护** 这一关键步骤。

**🔎 现象**：三处元数据必须保持一致：

- `configsvr.config.shard.host` = shardsvr 连接串
- `configsvr.config.version.clusterId` = shardsvr `shardIdentity.clusterId`
- `shardsvr.shardIdentity.configsvrConnectionString` = configsvr 连接串

**🧪 定位 / 原因**：分片集群元数据强耦合 configsvr 与 shardsvr。

**🛠 解决方案**：

**configsvr 处理**：

1. 注释 `sharding`/`replication` 段，以 standalone 启动
2. 用 GCS 单进程回档功能 restore 数据
3. `config.shards` 更新 host 字段为新 shardsvr 连接串
4. 关掉 balancer：`db.settings.insert({_id:"balancer",mode:"full",stopped:true})`
5. 恢复配置以 `clusterRole: configsvr` 启动
6. 记录新的 `clusterId`

**shardsvr 处理**：

1. 同样以 standalone 启动
2. restore 数据
3. insert `shardIdentity` 到 `admin.system.version`（4.2 不允许 update，必须 insert）
4. 恢复 `clusterRole: shardsvr` 启动

最后启动 mongos 即可。

> 💡 **经验**：分片集群备份方案必须配套**元数据脚本**，否则 restore 出来的集群路由错乱。参考 [官方文档](https://www.mongodb.com/docs/v4.4/tutorial/restore-sharded-cluster/)。

---

## 12.5 迁移 / 扩缩容类

### 案例 #18 · xssh · 5 区分服 mongos/shard 缩容 〔P1〕

- **业务**：xssh 小森生活（2022-07）
- **版本**：任意
- **标签**：`缩容` `机型变更` `分服`
- **iWiki**：[https://iwiki.woa.com/p/931103786](https://iwiki.woa.com/p/931103786)

**摘要**：5 个分服（iosqq/ioswx/androidqq/androidwx/游客服），mongos 从 16 个 D12-30-100-10 缩到 6 个 D4-15-100-10；shard 从 D7-29-300-10-Z 缩到 D4-20-100-10-Z。

**📖 背景**：游戏运营进入稳定期，资源利用率下降，需要降本。

**🔎 现象**：容量充裕但成本高；机型规格远超实际需求。

**🧪 定位 / 原因**：初期按峰值容量预估，后期没有及时降配。

**🛠 解决方案**：

1. shard：D7-29-300-10-Z → D4-20-100-10-Z
2. mongos 实例数：16 → 6，机型 D12-30-100-10 → D4-15-100-10
3. 分阶段缩容（先验证 1 个区，再推广）

> 💡 **经验**：游戏类业务有明显的"上线 → 衰减"曲线，缩容也是常态运维；务必**分批 + 灰度**。

---

### 案例 #19 · vega · 街霸合服 30→10 节点 〔P1〕

- **业务**：vega 街霸（2021-07）
- **版本**：任意
- **标签**：`合服` `mongodump` `mongorestore`
- **iWiki**：[https://iwiki.woa.com/p/863430064](https://iwiki.woa.com/p/863430064)

**摘要**：将 sq 后 30 个分服合并到前 10 个分服：S11~~S40 → S01~~S10，按 4 节点一组合并。

**📖 背景**：街霸合服需求，4 个分服合并为 1 个。

**🔎 现象**：30 个分服合到 10 个分服，需要保留数据完整性。

**🧪 定位 / 原因**：游戏中后期减少运维成本与玩家分散度的常规操作。

**🛠 解决方案**：

1. `mongodump` 各源服数据
2. 删除 `admin`/`test`/`config` 数据库（避免冲突）
3. `mongorestore` 到目标分服
4. 分批回收资源（QQ 区先，WX 区观察后再回收）

> 💡 **经验**：合服流程必须"先验证、再回收"；保留观察期至少 2~3 天再下架资源。

---

### 案例 #20 · 基于实例迁移的扩容缩容（GCS 单据流） 〔P2〕

- **版本**：任意
- **标签**：`扩容` `缩容` `GCS 单据`
- **iWiki**：[https://iwiki.woa.com/p/284630719](https://iwiki.woa.com/p/284630719)

**摘要**：通过 **新增 SECONDARY → 域名切换 → 下架旧实例** 的单据序列完成扩缩容。

**📖 背景**：单机器实例数增多导致内存压力 / 想合并机器降本时使用。

**🔎 现象**：需要在不中断服务的前提下迁移实例。

**🧪 定位 / 原因**：单纯关停-迁移会有中断；副本集机制可平滑过渡。

**🛠 解决方案**：

**扩容顺序**：

1. 准备新机器，安装 shardsvr-tmp（AreaId/SetId 与原实例相同；副本集模式端口也要相同）
2. 用"增加节点"单据加入 RS（业务高峰建议 `priority:0`）
3. 等同步完成 → SECONDARY
4. 执行"域名切换"
5. 调高新实例 CacheSize
6. 下架旧实例

**缩容**：步骤相同；要注意现有实例内存使用量，必要时先调小 CacheSize。

> 💡 **经验**：同步失败（卡 RECOVERING）时改用 **fsyncLock + 拷贝数据文件** 的 `resync-replica-set-member` 流程；3.0 WiredTiger 不支持此法。

---

## 12.6 工具集

### 案例 #21 · MongoDB 慢查询分析工具（基于 ES + Grafana） 〔P2〕

- **版本**：任意
- **标签**：`慢查询` `Grafana` `火焰图` `ES`
- **iWiki**：[https://iwiki.woa.com/p/278981241](https://iwiki.woa.com/p/278981241)

**摘要**：从 ES 拉慢查询日志，写入 spider 集群，通过 Grafana 提供曲线/饼图/火焰图/表格多视图，支持 **业务→集群→实例** 三级下钻分析。

**📖 背景**：传统 mongo profiling 对性能影响大；需要"零侵入"的慢查询分析方案。

**🔎 现象**：人工抓 explain 与 profile 效率低，无法横向对比业务。

**🧪 定位 / 原因**：缺少统一的诊断平台。

**🛠 解决方案**：

- 不开 profiling，**性能影响为零**
- 正则矩阵抓取多版本不同操作类型的慢查询日志
- 实参 → 形参替换 + 哈希作为主键聚合统计
- top5 自动连接实际数据库执行 explain plan
- 规则表检查：`totalDocsExamined ≫ totalKeysExamined` 或 `COLLSCAN` → 自动生成"缺失索引"建议

入口：[Grafana MongoDB 慢查询分析](http://monitor.gcs.ied.com/d/xtGpK8qZk/mongodb-man-cha-xun-fen-xi)

> 💡 **经验**：慢查询治理需要平台级工具；引入"自动给优化建议"能极大降低 DBA 重复劳动。

---

## 12.7 单据指引

### 案例 #22 · GCS 单据指引 · 安装 MongoDB 〔P2〕

- **版本**：任意
- **标签**：`GCS 单据` `安装` `部署`
- **iWiki**：[https://iwiki.woa.com/p/284630719](https://iwiki.woa.com/p/284630719)

**摘要**：副本集 / 分片集群两种安装路径；不同副本集端口错开便于后续合并；单机多实例 WTCacheSize 总和 ≤ 内存 60%。

**📖 背景**：业务新上线场景。

**🔎 现象**：需要标准化的部署流程。

**🧪 定位 / 原因**：手工部署易出错且难审计。

**🛠 解决方案**：

**副本集**：

1. "MongoDB-安装"单据，类型选"副本集"
2. 不同副本集端口错开
3. WTCacheSize 总和 ≤ 内存 60%
4. Backup 节点规格可为 Primary/Secondary 的一半
5. 执行"部署监控"单据

**分片集群**：

1. 安装 configsvr 副本集（≥ 3.0 setid 固定为 `conf` 自动注册 configdb；2.4 需手动配 `$app→MongoDB→cluster→$ClusterID→$configdb`）
2. 安装各分片副本集
3. 安装 mongos
4. 连 mongos 执行 `sh.addShard` 加分片
5. 关闭 balancer + 设 chunkSize（默认 64M，最大 1024M）：
  - `sh.setBalancerState(false)`
  - `db.getSisterDB('config').settings.save({_id:'chunksize', value:512})`
6. 执行"激活 Mongos 域名" + "部署监控"
7. 建库表：`sh.enableSharding` + `sh.shardCollection`

> 💡 **经验**：端口规划是隐藏的运维财富：错开端口后，将来"机器合并"时不需要改任何业务连接串。

---

### 案例 #23 · GCS 单据指引 · 部分/全量回档 〔P0〕

- **版本**：任意
- **标签**：`回档` `构造数据` `recover`
- **iWiki**：[https://iwiki.woa.com/p/284630719](https://iwiki.woa.com/p/284630719)

**摘要**：区分**部分数据回档**（受影响玩家可枚举）与**全量数据回档**（影响全服）两种方案。

**📖 背景**：业务出现复制 bug 或误操作，需要回退到过去时间点。

**🔎 现象**：数据状态错误，需要恢复。

**🧪 定位 / 原因**：人为误操作 / 业务 bug / 程序逻辑缺陷。

**🛠 解决方案**：

**部分数据回档**（推荐）：

1. 申请新机器
2. "MongoDB-安装"部署 shardsvr-primary（单点）
3. "MongoDB-addUser" 增加 recover 用户（需 AnyAction 权限）
4. "MongoDB-构造数据"
5. 请产品给出受影响 QQ/openid 列表 → 封号 → 开服
6. 对受影响用户做数据替换（脚本编写或开发协助）
7. 验证后解封

**全量数据回档**：

1. 同样准备新机器 + 部署 shardsvr-primary
2. 构造数据完成后导出，再导入现网 DB（停服状态下操作）

> 💡 **经验**：**部分回档优先**，全量回档压力大；任何回档前必须先备份。

---

### 案例 #24 · 故障替换流程 〔P1〕

- **版本**：任意
- **标签**：`故障替换` `RECOVERING` `fsyncLock`
- **iWiki**：[https://iwiki.woa.com/p/284630719](https://iwiki.woa.com/p/284630719)

**摘要**：机器故障时通过 so.ied.com 申请新机 → 部署 tmp 节点 → 故障替换单据 → 部署监控 → 下架旧节点。

**📖 背景**：某机器突发故障。

**🔎 现象**：实例不可用，需要紧急替换。

**🧪 定位 / 原因**：硬件故障 / 系统异常 / 网络隔离等。

**🛠 解决方案**：

1. so.ied.com 用"故障替换"申请同机房同规格新机
2. "MongoDB-安装"部署相应数量的 shardsvr-tmp
3. "MongoDB-故障替换"单据完成实例替换
4. "MongoDB-部署监控"
5. "MongoDB-下架"旧实例

同步失败（RECOVERING）时改用 **fsyncLock + 拷贝数据文件**：

```javascript
// 在健康的 SECONDARY B 上
db.fsyncLock()
// 拷贝 B 数据文件到故障节点 C 的对应目录
// 启动 C
db.fsyncUnlock()  // 在 B 上执行
```

> 💡 **经验**：**WiredTiger 3.0 不能用 fsyncLock 拷文件法**；超大文件传输考虑 tsunami 加速。

---

## 章节导航

⬅️ [上一章 · 第 11 章 URI 与 Read Preference](11-uri-readpref.md) ｜ [📖 返回目录](README.md) ｜ [下一章 · 第 13 章 DBM 性能视图 ➡️](13-performance-views.md)


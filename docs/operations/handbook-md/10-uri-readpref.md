# 第 10 章 · MongoDB 连接 URI 与 readPreference 全解

MongoDB 客户端与服务器之间的「**连接串**」远比 MySQL JDBC URL 复杂：它一行字符串里同时包含了 **种子节点列表、副本集名称、认证库、TLS、压缩、读偏好、超时** 等几十种参数。

理解 `connection string` 与 `readPreference`，是排查 *读写分离不生效、慢查询打错节点、从节点延迟读到旧数据* 等问题的前提。本章对照真实业务案例，给出可直接复用的连接模板。

---

## 11.1 连接串两种格式（基础）

### 📜 标准格式 · Standard

最常用。直接列出种子主机，副本集 / mongos 都适用。

```
mongodb://[username:password@]host1[:port][,host2[:port],...][/[defaultDb][?options]]
```

- **host 列表**：副本集时建议 **全部成员** 都列上，至少 2 个；分片集群列 **所有 mongos**。
- **defaultDb**：常被误以为是「认证库」，其实是「默认 use 的库」；认证库由 `authSource` 指定。

### 🌐 SRV 格式 · DNS Seedlist

需要 DNS 服务支持，能从一条记录解析出多节点种子。

```
mongodb+srv://user:pass@cluster.example.com/?replicaSet=rs0
```

> ⚠ **蓝鲸 / GCS 域名当前不提供 SRV 记录**
> 内网 DNS 多采用「轮询返回单 IP」机制，**请使用标准格式手动列出全部 mongos / 副本集成员**，否则可能出现 cursor 失效与负载不均（见 11.6）。

### 解剖一条真实连接串

```
// 副本集（主从读写分离）
mongodb://appuser:P@ssw0rd@10.1.1.1:27017,10.1.1.2:27017,10.1.1.3:27017/myapp?replicaSet=rs0&authSource=admin&readPreference=secondaryPreferred&maxStalenessSeconds=90&w=majority

// 分片集群（多 mongos）
mongodb://appuser:P@ssw0rd@mongos1:27021,mongos2:27021,mongos3:27021/?authSource=admin&readPreference=primary&retryWrites=true
```

> 🔑 **密码中有特殊字符？**
> `@ : / ? # [ ]` 等需要 **URL 百分号转义**（如 `@`→`%40`），否则解析会把密码截断当成 host。
> 部分外部同步工具明确要求「密码不能含 `@`」，建议运维侧在建账号时 **避开特殊字符**。

---

## 11.2 常用 URI Options 速查（参数）

URI 后 `?` 里的 key=value 都是 options，多个用 `&` 连接。下表整理蓝鲸场景最常见的 18 项。

| 分类 | 参数 | 取值 / 示例 | 说明 |
|------|------|------------|------|
| 拓扑 | `replicaSet` | `rs0` | 副本集名；**不写**则当作单机连接，故障转移失效 |
| 拓扑 | `directConnection` | `true` / `false` | 强制直连指定 host，跳过拓扑发现（排障常用） |
| 认证 | `authSource` | `admin` | 认证库；与 `defaultDb` 区分 |
| 认证 | `authMechanism` | `SCRAM-SHA-256` | 4.0+ 默认；老版本用 SHA-1 |
| 认证 | `tls` / `ssl` | `true` | 启用 TLS（外网 / 公有云常用） |
| 读偏好 | `readPreference` | `secondaryPreferred` | 见 11.3 |
| 读偏好 | `readPreferenceTags` | `dc:sh,role:analytics` | 按 tag 选节点 |
| 读偏好 | `maxStalenessSeconds` | `90` | 从库最大延迟阈值；超过则跳过 |
| 写关注 | `w` | `1` / `majority` | 写多少个节点才返回成功 |
| 写关注 | `journal` / `j` | `true` | 是否落 journal 才返回 |
| 写关注 | `wtimeoutMS` | `5000` | 写关注的超时 |
| 连接池 | `maxPoolSize` | `100` | 客户端单 host 最大连接数（默认 100） |
| 连接池 | `minPoolSize` | `0` | 常驻最小连接 |
| 连接池 | `maxIdleTimeMS` | `60000` | 空闲连接回收时间 |
| 超时 | `connectTimeoutMS` | `10000` | 建立 socket 的超时 |
| 超时 | `socketTimeoutMS` | `0` | 单次 IO 超时；0 = 永不超时 |
| 高级 | `retryWrites` | `true` | 4.2+ 默认 true，幂等写自动重试一次 |
| 高级 | `compressors` | `zstd,snappy,zlib` | 线上传输压缩；3.6+ 支持 |

完整列表见 [官方 Connection String Options](https://www.mongodb.com/docs/manual/reference/connection-string-options/)。

---

## 11.3 readPreference 五种模式（读偏好）

这是最容易写错、也最影响业务体验的一组参数。**它仅决定「读流量打到哪个节点」**，写流量永远只能到 Primary。

### 🔴 primary · 仅主

- **默认值**。所有读都打到 Primary。
- 强一致；Primary 故障期间读会失败。
- 适合：账户、订单、计费等强一致业务。

### 🟠 primaryPreferred · 主优先

- Primary 健康时打 Primary，否则打 Secondary。
- Primary 故障期间读不会中断。
- 适合：希望故障期间「读降级」的写多读少业务。

### 🟢 secondary · 仅从

- 必须打 Secondary，主上不读；无可用从库则读失败。
- 从可能落后；非主链路存在 **瞬时旧数据**。
- 适合：报表、离线统计、爬虫式扫描。

### 🔵 secondaryPreferred · 从优先

- **蓝鲸内最常见**。优先 Secondary，无可用从库再读 Primary。
- 读写分离的最佳折中：主写从读，主故障读不中断。
- 监控采集 / 备份 / 旁路分析等只读型负载推荐使用。

### 🟣 nearest · 最近节点

- 不区分主从，按 **ping 延迟** 选最近的节点（含 Primary）。
- 适合：跨机房 / 跨地域部署，希望就近读。
- 注意：拿到的可能是从（旧数据）也可能是主（强一致）；业务必须能容忍这两种情况。

### mongosh 中切换 readPref

```javascript
// 当前会话切换；脚本里很常用，例如「呢称提取脚本」
db.getMongo().setReadPref("secondary")
db.getMongo().setReadPref("secondaryPreferred", [{ dc: "sh" }])    // 带 tag

// 单条命令级覆盖
db.users.find().readPref("secondaryPreferred").limit(10)
```

---

## 11.4 maxStalenessSeconds：让从读「不至于太旧」（一致性）

当 readPreference 允许从读时，**maxStalenessSeconds** 决定客户端只挑选「延迟不超过 N 秒」的从节点；超过该阈值的从会被驱动暂时排除。

| 取值 | 含义 | 建议 |
|------|------|------|
| `未设置` | 不限制；任意延迟都用 | 采集 / 异步统计可不填 |
| `90` | 从必须落后不超过 90s | **蓝鲸 cmdb 真实采用值**（见慢查询案例） |
| `120` | 2 分钟 | 读容忍度较高的报表 |

> ⚠ **下限 90 秒**
> MongoDB 协议规定该参数最小值为 `90`，小于 90 会报错。
> 且只有 `secondary` / `secondaryPreferred` / `nearest` 三种模式下才生效。

---

## 11.5 writeConcern：写多少节点才算成功（一致性）

与 readPreference 对偶，**writeConcern** 控制写请求需要复制到几个节点才返回 ACK，可以在 URI、单条命令、事务三个级别设置。

### ⚡ w=1（默认 4.x 之前）

- Primary 落地即返回；最快但有 **主切换丢失** 风险。
- 用于日志类、可重试写。

### 🛡 w=majority（5.0+ 默认）

- 必须落到「过半成员」；可对抗主切换丢数据。
- 账户、订单、扣费类 **必填**。

### 📐 w=&lt;number&gt;

- 指定到 N 个节点；`w=2` 常用于 3 节点副本集，性能与可靠性折中。

### 🏷 w=&lt;custom-tag&gt;

- 结合副本集 `settings.getLastErrorModes`，按机房 / 角色组合数。
- 跨城多活会用到。

```javascript
// 单条写指定 writeConcern
db.orders.insertOne(
  { _id: 1, amount: 100 },
  { writeConcern: { w: "majority", j: true, wtimeout: 5000 } }
)
```

---

## 11.6 真实业务案例 · 连接串踩坑（案例）

### 🔴 CASE-1 · CursorNotFound：域名 / VIP 连 mongos

- **现象**：用 GCS 域名 / CLB VIP 跑 mongodump 报 `CursorNotFound`。
- **原因**：DNS 轮询或 LB 未开会话保持，2 个连接落到不同 mongos，cursor 失效。
- **修复**：连接串里把 **所有 mongos IP 全部写上** `mongodb://m1,m2,m3/?...`

### 🟠 CASE-2 · mongos 负载不均

- **现象**：CLB VIP 开会话保持后，单台 mongos 被打爆。
- **原因**：客户端被绑死到一台 mongos。
- **修复**：去掉会话保持改用 **多 IP 列表**；客户端驱动会自动均衡。

### 🟢 CASE-3 · cmdb：$readPreference 90s

- 蓝鲸 cmdb 慢查询日志显示 `$readPreference: { mode: "secondaryPreferred", maxStalenessSeconds: 90 }`
- **意图**：业务允许 90 秒延迟读，把 list / scan 类压力下放到 Secondary。
- **关注点**：Secondary 上仍要保证索引覆盖，否则慢查询会照样飞到主。

### 🔵 CASE-4 · 呢称脚本 · setReadPref

- warthunder 业务用 mongo shell 跑导出脚本，开头先 `db.getMongo().setReadPref('secondary')`。
- **价值**：扫全表的导出不再压主，避免影响在线玩家。
- **提示**：写型脚本（含 `save` / `update`）**不能** 这样设；驱动会拒绝写非主。

---

## 11.7 各客户端 / 驱动 URI 写法（实战）

### mongosh

```bash
# 副本集 + 从优先 + 写多数
mongosh "mongodb://app:pwd@10.1.1.1:27017,10.1.1.2:27017,10.1.1.3:27017/?replicaSet=rs0&authSource=admin&readPreference=secondaryPreferred&w=majority"

# 仅排障：直连某个 hidden 节点
mongosh "mongodb://app:pwd@10.1.1.9:27017/?authSource=admin&directConnection=true"
```

### Java

```java
MongoClient client = MongoClients.create(
  "mongodb://app:pwd@m1:27021,m2:27021,m3:27021/?authSource=admin" +
  "&readPreference=secondaryPreferred&maxStalenessSeconds=90" +
  "&maxPoolSize=200&retryWrites=true");
```

### Python (PyMongo)

```python
from pymongo import MongoClient
client = MongoClient(
    "mongodb://app:pwd@10.1.1.1,10.1.1.2,10.1.1.3:27017/"
    "?replicaSet=rs0&authSource=admin"
    "&readPreference=secondaryPreferred&maxStalenessSeconds=90"
)
```

### Go

```go
opts := options.Client().ApplyURI(
  "mongodb://app:pwd@m1:27021,m2:27021/?authSource=admin&readPreference=secondaryPreferred",
)
client, err := mongo.Connect(ctx, opts)
```

### Node.js

```javascript
const { MongoClient } = require('mongodb');
const client = new MongoClient(
  'mongodb://app:pwd@m1:27021,m2:27021/?authSource=admin&readPreference=secondaryPreferred'
);
```

---

## 11.8 排障 Checklist（速查）

### 🔍 客户端报「无法连主」

1. 检查 `replicaSet` 名是否一致（可用 `rs.conf().settings.replicaSetId` 比对）。
2. **是否漏写 mongos / 成员**，导致单点故障即不可用。
3. VPC / 安全组放通了「全部成员端口」吗？只放通主是不够的。

### 🐢 「读到旧数据」

1. 确认 readPreference 是否为 secondary*；调到 `primary` 复测。
2. 查看 `rs.printSecondaryReplicationInfo()`，**从延迟** 是否高。
3. 设置 `maxStalenessSeconds=90`，让驱动主动剔除老化从节点。

### 📈 从读慢查询打到主

1. 慢日志里检查 `$readPreference.mode` 字段。
2. 若为 `primary`，驱动 / 框架配置覆盖了 URI；优先在 **客户端代码** 中关掉。
3. 从节点 **必须建相同索引**；否则即便走从也很慢。

### 🔁 主切换后业务报错

1. 检查 `retryWrites=true` 是否开启。
2. 幂等写已自动重试一次；非幂等写需业务自行实现幂等。
3. Java 驱动 ≥ 4.x、PyMongo ≥ 3.11 默认开启。

---

## 11.9 蓝鲸 DBM 推荐连接模板（模板）

### 在线交易（强一致）

```
mongodb://app:pwd@host1,host2,host3/?
  authSource=admin
  &replicaSet=rs0
  &readPreference=primary
  &w=majority&j=true
  &retryWrites=true
  &maxPoolSize=200
```

### 读写分离（默认）

```
mongodb://app:pwd@host1,host2,host3/?
  authSource=admin
  &replicaSet=rs0
  &readPreference=secondaryPreferred
  &maxStalenessSeconds=90
  &w=majority
  &retryWrites=true
```

### 报表 / 离线扫描

```
mongodb://analytics:pwd@host1,host2,host3/?
  authSource=admin
  &replicaSet=rs0
  &readPreference=secondary
  &maxStalenessSeconds=120
  &socketTimeoutMS=600000          // 长扫描防中断
  &maxPoolSize=20                  // 不要把从打满
```

### 备份采集

```
mongodb://backup:pwd@host1,host2,host3/?
  authSource=admin
  &replicaSet=rs0
  &readPreference=secondary
  &readPreferenceTags=role:backup     // 优先打 backup 节点
  &readPreferenceTags=                // 兜底任意从
```

> 📘 **相关章节**
> ① [第 5 章 · mongosh 入门](05-mongosh.md) 有连接示范；
> ② [第 8 章 · MongoDB 工具集](08-mongo-tools.md) 各工具如何使用 URI 与 readPref；
> ③ [第 9 章 · 业务案例](09-cases.md) 有 mongos 负载不均、CursorNotFound 等真实问题。

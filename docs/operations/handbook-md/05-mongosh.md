# 第 5 章 · MongoDB Shell 语法入门（mongosh）

> 面向有 **MySQL / Redis** 使用经验、需要快速上手 MongoDB 交互的运维人员。仅覆盖**日常排障与验活**常用写法；聚合、事务、分片键设计请参考 [MongoDB 官方文档](https://www.mongodb.com/docs/manual/)。

---

## 5.1 环境与连接

`mongo` 与 `mongosh` **都是 MongoDB 官方 Shell**。`mongosh` 在 **MongoDB 5.0 阶段**作为新一代交互式 Shell 推出，**向下兼容 MongoDB 3.6 及以上**所有版本。它基于 Node.js 实现，提供更友好的语法高亮、补全、异步 await 与现代 JS 能力。

### 🌟 mongosh（推荐）

- 5.0 起官方主推，5.x/6.x/7.x/8.x 安装包**默认仅含 mongosh**。
- 对内置脚本对象（`rs.*`、`sh.*`、`db.adminCommand` 等）**支持最完整**，部分新方法仅在 mongosh 中可用。
- 支持 ES Module、await 异步、外部 npm 包加载。

### 🧰 mongo（legacy shell）

- 3.x ~ 4.x 时代的经典 Shell，4.4 及更早集群运维仍常用。
- 大部分 CRUD / explain 用法两者一致；写脚本可**互相迁移**。
- 5.0+ 服务端安装包**不再附带**，但二进制仍可独立下载使用。

> 💡 **选型建议**
> ① **操作系统内置脚本对象**（如 `sh.status()`、`rs.status()`、`rs.conf()`）请优先使用 `mongosh`，新版本特性覆盖最全；
> ② 老集群（3.6 / 4.0 / 4.2 / 4.4）若只装了 `mongo`，继续使用即可；
> ③ 需要在脚本里使用 `await`、`fetch`、外部 npm 模块时，必须用 `mongosh`。

连接方式与 MySQL 客户端类似：指定主机、端口、认证库与用户密码；副本集常在连接串中带 `replicaSet` 参数。

```bash
# 直连单节点或经 mongos 访问（按环境替换主机、端口、用户）
mongosh "mongodb://user:password@host1:27017,host2:27017/admin?replicaSet=rs0"

# 老集群仍可用 legacy shell，命令完全兼容
mongo   "mongodb://user:password@host1:27017/admin?replicaSet=rs0"
```

- **SRV 记录**：`mongodb+srv://...` 常用于云或托管服务解析种子列表。
- **与 MySQL 对照**：`mysql -h host -P 3306 -u user -p` → mongosh 通常用 URI 或 `--host` / `--port` / `--username` 等参数（见 `mongosh --help`）。
- **连接字符串细节**：见 [第 11 章 · 连接 URI & readPreference](./11-uri-readpref.md)。

---

## 5.2 层次与命名

| MongoDB | 可类比 MySQL | 说明 |
|---|---|---|
| `database` | database | `use <db>` 切换当前库 |
| `collection` | table | 无固定 schema，文档结构可不同 |
| `document` | row | BSON / JSON 文档 |
| `field` | column | 嵌套对象与数组即子结构 |

**命名空间（namespace）**：`<database>.<collection>`，例如 `app.users`。

---

## 5.3 必会命令（交互式）

```javascript
show dbs                    // 列出可见数据库（需权限）
use myapp                   // 切换当前数据库（不存在则延后创建）
show collections            // 当前库下的集合，也可写作 show tables
db.getName()                // 当前库名，也可直接输入 db
```

对集合的操作统一写为：`db.<集合名>.<方法>(...)`，例如 `db.users.find()`。

---

## 5.4 基础 CRUD

下列示例中集合名为 `users`。

### 插入

新脚本建议使用 `insertOne` / `insertMany`，不要再使用旧的 `insert` 写法。

```javascript
db.users.insertOne({ name: "Alice", age: 30 })                         // 插入一条
db.users.insertMany([{ name: "Bob" }, { name: "Carol", tags: ["vip"] }]) // 插入多条
```

### 查询

```javascript
db.users.find()                              // 全表扫描式列出（生产慎用）
db.users.findOne({ name: "Alice" })          // 一条
db.users.find({ age: { $gte: 18 } }, { name: 1, _id: 0 })  // 条件 + 投影
db.users.find().limit(10).sort({ age: -1 }) // 排序与限制条数
```

### 更新

MongoDB 更新时要先确认目标：是**只更新某个字段**，还是**替换整个文档**。

- 新脚本建议使用 `updateOne` / `updateMany`，不要再使用旧的 `update` 写法。
- 只改字段：使用 `updateOne` / `updateMany` 搭配 `$set`、`$unset`、`$inc` 等更新操作符。
- 替换整文档：使用 `replaceOne`，新文档会替换原文档中除 `_id` 以外的内容，未写入的字段会丢失。
- `updateOne` / `updateMany` 是 MongoDB 3.2 新增的语义化方法；老脚本里常见的 `update(filter, update, options)` 默认只更新一条，传 `{ multi: true }` 才会更新多条。

```javascript
db.users.updateOne(
  { name: "Alice" },
  { $set: { age: 31 }, $currentDate: { lastModified: true } }  // 只更新字段
)
db.users.replaceOne({ name: "Bob" }, { name: "Bob", age: 0 })  // 整文档替换

// 历史写法，仅用于理解老脚本，不建议新写
db.users.update({ name: "Alice" }, { $set: { age: 31 } })                  // 默认只更新一条
db.users.update({ age: { $lt: 18 } }, { $set: { status: "minor" } }, { multi: true })  // 更新多条
```

### 删除

`deleteOne` / `deleteMany` 也是 MongoDB 3.2 新增的语义化方法；新脚本建议使用它们，不要再使用旧的 `remove` 写法：

- `deleteOne(filter)`：删除匹配条件的第一条文档。
- `deleteMany(filter)`：删除所有匹配条件的文档。
- `remove(filter)`：旧写法，常见于历史脚本；默认效果接近 `deleteMany(filter)`，如果传 `{ justOne: true }` 或第二个参数 `true`，则接近 `deleteOne(filter)`。

```javascript
db.users.deleteOne({ name: "Carol" })       // 删除一条
db.users.deleteMany({ age: { $lt: 18 } })   // 删除多条

// 历史写法，仅用于理解老脚本，不建议新写
db.users.remove({ name: "Carol" })          // 默认删除匹配条件的多条
db.users.remove({ name: "Carol" }, true)    // 只删除一条
```

### SQL 对照（关键词）

| SQL | MongoDB（典型） |
|---|---|
| `SELECT * FROM users WHERE id = 1` | `db.users.find({ _id: 1 })` |
| `SELECT name FROM users LIMIT 10` | `db.users.find({}, { name: 1, _id: 0 }).limit(10)` |
| `INSERT INTO users ...` | `insertOne` / `insertMany` |
| `UPDATE users SET age=31 WHERE name='Alice'` | `updateOne` + `$set`，只更新字段 |
| `DELETE FROM users WHERE ...` | `deleteOne` / `deleteMany` |

> 🔑 **关于 `_id`**
> 若插入时不指定，服务端会生成 **ObjectId**。在 shell 中可用 `ObjectId("hexstring")` 构造。

---

## 5.5 常用查询运算符（极简）

| 运算符 | 含义 | 示例 |
|---|---|---|
| `$eq` / `$ne` | 等于 / 不等于 | `{ status: { $ne: "deleted" } }` |
| `$gt` / `$gte` / `$lt` / `$lte` | 比较 | `{ age: { $gte: 18 } }` |
| `$in` / `$nin` | 在列表中 / 不在 | `{ type: { $in: ["a", "b"] } }` |
| `$and` / `$or` | 与 / 或 | `{ $or: [ { a: 1 }, { b: 2 } ] }` |
| `$regex` | 正则 | `{ name: { $regex: /^A/ } }` |

**逻辑与**：同一对象内多字段默认 **AND**。

---

## 5.6 索引入门

```javascript
db.users.createIndex({ name: 1 }, { unique: true })   // 单字段升序，唯一
db.users.createIndex({ lastLogin: -1 })              // 降序
db.users.getIndexes()                               // 查看索引
db.users.dropIndex("name_1")                        // 按索引名删除（名以实际为准）
```

> ⚠ **性能提示**
> 与 MySQL 类似：大集合上无索引的 `find` 易导致 CPU/IO 压力，排障时先 `explain("executionStats")`。

---

## 5.7 MongoDB 数据类型

MongoDB 文档底层使用 **BSON**。在 `mongosh` 中看起来像 JSON，但实际比 JSON 多了 `ObjectId`、`Date`、`Long`、`Decimal128`、`BinData` 等类型。

| 类型 | 示例 | 常见用途 / 注意点 |
|------|------|-------------------|
| `String` | `"Alice"` | 字符串 |
| `Boolean` | `true` / `false` | 布尔值 |
| `Int32` | `NumberInt(100)` | 32 位整数；老脚本中常见 |
| `Long` / `Int64` | `NumberLong("9223372036854775807")` | 64 位整数；大 ID、计数值建议显式使用 |
| `Double` | `3.14` | 浮点数；不适合金额等精确计算 |
| `Decimal128` | `NumberDecimal("19.99")` | 高精度小数；金额、费率等建议使用 |
| `ObjectId` | `ObjectId("64f...")` | 默认 `_id` 类型，包含时间戳信息 |
| `Date` | `ISODate("2026-05-20T08:00:00Z")` | UTC 时间；展示时注意时区 |
| `Array` | `["vip", "active"]` | 数组字段，可建多键索引 |
| `Object` | `{ profile: { city: "SZ" } }` | 嵌套文档，可用点号查询 |
| `Null` | `null` | 空值；与字段不存在不是同一回事 |
| `BinData` | `BinData(0, "...")` | 二进制数据，业务排障中较少直接手写 |

常见写法：

```javascript
db.users.insertOne({
  _id: ObjectId(),
  name: "Alice",
  age: NumberInt(30),
  balance: NumberDecimal("19.99"),
  created_at: ISODate("2026-05-20T08:00:00Z"),
  tags: ["vip", "active"],
  profile: {
    city: "Shenzhen"
  }
})
```

> ⚠ **运维提醒**
>
> - JSON 文本里的数字不一定能保留业务期望的整数宽度；大整数建议显式使用 `NumberLong("...")`。
> - 金额、费率不要用普通浮点数表达，优先使用 `NumberDecimal("...")`。
> - `Date` 在 MongoDB 内部按 UTC 存储；排查日志和业务时间时要统一时区。
> - `{ field: null }` 会匹配字段值为 `null` 的文档，也可能匹配字段不存在的文档；需要严格区分时结合 `$exists`。

---

## 5.8 运维常用一条命令（拓扑相关）

### 🔗 副本集状态

先用 `db.isMaster()` 快速判断当前连接到的节点角色、主库是谁、复制集成员有哪些。

```javascript
db.isMaster()
```

典型输出示例：

```javascript
{
  ismaster: true,
  secondary: false,
  setName: "rs0",
  hosts: [
    "10.0.0.1:27017",
    "10.0.0.2:27017",
    "10.0.0.3:27017"
  ],
  primary: "10.0.0.1:27017",
  me: "10.0.0.1:27017",
  ok: 1
}
```

重点看：`ismaster` 是否为 `true`、`secondary` 是否为 `true`、`primary` 指向哪台、`me` 是当前连接节点。MongoDB 新版本也可使用 `db.hello()`，但老集群和历史脚本中常见 `db.isMaster()`。

`rs.status()` 用于查看副本集成员健康、角色和复制状态。

```javascript
rs.status()
```

典型输出示例：

```javascript
{
  set: "rs0",
  date: ISODate("2026-05-20T07:50:00Z"),
  myState: 1,
  members: [
    {
      name: "10.0.0.1:27017",
      stateStr: "PRIMARY",
      health: 1,
      optimeDate: ISODate("2026-05-20T07:49:58Z")
    },
    {
      name: "10.0.0.2:27017",
      stateStr: "SECONDARY",
      health: 1,
      optimeDate: ISODate("2026-05-20T07:49:57Z")
    },
    {
      name: "10.0.0.3:27017",
      stateStr: "ARBITER",
      health: 1
    }
  ],
  ok: 1
}
```

重点看：`myState: 1` 表示当前节点是 PRIMARY，`stateStr` 表示成员角色，`health: 1` 表示成员健康。排查复制延迟时可对比各成员的 `optimeDate`。

### 🧱 分片集群状态

```javascript
sh.status()
```

典型输出示例：

```text
shardingVersion
{ _id: 1, clusterId: ObjectId("...") }

shards
[
  { _id: "shard01", host: "shard01/10.0.1.1:27017,10.0.1.2:27017" },
  { _id: "shard02", host: "shard02/10.0.2.1:27017,10.0.2.2:27017" }
]

active mongoses
[
  "5.0.24"
]

databases
[
  {
    database: {
      _id: "myapp",
      primary: "shard01",
      partitioned: true
    },
    collections: {
      "myapp.orders": {
        shardKey: { user_id: "hashed" },
        unique: false,
        balancing: false,
        chunks: [
          { shard: "shard01", nChunks: 8 },
          { shard: "shard02", nChunks: 8 }
        ]
      }
    }
  }
]
```

重点看：`shards` 是否符合预期、库是否 `partitioned`、集合的 `shardKey`、`balancing` 状态，以及 `chunks` 在各 shard 上是否明显倾斜。

具体拓扑与在蓝鲸 DBM 中的入口见 [第 2 章](./02-cluster-topology.md)。

---

## 5.9 边界说明

- 本章不覆盖**聚合管道（aggregation）**、**多文档事务**、**Change Streams**、**分片键与 balancer** 等；请参阅官方手册。
- 权限以部署侧配置的认证规则为准；`db.runCommand({ connectionStatus: 1 })` 可查看当前认证用户等信息。

> 📘 **官方入口**
> [MongoDB Manual](https://www.mongodb.com/docs/manual/) · [mongosh 文档](https://www.mongodb.com/docs/mongodb-shell/)

---

[⬅ 上一章：04 · 工单系统](./04-tickets.md) | [📖 返回目录](./README.md) | [下一章：06 · bk-dbmon ➡](./06-bk-dbmon.md)

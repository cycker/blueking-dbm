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
- **连接字符串细节**：见 [第 10 章 · 连接 URI & readPreference](./10-uri-readpref.md)。

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
show collections            // 当前库下的集合
db.getName()                // 当前库名
```

对集合的操作统一写为：`db.<集合名>.<方法>(...)`，例如 `db.users.find()`。

---

## 5.4 基础 CRUD

下列示例中集合名为 `users`。

### 插入

```javascript
db.users.insertOne({ name: "Alice", age: 30 })
db.users.insertMany([{ name: "Bob" }, { name: "Carol", tags: ["vip"] }])
```

### 查询

```javascript
db.users.find()                              // 全表扫描式列出（生产慎用）
db.users.findOne({ name: "Alice" })          // 一条
db.users.find({ age: { $gte: 18 } }, { name: 1, _id: 0 })  // 条件 + 投影
db.users.find().limit(10).sort({ age: -1 }) // 排序与限制条数
```

### 更新

```javascript
db.users.updateOne(
  { name: "Alice" },
  { $set: { age: 31 }, $currentDate: { lastModified: true } }
)
db.users.replaceOne({ name: "Bob" }, { name: "Bob", age: 0 })  // 整文档替换
```

### 删除

```javascript
db.users.deleteOne({ name: "Carol" })
db.users.deleteMany({ age: { $lt: 18 } })
```

### SQL 对照（关键词）

| SQL | MongoDB（典型） |
|---|---|
| `SELECT * FROM users WHERE id = 1` | `db.users.find({ _id: 1 })` |
| `SELECT name FROM users LIMIT 10` | `db.users.find({}, { name: 1, _id: 0 }).limit(10)` |
| `INSERT INTO users ...` | `insertOne` / `insertMany` |
| `UPDATE users SET age=31 WHERE name='Alice'` | `updateOne` + `$set` |
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

## 5.7 运维常用一条命令（拓扑相关）

### 🔗 副本集状态

```javascript
rs.status()
```

查看成员角色与健康（需在副本集成员上执行）。

### 🧱 分片集群状态

```javascript
sh.status()
```

查看分片与块分布摘要。

具体拓扑与在蓝鲸 DBM 中的入口见 [第 2 章](./02-cluster-topology.md)。

---

## 5.8 边界说明

- 本章不覆盖**聚合管道（aggregation）**、**多文档事务**、**Change Streams**、**分片键与 balancer** 等；请参阅官方手册。
- 权限以部署侧配置的认证规则为准；`db.runCommand({ connectionStatus: 1 })` 可查看当前认证用户等信息。

> 📘 **官方入口**
> [MongoDB Manual](https://www.mongodb.com/docs/manual/) · [mongosh 文档](https://www.mongodb.com/docs/mongodb-shell/)

---

[⬅ 上一章：04 · 工单系统](./04-tickets.md) | [📖 返回目录](./README.md) | [下一章：06 · bk-dbmon ➡](./06-bk-dbmon.md)

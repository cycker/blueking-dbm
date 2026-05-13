# MongoDB Shell 语法入门（mongosh）

面向有 MySQL / Redis 使用经验、需要快速上手 MongoDB 交互的运维人员。仅覆盖日常排障与验活常用写法；聚合、事务、分片键设计等请参考 [MongoDB 官方文档](https://www.mongodb.com/docs/manual/)。

**相关文档**：[MongoDB 运维指南（蓝鲸 DBM）](./mongodb-ops-guide.md) · [bk-dbmon 使用指引](./mongodb-bk-dbmon-guide.md) · [版本特性概览](./mongodb-version-features-2.4-8.md) · [可升级版本 API](../api/mongodb_list_available_versions.md)

---

## 1. 环境与连接

推荐使用 **mongosh**（MongoDB Shell）。旧版 `mongo` 已弃用，新集群请以 mongosh 为准。

连接方式与 MySQL 客户端类似：指定主机、端口、认证库与用户密码；副本集常在连接串中带上 `replicaSet` 参数。

```bash
# 示例：直连单节点或经 mongos 访问（按环境替换主机、端口、用户）
mongosh "mongodb://user:password@host1:27017,host2:27017/admin?replicaSet=rs0"
```

- **SRV 记录**：`mongodb+srv://...` 常用于云或托管服务解析种子列表。
- **与 MySQL 对照**：`mysql -h host -P 3306 -u user -p` → mongosh 通常用 URI 或 `--host` / `--port` / `--username` 等参数（见 `mongosh --help`）。

---

## 2. 层次与命名

| MongoDB | 可类比 MySQL | 说明 |
|---------|--------------|------|
| database | database | `use <db>` 切换当前库 |
| collection | table | 无固定 schema，文档结构可不同 |
| document | row | BSON/JSON 文档 |
| field | column | 嵌套对象与数组即子结构 |

**命名空间（namespace）**：`<database>.<collection>`，例如 `app.users`。

---

## 3. 必会命令（交互式）

进入 mongosh 后：

```javascript
show dbs                    // 列出可见数据库（需权限）
use myapp                   // 切换当前数据库（不存在则延后创建）
show collections            // 当前库下的集合
db.getName()                // 当前库名
```

对集合的操作统一写为：`db.<集合名>.<方法>(...)`，例如 `db.users.find()`。

---

## 4. 基础 CRUD

下列示例中集合名为 `users`。

### 插入

```javascript
db.users.insertOne({ name: "Alice", age: 30 })
db.users.insertMany([{ name: "Bob" }, { name: "Carol", tags: ["vip"] }])
```

### 查询

```javascript
db.users.find()                              // 全表扫描式列出（生产慎用）
db.users.findOne({ name: "Alice" })         // 一条
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

### 与 SQL 对照（关键词）

| SQL | MongoDB（典型） |
|-----|-----------------|
| `SELECT * FROM users WHERE id = 1` | `db.users.find({ _id: 1 })` 或使用 ObjectId |
| `SELECT name FROM users LIMIT 10` | `db.users.find({}, { name: 1, _id: 0 }).limit(10)` |
| `INSERT INTO users ...` | `insertOne` / `insertMany` |
| `UPDATE users SET age=31 WHERE name='Alice'` | `updateOne` + `$set` |
| `DELETE FROM users WHERE ...` | `deleteOne` / `deleteMany` |

`_id`：若插入时不指定，服务端会生成 **ObjectId**。在 shell 中可用 `ObjectId("hexstring")` 构造。

---

## 5. 常用查询运算符（极简）

| 运算符 | 含义 | 示例 |
|--------|------|------|
| `$eq` / `$ne` | 等于 / 不等于 | `{ status: { $ne: "deleted" } }` |
| `$gt` / `$gte` / `$lt` / `$lte` | 比较 | `{ age: { $gte: 18 } }` |
| `$in` / `$nin` | 在列表中 / 不在 | `{ type: { $in: ["a", "b"] } }` |
| `$and` / `$or` | 与 / 或 | `{ $or: [ { a: 1 }, { b: 2 } ] }` |
| `$regex` | 正则 | `{ name: { $regex: /^A/ } }` |

逻辑与：同一对象内多字段默认 **AND**。

---

## 6. 索引入门

```javascript
db.users.createIndex({ name: 1 }, { unique: true })   // 单字段升序，唯一
db.users.createIndex({ lastLogin: -1 })              // 降序
db.users.getIndexes()                               // 查看索引
db.users.dropIndex("name_1")                        // 按索引名删除（名以实际为准）
```

与 MySQL 类似：大集合上无索引的 `find` 易导致 CPU/IO 压力，排障时先 `explain("executionStats")`（进阶，此处不展开）。

---

## 7. 运维常用一条命令（拓扑相关）

- **副本集**：`rs.status()` —— 查看成员角色与健康（需在副本集成员上执行）。
- **分片集群**：`sh.status()` —— 查看分片与块分布摘要。

具体拓扑与在 **蓝鲸 DBM** 中的入口见 [运维指南](./mongodb-ops-guide.md)。

---

## 8. 边界说明

- 本文不覆盖 **聚合管道（aggregation）**、**多文档事务**、**Change Streams**、**分片键与 balancer** 等；请参阅官方手册对应章节。
- 权限以部署侧配置的认证规则为准；`db.runCommand({ connectionStatus: 1 })` 可查看当前认证用户等信息。

**官方入口**：[MongoDB Manual](https://www.mongodb.com/docs/manual/) · [mongosh 文档](https://www.mongodb.com/docs/mongodb-shell/)

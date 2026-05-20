# 第 8 章 · mongodump / mongorestore 与 MongoDB 工具集

> MongoDB 官方提供了一组独立分发的 **Database Tools**（自 4.4 起独立打包，版本号体系 `100.x`），覆盖 **逻辑备份/恢复、JSON/CSV 导入导出、文件传输、监控、在线诊断** 等场景。
> 本章按「**用得最多 → 偶尔用 → 排障用**」的顺序，整理实战常用参数、坑位与与 DBM 的对接方式。

> 📦 **独立分发**
> 从 MongoDB 4.4 开始，`mongodump / mongorestore / mongoexport / mongoimport / mongostat / mongotop / mongofiles / bsondump` 被剥离为独立的 [MongoDB Database Tools](https://www.mongodb.com/docs/database-tools/) 包，版本号统一为 `100.x`（如 `mongodump.100.7`）。
> 早期 2.4 / 3.x / 4.0 / 4.2 仍随 server 一起发布，蓝鲸 DBM 在介质目录下按版本提供 `mongodump.2.4 / mongodump.3.0 / mongodump.3.2 / mongodump.3.4 / mongodump.3.6 / mongodump.4.0 / mongodump.4.2 / mongodump.100.7` 等多版本副本。

---

## 9.1 工具家族总览

| 工具 | 类别 | 典型用途 | 等价 MySQL 类比 |
| --- | --- | --- | --- |
| `mongodump` | 逻辑备份 | 导出 BSON 格式备份；支持按库/集合 / 全量；可选 `--oplog` 一致性快照 | `mysqldump --single-transaction` |
| `mongorestore` | 逻辑恢复 | 从 mongodump 产物恢复；支持改名、重映射、并行集合 | `mysql < backup.sql` |
| `mongoexport` | 逻辑导出 | 导出 **JSON/CSV**，用于跨系统交换数据 | `SELECT INTO OUTFILE` |
| `mongoimport` | 逻辑导入 | 导入 **JSON/CSV/TSV** | `LOAD DATA INFILE` |
| `bsondump` | 调试 | 把 `.bson` 文件转成 JSON 直接看 | `mysqlbinlog` |
| `mongostat` | 实时监控 | 每秒打印 insert/query/update/delete/conn 等指标 | `mysqladmin extended` |
| `mongotop` | 实时监控 | 按 collection 统计读写时间分布 | — |
| `mongofiles` | GridFS | 命令行操作 GridFS 文件（put/get/list/delete） | — |
| `mongosh` | 交互 Shell | 新一代 Shell，详见 [第 5 章](05-mongosh.md) | `mysql` |

> ⚠ **版本与 server 兼容**
> 建议 `tools 版本 ≥ server 版本`。低版本工具连接高版本 server 可能出现 `command not supported`、`oplog 字段无法识别`、`Extended JSON v1 vs v2` 等问题。蓝鲸 DBM 介质中常用 `100.7.1` 兼容 4.4 / 5.0 / 6.0。

---

## 9.2 mongodump · 逻辑备份

`mongodump` 用于把数据导出为 **BSON**（文档原始二进制） + **metadata.json**（索引等元信息），目录结构为：

```
dump/
└── <database>/
    ├── <collection>.bson           # 数据
    └── <collection>.metadata.json  # 索引、collation 等
```

### 常用参数速查

| 参数 | 说明 |
| --- | --- |
| `--uri` / `-h --port -u -p` | 连接串 / 拆开传；URI 形式建议加引号 |
| `-d <db>` / `-c <coll>` | 限定库 / 集合，不写则全量 |
| `-q '<json>'` | 条件过滤，等价 `find()` 的 filter |
| `-o <dir>` | 输出目录；默认 `./dump` |
| `--gzip` | 每个 `.bson` 单独 gzip 压缩 |
| `--archive=FILE` | 归档为 **单个文件**（避免一堆小文件），可与 `--gzip` 配合 |
| `--oplog` | 备份开始/结束时点的 oplog，用于 **一致性恢复**（仅副本集成员可用） |
| `--numParallelCollections N` | 并行备份的集合数（默认 4） |
| `--readPreference` | 建议 `secondary` 减小主库压力 |
| `--excludeCollection` / `--excludeCollectionsWithPrefix` | 排除集合（如 `system.profile`） |
| `--authenticationDatabase admin` | 常见为 `admin` |

### 四种典型用法

**A · 全实例备份**

```bash
# 全量备份（含所有库），输出到 ./dump 目录
mongodump \
  --uri="mongodb://dba:passwd@1.1.1.1:27017,1.1.1.2:27017/admin?replicaSet=rs0" \
  --readPreference=secondary \
  -o /data/dbbak/dump-$(date +%Y%m%d%H%M)
```

**B · 单库 / 单集合**

```bash
# 只备份 testa 库
mongodump -h 1.1.1.1:27017 -u dba -p passwd --authenticationDatabase=admin \
  -d testa -o /data/dbbak/

# 只备份 testa.col2 集合（带 gzip）
mongodump -h 1.1.1.1:27017 -u dba -p passwd --authenticationDatabase=admin \
  -d testa -c col2 --gzip -o /data/dbbak/

# 带条件过滤：只导某用户最近一周的数据
mongodump -d game -c log -q '{"uin":12345,"ts":{"$gt":{"$date":"2025-05-01T00:00:00Z"}}}' \
  -o /data/dbbak/
```

**C · 一致性 + 归档**

```bash
# 一致性归档：单文件 + gzip + oplog
mongodump \
  --uri="mongodb://dba:passwd@1.1.1.1:27017/?replicaSet=rs0" \
  --oplog \
  --archive=/data/dbbak/full-$(date +%F).archive.gz \
  --gzip

# 文件名由 dbm 内部规约：mongodump-{name}-FULL-{ip}-{port}-{ymdh}-{ts}.archive.gz
# DBM 自带备份程序生成的文件名遵循该规约，便于 PITR 恢复时解析
```

**D · 大集合并行 + 二级节点**

```bash
# 大集合：并行 + 走 secondary，避免拖主库
mongodump \
  --uri="mongodb://dba:passwd@host1:27017,host2:27017/admin?replicaSet=rs0&readPreference=secondary" \
  --numParallelCollections=8 \
  -d bigdb \
  --gzip \
  -o /data/dbbak/

# 只在副本集 secondary 节点登机直连备份（避免被选主切换打断）
# 此时可省去 readPreference 直连本地 27017
```

> ⛔ **分片集群（mongos） + LB 的踩坑（来自 IegMongoTeam 真实案例）**
> 通过 **域名 / CLB VIP** 连 mongos 跑 `mongodump`，可能报 `CursorNotFound`。原因：mongodump 内部会建立 **2 条连接**，若 LB 没开启 **会话保持**，两条连接落到不同 mongos，cursor 失效。
> 解决：① 直接连一个 mongos IP；或 ② LB 开启会话保持；或 ③ 用 URI 写多个 mongos seedlist。
> *所有「多连接客户端」（mongodump、mongorestore、自定义 driver 程序）都要确认 LB 设置。*

---

## 9.3 mongorestore · 逻辑恢复

`mongorestore` 是 `mongodump` 的镜像操作。基本流程：先恢复数据 → 再重建索引；如带 `--oplogReplay` 则会回放 oplog 实现一致性。

### 常用参数速查

| 参数 | 说明 |
| --- | --- |
| `--archive=FILE` / `--gzip` | 从归档恢复（与 dump 时呼应） |
| `--drop` | 恢复前 **先 drop 同名集合**（不会 drop 整库） |
| `--oplogReplay` | 回放 dump 期间的 `oplog.bson` |
| `--nsInclude` / `--nsExclude` | 按命名空间通配符筛选，如 `game.*` |
| `--nsFrom` / `--nsTo` | 命名空间 **重命名**，例 `--nsFrom 'old.*' --nsTo 'new.*'` |
| `--numParallelCollections` / `--numInsertionWorkersPerCollection` | 并行集合 / 集合内并行（小心打满主） |
| `--noIndexRestore` | 跳过索引恢复（用于先导数据后异步建索引） |
| `--maintainInsertionOrder` | 保留插入顺序（默认 false 以提高吞吐） |
| `--writeConcern '{w:0}'` | 大量恢复时降低 wc 提速；恢复完务必 **一致性校验** |
| `--dryRun` | 只演练，不真写 |

### 常见恢复方式

**A · 目录恢复**

```bash
# 从目录恢复，drop 同名集合避免主键冲突
mongorestore \
  --uri="mongodb://dba:passwd@1.1.1.2:27017/?replicaSet=rs1" \
  --drop \
  /data/dbbak/dump-202505140100/
```

**B · 归档恢复**

```bash
# 从单文件归档 + gzip 恢复
mongorestore \
  --uri="mongodb://dba:passwd@1.1.1.2:27017/admin" \
  --archive=/data/dbbak/full-2025-05-14.archive.gz \
  --gzip \
  --drop
```

**C · 改库改表名**

```bash
# 把 testa 库恢复到 testa_recover 库（常用于回档/构造数据）
mongorestore \
  --uri="mongodb://dba:passwd@1.1.1.2:27017/admin" \
  --nsFrom='testa.*' \
  --nsTo='testa_recover.*' \
  /data/dbbak/dump-202505140100/

# 只恢复 game.log 集合
mongorestore --nsInclude='game.log' /data/dbbak/dump-xxx/
```

**D · PITR · oplog 回放**

```bash
# 1. mongodump 时记录 oplog（产物中会多出 oplog.bson）
mongodump --oplog --archive=/data/dbbak/full.archive

# 2. 恢复时回放 oplog 到一致点
mongorestore --archive=/data/dbbak/full.archive --oplogReplay

# 3. 进一步 PITR：用 dbm-services/mongo-toolkit-go 的 pitr_recover
#    可基于 mongodump-*-FULL + mongodump-*-INCR-*-oplog.rs.bson(.gz/.zst)
#    指定 --target-time 恢复到任意秒级时间点
```

> 💡 **性能调优 4 条建议**
> ① 大库恢复期间临时降低 `writeConcern` 至 `{w:1}` 甚至 `{w:0}`；
> ② 恢复完 **立刻校验集合 count、关键索引存在**；
> ③ 索引可拆开：先用 `--noIndexRestore` 灌数据，再 `db.coll.createIndex(...)` 异步建；
> ④ 全实例恢复时 **关闭 balancer**（仅分片集群）：`sh.stopBalancer()`。

---

## 9.4 mongoexport / mongoimport · JSON/CSV 交换

与 mongodump 不同：`mongoexport` 输出 **纯文本 JSON / CSV**，**会丢失 BSON 类型保真度**（如 `NumberLong`、`ObjectId` 在 v1 模式下变成字符串）。

**跨 MongoDB 集群迁移请用 dump/restore，跨系统数据交换才用 export/import**。

### 📤 mongoexport · 导出 JSON / CSV

```bash
# 导 JSON
mongoexport -h 1.1.1.1:27017 -u dba -p pwd \
  -d game -c users \
  -q '{"vip":true}' \
  -o /tmp/vip.json

# 导 CSV，必须显式 --type=csv 并指定 --fields
mongoexport -d game -c users \
  --type=csv \
  --fields=_id,name,age,vip \
  -o /tmp/users.csv
```

### 📥 mongoimport · 导入 JSON / CSV / TSV

```bash
# 导 JSON（每行一个文档）
mongoimport -h 1.1.1.2:27017 -u dba -p pwd \
  -d game -c users \
  --file=/tmp/vip.json

# 导 CSV（首行为表头）
mongoimport -d game -c users \
  --type=csv --headerline \
  --file=/tmp/users.csv \
  --mode=upsert        # insert/upsert/merge/delete
```

> ⚠ **JSON 模式：v1 vs v2**
> `--jsonFormat=canonical`（v2，**类型保真**，如 `"$numberLong":"..."`）
> / `--jsonFormat=relaxed`（v2，更易读）
> / `--jsonFormat=legacy`（v1，老格式）。
> 跨版本迁移建议用 `canonical`，避免精度丢失。

---

## 9.5 mongostat / mongotop · 实时观测

用于「**登机即时看实例压力分布**」，特别是在告警未触达、监控大盘看不出来时。

### mongostat

```bash
mongostat --uri="mongodb://dba:pwd@1.1.1.1:27017/admin" 2 30
# 每 2 秒采样一次，采样 30 次

# 输出列含义（最常看的几个）：
#   insert/query/update/delete/getmore/command   每秒 ops
#   dirty/used                                  WT cache 脏页/使用率（接近 20% 触发刷盘）
#   qrw                                          排队的读/写（>0 长时间则是慢）
#   ar|aw                                        active reader/writer
#   conn                                         当前连接数
#   net_in/net_out                               网络吞吐
```

### mongotop

```bash
mongotop --uri="mongodb://dba:pwd@1.1.1.1:27017/admin" 2
# 每 2 秒一次按 collection 列出 read/write 占用毫秒数
```

> 📌 **排障套路**
> ① 业务报慢 → `mongostat 1` 看 qr/qw、dirty/used；
> ② 锁定可疑 collection → `mongotop 2`；
> ③ 进 `mongosh` 执行 `db.currentOp({"secs_running":{$gt:1}})` 抓慢操作；
> ④ 必要时 `db.killOp(opid)` 终止。

---

## 9.6 bsondump / mongofiles · 文件级工具

### 🔍 bsondump

直接把 `.bson` 文件内容打成 JSON，用于 **不连库** 的离线查看：

```bash
# 看一眼某个备份目录里的 oplog.rs.bson 都有什么
bsondump dump/local/oplog.rs.bson | head -20
bsondump --type=debug dump/game/users.bson | less
```

### 🗂 mongofiles · 操作 GridFS

命令行把大文件存到 MongoDB 的 GridFS（fs.files / fs.chunks 集合）。

```bash
mongofiles --uri=... -d gridfs put /path/big.zip
mongofiles --uri=... -d gridfs list
mongofiles --uri=... -d gridfs get big.zip
mongofiles --uri=... -d gridfs delete big.zip
```

---

## 9.7 备份策略与 DBM 命名规约

蓝鲸 DBM 的 bk-dbmon 在 `/data/dbbak/mg/mongodump/` 下生成两类备份产物，文件名解析见 `dbm-services/mongodb/db-tools/mongo-toolkit-go/toolkit/pitr/filename.go`：

| 类型 | 格式（示例） | 用途 |
| --- | --- | --- |
| FULL · 全量 | `mongodump-{name}-FULL-{ip}-{port}-{ymdh}-{yyyymmddHHMMSS}.archive.gz` | 定点恢复的基准 |
| INCR · 增量 oplog | `mongodump-{name}-INCR-{ip}-{port}-{ymdh}-{i}-{yyyymmddHHMMSS}.oplog.rs.bson.gz` | 叠加在 FULL 之上回放至目标时点 |

支持的压缩后缀：`.tar / .tar.gz / .archive / .archive.gz / .archive.zst / .archive.zstd / .oplog.rs.bson / .oplog.rs.bson.gz / .oplog.rs.bson.zst`。

### cluster_config.go 中的备份配置项（节选）

```go
{Segment: SegmentBackup, Key: KeyArchive,                Value: ValueFalse}  // mongodump --archive 单文件归档，默认 false
{Segment: SegmentBackup, Key: KeyNumParallelCollections, Value: "0"}         // 并行备份的集合数，0 表示用 mongodump 默认
```

> 🧪 **每次备份后做 3 件事**
> ① `bsondump` 抽 1 个集合看是否可解析；
> ② 抽样 `mongorestore --dryRun`；
> ③ 校验 **FULL + 最近一段 INCR** 是否覆盖业务侧 RPO（一般 ≤15 min）。

---

## 9.8 边界与官方文档入口

- 本章不覆盖：**物理快照（cp/rsync data 目录）、percona-backup-mongodb（PBM）、Atlas Cloud Backup**；如需自建快照请参考 [官方文件系统快照文档](https://www.mongodb.com/docs/manual/tutorial/backup-with-filesystem-snapshots/)。
- **分片集群一致性备份**：mongodump 不能保证 mongos 视角的全局一致；若必须，需借助 PBM 或停 balancer + 同时刻 dump 各分片。
- **性能影响**：所有逻辑工具都会引发 **WT cache 占用 + 网络拷贝**；务必走 secondary，避开高峰期。

> 📘 **官方入口**
> [Database Tools](https://www.mongodb.com/docs/database-tools/) ·
> [mongodump](https://www.mongodb.com/docs/database-tools/mongodump/) ·
> [mongorestore](https://www.mongodb.com/docs/database-tools/mongorestore/) ·
> [mongoexport](https://www.mongodb.com/docs/database-tools/mongoexport/) ·
> [mongoimport](https://www.mongodb.com/docs/database-tools/mongoimport/)

---

⬅ [上一章：第 7 章 · 版本支持与升级](07-versions.md) ｜ [返回目录](README.md) ｜ [下一章：第 9 章 · MongoDB 日志 ➡](09-mongodb-logs.md)

# 第 6 章 · MongoDB bk-dbmon 使用指引

> **bk-dbmon** 是部署在 MongoDB 机器上的**本地守护进程**，负责例行任务（备份、心跳、健康检查），并通过 **bkmonitorbeat** 与蓝鲸监控体系对接。

📦 **源码与脚本路径**
- 进程：`dbm-services/mongodb/db-tools/dbmon/`
- 安装编排：`flow/.../mongodb_install_dbmon.py`
- 节点执行：`dbactuator/pkg/atomjobs/atommongodb/install_dbmon.go`

---

## 6.1 作用概述

根据仓库内 README 描述，bk-dbmon 提供**本地例行任务**能力，典型包括：

| 能力 | 说明 |
|------|------|
| 💾 **例行备份** | 本机备份计划与上报相关任务 |
| 💓 **心跳与健康检查** | 周期性探测 `mongod` / `mongos` 端口与认证 |
| 📡 **结果上报** | 写入本机目录后由 **bkmonitorbeat** 上报至蓝鲸监控 |

事件类行为示例（如认证失败、实例状态异常、尝试拉起进程等）见仓库 README。

---

## 6.2 在 DBM 中如何安装 / 更新

### 工单类型与权限
- 单据类型：**MongoDB 安装 DBMon** → 常量 `MONGODB_INSTALL_DBMON`
- IAM 动作 ID 一般为 `mongodb_install_dbmon`（见 `iam_app/migration_json_files/initial.json`）
- 菜单名称以你环境蓝鲸权限中心为准

> ⚠ **UI 入口提示**：当前仓库前端 `TicketTypes` 枚举中可能未单独列出该类型，但**后端工单与 IAM 已定义**。若控制台未展示入口，可通过**工单 API / 运维二次开发菜单**或联系平台管理员开启。

### 平台实际做了什么（摘要）

1. **拉取介质包**：从介质库拉取 **dbactuator、dbmon、dbtools、mongo-toolkit** 等包的最新或指定版本（`get_pkg_info()`）。
2. **下发到节点**：下发到节点工作目录（`MongoUtil().get_mongodb_os_conf()["file_path"]`）。
3. **执行 InstallDBMon**：通过 dbactuator 执行 `MongoDBActuatorActionEnum.InstallDBMon`，以 `root` 执行、`sudo_account` 为 `mysql`。
4. **注入默认配置**：注入 `http_address`: `127.0.0.1:6677`、`report_save_dir`（如 `/home/mysql/report`）及 **bkmonitorbeat** 配置。

### 随其它工单自动安装

以下场景会在主流程中**嵌入** `add_install_dbmon`，**不必单独提单**：

- MongoDB 集群部署
- 扩缩容
- 集群标准化
- 整机替换 / 迁移等子流程

---

## 6.3 Flow 入参（API）

编排类入口：`MongoDBController.install_dbmon` → `MongoInstallDBMonFlow`

```http
POST /apis/v1/flow/scene/mongo_install_dbmon
```

### Body 字段

| 字段 | 说明 |
|------|------|
| `uid` | 工单 UID |
| `created_by` | 提单人 |
| `bk_biz_id` | 蓝鲸业务 ID |
| `ticket_type` | 工单类型 |
| `action` | 动作 |
| `bk_cloud_id` | 云区域 ID（必须与集群一致） |
| `infos` | 字符串列表，见下方 3 种支持形态 |

### `infos` 支持形态

| # | 形态 | 说明 |
|---|------|------|
| 1 | **主机 IP** | 直接在该机安装 / 更新 bk-dbmon |
| 2 | **集群 ID** | 纯数字，会展开为该集群下的 IP 列表 |
| 3 | **集群域名** | 以 `.db` 结尾的域名，会先解析为集群 ID 再展开 IP |

> 🚫 **校验**：`bk_cloud_id` 必须与集群所属云区域一致，否则流程会校验失败。

---

## 6.4 安装路径与配置

### 目录约定（与 dbactuator 实现一致）

| 项 | 路径 / 说明 |
|----|-------------|
| 安装目录 | `/home/mysql/bk-dbmon/` |
| 主配置 | `dbmon-config.yaml`（与可执行文件同目录） |
| 启动脚本 | `start.sh` / `stop.sh` |
| 本地上报目录示例 | `/home/mysql/report`（流程默认值） |

### 进程与自检

- `start.sh` 会读取配置中的 `http_address`，并请求 `http://<http_address>/health` 判断 bk-dbmon 是否已存活。
- 未启动则 `nohup ./bk-dbmon --config=dbmon-config.yaml` 拉起。
- 可为 `start.sh` 传入 `debug` 以开启调试日志。

### 配置示例（字段含义）

| 字段 | 含义 |
|------|------|
| `report_save_dir` / `report_left_day` | 本机结果保留目录与天数 |
| `http_address` | HTTP 管理地址（默认 `127.0.0.1:6677`） |
| `bkmonitorbeat` | 包含 `agent_address` / `beat_path` / `event_config` / `metric_config` |
| `servers` | 由流程中的 `PrepareInstanceInfo` 填充，**勿手改** |

---

## 6.5 常用命令（在实例机上）

> 以下命令在 `/home/mysql/bk-dbmon` 目录下执行；若企业自定义安装路径，以实际为准。

### 启停

```bash
cd /home/mysql/bk-dbmon
sh start.sh          # 启动（后台），并尝试加入 crontab 每 2 分钟自检拉起
sh stop.sh           # 停止
```

### 元数据 meta

```bash
./bk-dbmon meta list --port all
./bk-dbmon meta list --port 27017,27018
./bk-dbmon meta delete --port 27017,27018   # 清理无效或已下线实例
```

`--port` 支持：`27017`、`27017,27018`、`all`、`0`（`0` 与 `all` 语义见 `package/readme.md`）。

### 告警 alarm

```bash
./bk-dbmon alarm shield  --port all
./bk-dbmon alarm unblock --port 27017,27018
./bk-dbmon alarm list    --port 27017,27018
```

平台在**版本升级**等流程中也会通过脚本调用 `alarm shield` / `unblock` / `meta delete`，避免维护窗口误报。

### 动态配置 config

```bash
./bk-dbmon config get-all --port all
./bk-dbmon config set --port all -s backup -k enable -V false   # 示例：关闭备份段
./bk-dbmon config set --port all -s parselog -k enable -V false
```

**parselog** 默认开启：tail 实例 `mongo.log`，将 **2.4 文本 / 3.0～4.2 文本 / 4.4+ JSON** 等形态统一写成 **`jsonlog/` 下 JSON 行**（不改动源日志）。解析器版本、输出路径与限流见 [第 9 章 · MongoDB 日志](09-mongodb-logs.md)。

具体 segment / key 以 `bk-dbmon config` 在线帮助与版本为准。

### 连接 mongosh

```bash
sh conn.sh 27017
sh conn.sh 27017 "db.serverStatus().ok"
sh conn.sh all   "db.adminCommand({ ping: 1 })"
```

---

## 6.6 日常备份策略

bk-dbmon 内置 **backup** 段，是 MongoDB 集群**日常备份的执行者**。它以本地守护进程的方式在每台机器上独立调度，**只在 backup 节点（priority=0、hidden=true）上真正发起备份**，从而避免对线上读写造成 IO / CPU 抖动（详见 [§2.1 副本集拓扑](02-cluster-topology.md)）。

### 顶部要点

| 维度 | 说明 |
|------|------|
| 🎯 **谁来备份** | 副本集：**backup 节点** 独占执行<br/>分片集群：**每个 shard 的 backup 节点** + **configsvr 的 backup 节点** |
| ⏰ **什么时候备** | 默认在业务低峰窗口（如 02:00-06:00）调度；由 dbmon 巡检触发，无需手工执行 |
| 📦 **怎么备** | `AUTO` 模式：按间隔自动选择 **FULL 全量** 或 **INCR 增量 oplog**<br/>产物落盘 `/data/dbbak/mg/mongodump/`<br/>可选 gzip / zstd 压缩 |

### 备份执行流程

1. **巡检与角色判定**：dbmon 周期巡检本机所有实例，读取 `cluster-config.yaml` 中 `backup.enable`，并通过 `rs.isMaster()` / `rs.conf()` 判断当前节点是否为 **backup 节点**。**仅 backup 节点**触发后续步骤。
2. **执行 mongodump**：调用 `mongo-toolkit-go` 包内的 `mongodump`，目标路径 `/data/dbbak/mg/mongodump/<cluster>/<ip>_<port>_<yyyymmdd_hhmmss>/`，连接串使用本地 `127.0.0.1:<port>`，readPreference 直连本节点，避免跨网络。
3. **打包 / 上报元数据**：备份完成后压缩成 `.tar` 或 `.tar.gz`，并把**备份元数据**（集群、实例、起止时间、文件大小、状态）写到本地 `report` 目录，由 **bkmonitorbeat** 上报蓝鲸监控。
4. **过期清理**：按 `backup.keepDays` 清理本机 `/data/dbbak/mg/mongodump/` 下的过期文件，避免占满磁盘；如对接对象存储/备份系统，则在上传成功后由保留策略统一清理。

### 增量备份策略（PITR）

MongoDB 的增量备份不是“复制一份新增数据文件”，而是基于副本集 **oplog**：全备作为基准，后续周期性导出 `local.oplog.rs` 中的变更记录。PITR 回档时先恢复最近一次 FULL，再按时间顺序回放 INCR oplog 文件到目标时间点。

| 备份类型 | 内容 | 典型间隔 | 用途 |
|----------|------|----------|------|
| **FULL 全量** | `mongodump` 导出的完整逻辑备份 | `fullFreq=86400`（约 1 天） | 定点恢复的基准 |
| **INCR 增量** | `local.oplog.rs` 的 oplog 片段 | `incrFreq=3600`（约 1 小时） | 叠加在 FULL 之后，恢复到更细时间点 |
| **AUTO 自动** | 由工具按 `fullFreq` / `incrFreq` 判断本次该做 FULL 还是 INCR | dbmon 默认调用模式 | 日常备份推荐方式 |

增量备份产物命名遵循 DBM 规约：

```text
mongodump-{name}-FULL-{ip}-{port}-{ymdh}-{yyyymmddHHMMSS}.archive.gz
mongodump-{name}-INCR-{ip}-{port}-{ymdh}-{i}-{yyyymmddHHMMSS}.oplog.rs.bson.gz
```

> ⚠ **增量备份依赖 oplog 窗口**
>
> 如果业务写入量很大、oplog 太小，导致上次增量点已经被覆盖，则 INCR 链会断，PITR 只能回到最近可用 FULL 或重新做全备。部署时的 `oplog_percent`、运行期的 `Oplog Window` 监控都需要一起关注。

> 📌 **分片集群注意**
>
> 分片集群需要每个 shard（以及 configsvr）各自形成 FULL + INCR 链。恢复到一致时间点时，必须使用同一目标时间组织各分片的增量回放；不要只恢复某一个 shard 的 INCR。

### 关键参数（segment：`backup`）

| key | 含义 | 典型值 |
|-----|------|--------|
| `enable` | 是否开启日常备份；关闭后该实例完全跳过备份调度 | `true` |
| `fullFreq` / `full_freq` | 全量备份间隔；多数集群为每日一次 | `86400` 秒 |
| `incrFreq` / `incr_freq` | 增量备份间隔；用于 PITR oplog 链 | `3600` 秒 |
| `startTime` / `endTime` | 允许执行备份的**窗口时段**，错开业务高峰 | `02:00` - `06:00` |
| `keepDays` | 本机备份保留天数 | `3` - `7` |
| `gzip` | 是否开启 gzip 压缩，节省磁盘但增加 CPU | `true` |
| `concurrency` / `numParallelCollections` | mongodump 并发集合数，影响速度与负载 | `4` |

> ⚠ 字段名以当前版本 `./bk-dbmon config get-all --port all` 输出为准；不同版本可能略有差异。

### 产物目录与命名约定

```
/data/dbbak/mg/mongodump/
└── <cluster_domain>/
    └── <ip>_<port>_<yyyymmdd_hhmmss>/
        ├── dump/                   # mongodump 输出（每库一个目录）
        │   ├── admin/
        │   ├── config/
        │   └── <business_db>/
        ├── meta.json               # 备份元数据（集群、实例、起止时间）
        └── done.flag               # 完成标识（缺失则视为失败）
```

详细文件名解析参见 [第 8 章 · mongo-toolkit / 备份产物](08-mongo-tools.md)。

### 跳过备份的两种方式

**A. 实例级关闭（dbmon CLI）**

登录到实例所在机器，关闭 backup 段：

```bash
./bk-dbmon config set --port all \
  -s backup -k enable -V false
```

适用：**临时关停**、紧急止损、**LogDB** 等无需备份的场景。

**B. 集群级标签（DBM 平台）**

在 DBM 集群属性 / Tag 中添加 `backup:no`，**巡检与备份检查会一并跳过**，适合长期不需备份的集群（数据可重建、纯日志库等）。

> ⚠ **常见踩坑**
> - 副本集中**没有 backup 节点** → 全部 Secondary 都未触发备份。请确认至少 1 个节点 `priority=0 + hidden=true`。
> - backup 节点磁盘空间不足 → mongodump 中途失败；建议 `/data/dbbak` 至少预留**数据量 × 1.5** 的空间。
> - 备份时段与**大表 TTL/索引重建**重叠 → IO 争用导致超时；调整 `startTime` 错开。
> - 关闭备份后忘记重新打开 → 监控会上报 **"备份长期缺失"** 告警；变更完毕请及时 `enable=true`。

> ✅ **查看备份是否成功**
> 1. 登录 backup 节点机器，`ls /data/dbbak/mg/mongodump/` 查看当天产物与 `done.flag`；
> 2. 在 DBM 控制台 **集群详情 → 备份记录** 查看（数据来自 dbmon 上报）；
> 3. 实例机本地：`./bk-dbmon meta list --port all` 查看备份段最近一次执行状态。

---

## 6.7 与监控、排障的关系

| 现象 | 排查路径 |
|------|---------|
| 📊 **监控无数据** | 检查本机 **bk-dbmon** 是否运行；`dbmon-config.yaml` 中 **bkmonitorbeat** 路径与 `data_id` / `token` 是否与当前环境一致；检查 GSE / bkmonitorbeat 插件是否正常 |
| 🔕 **误报或维护窗口** | 使用 `alarm shield` 屏蔽，结束后再 `unblock`（与平台升级脚本策略一致） |
| 🧹 **实例已下架仍报端口** | 尝试 `meta delete` 清理残留元数据 |
| 📋 **平台侧排障** | 结合 **工单详情** 与 Job 日志中的 dbactuator 输出（`install_dbmon` / `InstallDBMon` 步骤） |

---

## 6.8 版本与介质

bk-dbmon 安装包在流程中通过 `Package.get_latest_package(..., pkg_type="dbmon", db_type=MongoDB)` 选取（见 `get_pkg_info()`）。

> ✅ **固定版本场景**：若需固定版本，应在 **DBM 介质管理** 中维护可用包，并与环境变更流程对齐。

---

[← 第 5 章 mongosh](05-mongosh.md) | [↑ 返回目录](README.md) | [第 7 章 版本与兼容性 →](07-versions.md) · [第 13 章 性能视图](13-performance-views.md)

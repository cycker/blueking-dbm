# 第 6 章 · MongoDB bk-dbmon 使用指引

> **bk-dbmon** 是部署在 MongoDB 机器上的**本地守护进程**，负责备份、心跳、健康检查、事件上报和本地配置管理，并通过 **bkmonitorbeat** 与蓝鲸监控体系对接。

---

## 6.1 作用概览

| 能力 | 说明 |
|------|------|
| **例行备份** | 按 backup 段配置在 backup 节点执行 FULL / INCR 备份 |
| **健康检查** | 周期性探测 `mongod` / `mongos` 端口、认证和运行状态 |
| **自动拉起** | 发现进程不存在时，尝试在本机拉起实例 |
| **事件上报** | 将登录异常、自动拉起结果等事件上报到蓝鲸监控 |
| **心跳指标** | 上报 `mongo_dbmon_heart_beat`，用于确认 dbmon 自身存活 |
| **本地运维命令** | 提供 meta、alarm、config、conn 等实例机侧辅助命令 |

---

## 6.2 安装与更新

### 入口

| 项 | 说明 |
|----|------|
| 实际入口名称 | **集群标准化** |
| 主要作用 | 对目标集群补齐或更新 bk-dbmon、dbtools、mongo-toolkit 等运维组件 |
| 权限 | 以当前环境蓝鲸权限中心配置为准 |

> ⚠ **UI 入口提示**
>
> 不要按“安装 DBMon”单独找入口；实际在 **集群标准化** 中触发。

### 平台执行内容

1. 从介质库拉取 **dbmon、dbtools、mongo-toolkit** 等包的最新或指定版本。
2. 下发介质到目标节点工作目录。
3. 在目标机器上安装或更新 bk-dbmon，并使用 MongoDB 运维用户运行。
4. 注入默认配置，例如 `http_address: 127.0.0.1:6677`、`report_save_dir`、`bkmonitorbeat` 配置等。

### 自动安装场景

以下场景通常也会自动安装或更新 bk-dbmon，**不必额外走集群标准化**：

- MongoDB 集群部署
- 扩缩容
- 整机替换 / 迁移等维护场景

bk-dbmon 安装包由平台介质管理维护。若需固定版本，应在 **DBM 介质管理** 中维护可用包，并与环境变更流程对齐。

---

## 6.3 本机目录与配置

| 项 | 路径 / 说明 |
|----|-------------|
| 安装目录 | `/home/mysql/bk-dbmon/` |
| 主配置 | `dbmon-config.yaml`（与可执行文件同目录） |
| 启动脚本 | `start.sh` / `stop.sh` |
| 本地上报目录示例 | `/home/mysql/report` |

### 进程与自检

- `start.sh` 会读取配置中的 `http_address`，并请求 `http://<http_address>/health` 判断 bk-dbmon 是否已存活。
- 未启动则 `nohup ./bk-dbmon --config=dbmon-config.yaml` 拉起。
- 可为 `start.sh` 传入 `debug` 以开启调试日志。

### 关键配置字段

| 字段 | 含义 |
|------|------|
| `report_save_dir` / `report_left_day` | 本机结果保留目录与天数 |
| `http_address` | HTTP 管理地址（默认 `127.0.0.1:6677`） |
| `bkmonitorbeat` | 包含 `agent_address` / `beat_path` / `event_config` / `metric_config` |
| `servers` | 本机托管实例列表，通常由平台生成，**勿手改** |

---

## 6.4 常用命令

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

`--port` 支持：`27017`、`27017,27018`、`all`、`0`（`0` 通常与 `all` 等价，具体以当前版本帮助为准）。

### 告警 alarm

```bash
./bk-dbmon alarm shield  --port all
./bk-dbmon alarm unblock --port 27017,27018
./bk-dbmon alarm list    --port 27017,27018
```

平台在**版本升级**等维护场景中也会屏蔽或恢复告警，避免维护窗口误报。

### 动态配置 config

```bash
./bk-dbmon config get-all --port all
```

**parselog** 默认开启：tail 实例 `mongo.log`，将 **2.4 文本 / 3.0～4.2 文本 / 4.4+ JSON** 等形态统一写成 **`jsonlog/` 下 JSON 行**（不改动源日志）。解析器版本、输出路径与限流见 [第 9 章 · MongoDB 日志](09-mongodb-logs.md)。

常见操作示例：

```bash
# 关闭备份段：适用于临时止损、LogDB 等无需备份场景
./bk-dbmon config set --port all -s backup -k enable -V false

# 关闭 parselog：适用于日志量突增、解析任务消耗 CPU 时的临时止损
./bk-dbmon config set --port all -s parselog -k enable -V false

# 增加登录探测超时时间：适用于机器负载高、健康检查偶发 login timeout 的场景
./bk-dbmon config set --port all -s monitor -k loginTimeout -V 30
```

具体 segment / key 以 `bk-dbmon config` 在线帮助与版本为准。

### 连接 mongosh

```bash
sh conn.sh 27017
sh conn.sh 27017 "db.serverStatus().ok"
sh conn.sh all   "db.adminCommand({ ping: 1 })"
```

---

## 6.5 事件、指标与上报

### 自定义事件

| 事件名 | 级别 | 典型触发场景 |
|--------|------|--------------|
| `mongo_login` | `critical` | 实例认证失败、实例状态异常、端口有进程但登录超时 |
| `mongo_restart` | `warning` | 健康检查发现进程不存在，尝试自动拉起且成功 |
| `mongo_restart` | `critical` | 健康检查发现进程不存在，尝试自动拉起但失败 |

### 指标与备份上报

| 类型 | 说明 |
|------|------|
| `mongo_dbmon_heart_beat` | dbmon 心跳时序指标，用于确认 dbmon 自身存活 |
| 备份元数据 | 备份完成后写入本机 report 目录，由 bkmonitorbeat 上报；不等同于自定义事件 |

---

## 6.6 日常备份策略

bk-dbmon 内置 **backup** 段，是 MongoDB 集群**日常备份的执行者**。它以本地守护进程的方式在每台机器上独立调度，**只在 backup 节点（priority=0、hidden=true）上真正发起备份**，从而避免对线上读写造成 IO / CPU 抖动（详见 [§2.1 副本集拓扑](02-cluster-topology.md)）。

### 备份要点

| 维度 | 说明 |
|------|------|
| 谁来备份 | 副本集：**backup 节点** 独占执行<br/>分片集群：**每个 shard 的 backup 节点** + **configsvr 的 backup 节点** |
| 什么时候备 | 默认 **每小时一次增量备份**（`incrFreq=3600`），**每日一次全量备份**（`fullFreq=86400`）；`AUTO` 模式按两个参数自动选择本次该做 FULL 还是 INCR |
| 怎么备 | `AUTO` 模式：按间隔自动选择 **FULL 全量** 或 **INCR 增量 oplog**<br/>产物落盘 `/data/dbbak/mg/mongodump/`<br/>可选 gzip / zstd 压缩 |

### 备份执行流程

1. **巡检与角色判定**：dbmon 周期巡检本机所有实例，读取 `cluster-config.yaml` 中 `backup.enable`，并通过 `rs.isMaster()` / `rs.conf()` 判断当前节点是否为 **backup 节点**。**仅 backup 节点**触发后续步骤。
2. **执行 mongodump**：目标路径 `/data/dbbak/mg/mongodump/<cluster>/<ip>_<port>_<yyyymmdd_hhmmss>/`，连接串使用本地 `127.0.0.1:<port>`，readPreference 直连本节点，避免跨网络。
3. **打包 / 上报元数据**：备份完成后压缩成 `.tar` 或 `.tar.gz`，并把**备份元数据**（集群、实例、起止时间、文件大小、状态）写到本地 report 目录，由 **bkmonitorbeat** 上报蓝鲸监控。
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

```text
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

### 跳过备份

**A. 实例级关闭（dbmon CLI）**

```bash
./bk-dbmon config set --port all \
  -s backup -k enable -V false
```

适用：**临时关停**、紧急止损、**LogDB** 等无需备份的场景。

**B. 集群级标签（DBM 平台）**

在 DBM 集群属性 / Tag 中添加 `backup:no`，**巡检与备份检查会一并跳过**，适合长期不需备份的集群（数据可重建、纯日志库等）。

### 备份检查

> ✅ **查看备份是否成功**
>
> 1. 登录 backup 节点机器，`ls /data/dbbak/mg/` 查看当天产物与 `done.flag`。
> 2. 在 DBM 控制台 **集群详情 → 备份记录** 查看（数据来自 dbmon 上报）。
> 3. 实例机本地：`./bk-dbmon meta list --port all` 查看备份段最近一次执行状态。

> ⚠ **常见踩坑**
>
> - backup 节点磁盘空间不足 → mongodump 中途失败；建议 `/data/dbbak` 至少预留**数据量 × 1.5** 的空间。
> - 全备触发时间默认随机分布在 `backup.startTime ~ endTime` 窗口内（见上表"关键参数"行），便于错开同机房集中跑备份；若需要固定到具体小时点，需在 dbconfig 中显式收窄窗口。

---

## 6.7 排障速查

| 现象 | 排查路径 |
|------|---------|
| 监控无数据 | 检查本机 **bk-dbmon** 是否运行；`dbmon-config.yaml` 中 **bkmonitorbeat** 路径与 `data_id` / `token` 是否与当前环境一致；检查 GSE / bkmonitorbeat 插件是否正常 |
| 误报或维护窗口 | 使用 `alarm shield` 屏蔽，结束后再 `unblock` |
| 实例已下架仍报端口 | 尝试 `meta delete` 清理残留元数据 |
| 平台侧排障 | 结合 **工单详情** 与 Job 执行日志确认安装、启动和配置下发结果 |
| 备份长期缺失 | 先确认 backup 节点、`backup.enable`、备份窗口和 `/data/dbbak` 空间 |

---

[← 第 5 章 mongosh](05-mongosh.md) | [↑ 返回目录](README.md) | [第 7 章 版本与兼容性 →](07-versions.md) · [第 13 章 性能视图](13-performance-views.md)

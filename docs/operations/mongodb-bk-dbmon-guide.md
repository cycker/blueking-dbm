# MongoDB bk-dbmon 使用指引（蓝鲸 DBM）

**bk-dbmon** 是部署在 MongoDB 机器上的 **本地守护进程**，负责例行任务（如备份、心跳、健康检查等），并通过 **bkmonitorbeat** 与蓝鲸监控体系对接。本文说明在 **蓝鲸 DBM** 场景下的安装入口、目录约定与常用运维命令。

**相关文档**：[MongoDB 运维指南](./mongodb-ops-guide.md) · [Shell 入门](./mongodb-shell-primer.md)

**源码与脚本**：

- 进程与配置：`dbm-services/mongodb/db-tools/dbmon/`
- 安装编排：`dbm-ui/backend/flow/engine/bamboo/scene/mongodb/mongodb_install_dbmon.py`、`sub_task/install_dbmon_sub.py`
- 节点执行：`dbm-services/mongodb/db-tools/dbactuator/pkg/atomjobs/atommongodb/install_dbmon.go`
- 包内运维说明：`dbm-services/mongodb/db-tools/dbmon/package/readme.md`

---

## 1. 作用概述

根据仓库内 README 描述，bk-dbmon 提供 **本地例行任务** 能力，典型包括：

- **例行备份**、与备份/上报相关的本地任务；
- **心跳与健康检查**（如周期性探测 `mongod` / `mongos` 端口与认证）；
- 将结果写入本机目录后，由 **bkmonitorbeat** 上报至蓝鲸监控（`data_id` / `token` 等由平台生成并注入配置）。

事件类行为示例（如认证失败、实例状态异常、尝试拉起进程等）见 `dbm-services/mongodb/db-tools/dbmon/README.md` 中的说明。

---

## 2. 在 DBM 中如何安装 / 更新

### 2.1 工单类型与权限

- 单据类型：**MongoDB 安装DBMon** → 常量 `MONGODB_INSTALL_DBMON`（`dbm-ui/backend/ticket/constants.py`）。
- IAM 动作 ID 一般为 **`mongodb_install_dbmon`**（见 `dbm-ui/backend/iam_app/migration_json_files/initial.json`）；**菜单名称以你环境蓝鲸权限中心为准**。

> 说明：当前仓库前端 `TicketTypes` 枚举中可能未单独列出该类型，但 **后端工单与 IAM 已定义**。若控制台未展示入口，可通过 **工单 API / 运维二次开发菜单** 或联系平台管理员开启。

### 2.2 流程与入参（Flow）

编排类入口：`MongoDBController.install_dbmon` → `MongoInstallDBMonFlow`（`dbm-ui/backend/flow/engine/controller/mongodb.py`）。

HTTP 场景接口（与代码一致，前缀以网关为准）：

- **Path**：`/apis/v1/flow/scene/mongo_install_dbmon`
- **Method**：`POST`
- **Body 字段**（见 `MongoInstallDBMonFlow.Serializer`）：`uid`、`created_by`、`bk_biz_id`、`ticket_type`、`action`、`bk_cloud_id`、`infos`

其中 **`infos`** 为字符串列表，每一项可以是：

- **主机 IP**（直接在该机安装/更新 bk-dbmon）；
- **集群 ID**（纯数字，会展开为该集群下 IP 列表）；
- **集群域名**（以 `.db` 结尾的域名，会先解析为集群 ID 再展开 IP）。

`bk_cloud_id` 必须与集群所属云区域一致，否则流程会校验失败。

### 2.3 平台实际做了什么（摘要）

`add_install_dbmon`（`mongodb_install_dbmon.py`）会：

1. 从介质库拉取 **dbactuator、dbmon、dbtools、mongo-toolkit** 等包的最新或指定版本（`get_pkg_info()`）；
2. 下发到节点工作目录（`MongoUtil().get_mongodb_os_conf()["file_path"]`）；
3. 通过 dbactuator 执行 **`InstallDBMon`** 动作（`MongoDBActuatorActionEnum.InstallDBMon`），以 **root** 执行、`sudo_account` 为 **`mysql`**（见 `install_dbmon_sub.py`）；
4. 注入默认 **`http_address`: `127.0.0.1:6677`**、本机 **`report_save_dir`**（如 `/home/mysql/report`）及 **`bkmonitorbeat`** 配置（`ActKwargs.get_mongodb_monitor_conf()`）。

### 2.4 随其它工单自动安装

以下场景会在主流程中 **嵌入** `add_install_dbmon`（不必单独提「安装 DBMon」单），例如：MongoDB **集群部署**、**扩缩容**、**集群标准化**、**整机替换/迁移** 等子流程。具体以对应 `mongodb_*.py` 流程是否调用 `add_install_dbmon` 为准。

---

## 3. 安装路径与配置

### 3.1 目录约定（与 dbactuator 实现一致）

- 安装目录：**`/home/mysql/bk-dbmon/`**
- 主配置：**`dbmon-config.yaml`**（与可执行文件同目录，见 `dbm-services/mongodb/db-tools/dbmon/package/start.sh`）
- 启动脚本：**`start.sh`** / **`stop.sh`**
- 本地上报目录示例：`/home/mysql/report`（流程默认值；以实际 payload 为准）

### 3.2 进程与自检

- `start.sh` 会读取配置中的 **`http_address`**，并请求 **`http://<http_address>/health`** 判断 bk-dbmon 是否已存活；未启动则 `nohup ./bk-dbmon --config=dbmon-config.yaml` 拉起。
- 可为 `start.sh` 传入 **`debug`** 以开启调试日志（见 `start.sh`）。

### 3.3 配置示例（字段含义）

仓库内示例见 `dbm-services/mongodb/db-tools/dbmon/README.md`，一般包含：

- **`report_save_dir`** / **`report_left_day`**：本机结果保留目录与天数；
- **`http_address`**：HTTP 管理地址（默认 `127.0.0.1:6677`）；
- **`bkmonitorbeat`**：`agent_address`、`beat_path`、`event_config`、`metric_config`（蓝鲸监控采集）；
- **`servers`**：由流程中的 **PrepareInstanceInfo** 填充，描述每个 Mongo 实例的角色、端口、集群元数据等（平台写入，**勿手改** 除非你知道含义）。

---

## 4. 常用命令（在实例机上）

以下命令在 **`/home/mysql/bk-dbmon`** 目录下执行（与 `package/readme.md` 一致；若企业自定义安装路径，以实际为准）。

### 4.1 启停

```bash
cd /home/mysql/bk-dbmon
sh start.sh          # 启动（后台），并尝试加入 crontab 每 2 分钟自检拉起
sh stop.sh           # 停止
```

### 4.2 元数据（实例注册表）

```bash
./bk-dbmon meta list --port all
./bk-dbmon meta list --port 27017,27018
./bk-dbmon meta delete --port 27017,27018   # 清理无效或已下线实例
```

`--port` 支持：`27017`、`27017,27018`、`all`、`0`（`0` 与 `all` 语义见 `package/readme.md`）。

### 4.3 告警屏蔽 / 解除

```bash
./bk-dbmon alarm shield --port all
./bk-dbmon alarm unblock --port 27017,27018
./bk-dbmon alarm list --port 27017,27018
```

平台在 **版本升级** 等流程中也会通过脚本调用 **`bk-dbmon alarm shield` / `unblock` / `meta delete`**（见 `dbm-ui/backend/flow/utils/mongodb/mongodb_script_template.py`），避免维护窗口误报。

### 4.4 动态配置（部分项免重启）

```bash
./bk-dbmon config get-all --port all
./bk-dbmon config set --port all -s backup -k enable -V false   # 示例：关闭备份段
./bk-dbmon config set --port all -s parselog -k enable -V false
```

说明：具体 segment / key 以 `bk-dbmon config` 在线帮助与版本为准。

### 4.5 便捷连接 mongosh

```bash
sh conn.sh 27017
sh conn.sh 27017 "db.serverStatus().ok"
sh conn.sh all "db.adminCommand({ ping: 1 })"
```

---

## 5. 与监控、排障的关系

1. **监控无数据**：检查本机 **bk-dbmon** 是否运行、`dbmon-config.yaml` 中 **bkmonitorbeat** 路径与 **data_id/token** 是否与当前环境一致；检查 GSE / bkmonitorbeat 插件是否正常。  
2. **误报或维护窗口**：使用 **`alarm shield`**，结束后再 **`unblock`**（与平台升级脚本策略一致）。  
3. **实例已下架仍报端口**：尝试 **`meta delete`** 清理残留元数据。  
4. **平台侧排障**：结合 **工单详情** 与 Job 日志中的 dbactuator 输出（`install_dbmon` / `InstallDBMon` 相关步骤）。

---

## 6. 版本与介质

bk-dbmon 安装包在流程中通过 **`Package.get_latest_package(..., pkg_type="dbmon", db_type=MongoDB)`** 选取（见 `get_pkg_info()`）。若需固定版本，应在 **DBM 介质管理** 中维护可用包并与环境变更流程对齐。

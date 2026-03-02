文件：`views/query_metrics.py`

实现以下 MongoDB 指标查询工具：

- `get_mongodb_qps`：查询 MongoDB 集群 QPS（按 type/instance_role/instance 聚合）
- `get_mongodb_connections`：查询 MongoDB 集群连接数（current）
- `get_mongodb_locks`：查询 MongoDB 集群锁队列（global_lock current_queue）
- `get_mongodb_cpu_usage`：查询 MongoDB 主机 CPU 使用率

## 入参（通用）

- `start_time`：开始时间（datetime）
- `end_time`：结束时间（datetime，必须大于 `start_time`）
- `cluster_domain`：集群域名（注意：与 Meta 接口入参 `immute_domain` 同值，仅字段名不同）
- `instance_host`：可选。实例主机 IP，用于按主机过滤指标（为空表示不过滤）
- `instance`: 可选。 实例 addr，用于按实例过滤指标（为空表示不过滤）

## 出参（通用）

返回 `MongoMetricsOutputSerializer` 结构：

- `cluster_domain`：集群域名
- `metric_type`：指标类型（`qps` / `connections` / `locks` / `cpu_usage`）
- `series`：时序列表
  - `dimensions`：维度字典（如 `instance`、`instance_role`、`bk_target_ip` 等）
  - `datapoints`：数据点列表，格式 `[[value, timestamp], ...]`
- `error`：可选。失败时返回的错误信息

## 典型用法建议

若用户仅提供 IP（没有集群域名），建议先用 Meta 工具（如 `list_clusters_by_hosts`）定位集群域名（`immute_domain`），再将其作为这里的 `cluster_domain` 传入指标查询接口。
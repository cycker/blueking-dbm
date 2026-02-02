"""
TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
Copyright (C) 2017-2023 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import statistics
from collections import defaultdict
from typing import Any, Dict, List

from django.utils import timezone

from backend import env
from backend.components import BKLogApi
from backend.db_meta.models import Cluster
from backend.dbm_aiagent.mcp_tools.exceptions import DBMMcpBaseException
from backend.utils.time import datetime2str


def _calc_duration_stats(durations: List[int]) -> Dict[str, Any]:
    if not durations:
        return {"max_ms": 0, "min_ms": 0, "avg_ms": 0, "median_ms": 0}
    return {
        "max_ms": round(max(durations) / 1000, 2),
        "min_ms": round(min(durations) / 1000, 2),
        "avg_ms": round(statistics.mean(durations) / 1000, 2),
        "median_ms": round(statistics.median(durations) / 1000, 2),
    }


def get_cluster_slowlog_static(
    immute_domain: str,
    start_time: timezone.datetime,
    end_time: timezone.datetime,
) -> Dict:
    """获取集群时间范围内慢查询日志统计数据。当前返回空结构，需对接 MongoDB 慢日志检索（如 BKLog index）。"""
    cluster_slows = _get_mongo_slowlog(
        get_query_params(immute_domain=immute_domain, start_time=start_time, end_time=end_time)
    )
    instance_data = defaultdict(lambda: {"durations": [], "ops": defaultdict(int), "records": []})
    all_durations = []
    all_ops = defaultdict(int)
    for record in cluster_slows:
        instance = record.get("instance_addr", "unknown")
        duration = record.get("duration_ms", 0) * 1000
        op = record.get("op", "unknown")
        instance_data[instance]["durations"].append(duration)
        instance_data[instance]["ops"][op] += 1
        instance_data[instance]["records"].append(record)
        all_durations.append(duration)
        all_ops[op] += 1
    result = {
        "summary": {
            "total_count": len(cluster_slows),
            "instance_count": len(instance_data),
            "duration_stats": _calc_duration_stats(all_durations),
            "top_ops": dict(sorted(all_ops.items(), key=lambda x: x[1], reverse=True)[:10]),
        },
        "by_instance": {},
    }
    for instance, data in instance_data.items():
        durations = data["durations"]
        records = data["records"]
        slowest = max(records, key=lambda x: x.get("duration_ms", 0)) if records else {}
        slowest_info = (
            {
                "op": slowest.get("op", "unknown"),
                "ns": slowest.get("ns", ""),
                "duration_ms": slowest.get("duration_ms", 0),
                "create_time": slowest.get("create_time", ""),
            }
            if slowest
            else {}
        )
        result["by_instance"][instance] = {
            "total_count": len(durations),
            "duration_stats": _calc_duration_stats(durations),
            "top_ops": dict(sorted(data["ops"].items(), key=lambda x: x[1], reverse=True)[:5]),
            "slowest_query": slowest_info,
        }
    return result


def get_host_slowlog(
    immute_domain: str,
    start_time: timezone.datetime,
    end_time: timezone.datetime,
    host: str,
) -> Dict:
    """获取某台主机上时间范围内慢查询日志。当前返回空列表，需对接 MongoDB 慢日志检索。"""
    host_slows = _get_mongo_slowlog(
        get_query_params(
            immute_domain=immute_domain, start_time=start_time, end_time=end_time, host=host
        )
    )
    return {"slowlog_entries": host_slows, "total_count": len(host_slows)}


def _get_mongo_slowlog(query_params: Dict) -> List[Dict]:
    """从日志平台查询 MongoDB 慢日志。需配置 DBM_MONGODB 相关 index。"""
    try:
        resp = BKLogApi.esquery_search(query_params, use_admin=True)
        slog_logs = []
        for hit in resp.get("hits", {}).get("hits", []):
            log_src = hit.get("_source") or {}
            mongo_slow = log_src.get("mongodb") or log_src.get("mongo") or {}
            slow_d = mongo_slow.get("slowlog") or mongo_slow
            ext = log_src.get("__ext") or {}
            slog_logs.append({
                "instance_addr": "{}:{}".format(ext.get("instance_host", ""), ext.get("instance_port", "")),
                "instance_role": ext.get("instance_role", ""),
                "create_time": (log_src.get("event") or {}).get("created", ""),
                "duration_ms": slow_d.get("duration", {}).get("ms", 0) or slow_d.get("duration_ms", 0),
                "op": slow_d.get("op", ""),
                "ns": slow_d.get("ns", ""),
            })
        return slog_logs
    except Exception as e:
        raise DBMMcpBaseException(msg=f"query mongodb slow logs failed: {e}")


def get_query_params(
    immute_domain: str,
    start_time: timezone.datetime,
    end_time: timezone.datetime,
    host: str = None,
) -> Dict:
    """MongoDB 慢日志查询参数。indices 需按实际 MongoDB 慢日志 index 配置。"""
    query_parts = [f'__ext.cluster_domain:"{immute_domain}"']
    if host:
        query_parts.append(f'__ext.instance_host:"{host}"')
    return {
        "indices": f"{env.DBA_APP_BK_BIZ_ID}_bklog.mongodb_slowlog",
        "start_time": datetime2str(start_time),
        "end_time": datetime2str(end_time),
        "query_string": " AND ".join(query_parts),
        "start": 0,
        "size": 1000,
        "sort_list": [["dtEventTimeStamp", "asc"], ["gseIndex", "asc"], ["iterationIndex", "asc"]],
    }

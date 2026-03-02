"""
TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
Copyright (C) 2017-2023 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.utils.translation import gettext_lazy as _
from rest_framework.response import Response

from backend.dbm_aiagent.mcp_tools.constants import DBMMCPTags, DBMMcpTools
from backend.dbm_aiagent.mcp_tools.decorators import mcp_tools_api_decorator
from backend.dbm_aiagent.mcp_tools.mongodb.impl.mongodb_metrics import (
    get_mongodb_connections,
    get_mongodb_cpu_usage,
    get_mongodb_locks,
    get_mongodb_qps,
)
from backend.dbm_aiagent.mcp_tools.mongodb.serializers.query_metrics import (
    MongoMetricsInputSerializer,
    MongoMetricsOutputSerializer,
)
from backend.dbm_aiagent.mcp_tools.mongodb.tools.comm_tools import estimate_token_count
from backend.dbm_aiagent.mcp_tools.views import McpToolsViewSet
from backend.iam_app.handlers.drf_perm.base import RejectPermission


class MongoMetricsMcpToolsViewSet(McpToolsViewSet):
    default_permission_class = [RejectPermission()]

    @mcp_tools_api_decorator(
        description=str(_("查询 MongoDB 集群 QPS（按 type/instance_role/instance）")),
        request_slz=MongoMetricsInputSerializer,
        response_slz=MongoMetricsOutputSerializer,
        tags=[DBMMCPTags.READ],
        mcp=[DBMMcpTools.MONGODB_METRICS],
        name_prefix=DBMMcpTools.MONGODB_METRICS,
    )
    def get_mongodb_qps(self, request, *args, **kwargs):
        start_time = self.get_param("start_time")
        end_time = self.get_param("end_time")
        cluster_domain = self.get_param("cluster_domain")
        instance_host = self.get_param("instance_host") or None
        out = get_mongodb_qps(
            cluster_domain=cluster_domain,
            start_time=start_time,
            end_time=end_time,
            instance_host=instance_host,
        )
        if isinstance(out, dict):
            out["token_count"] = estimate_token_count(out)
        return Response(out)

    @mcp_tools_api_decorator(
        description=str(_("查询 MongoDB 集群连接数（current）")),
        request_slz=MongoMetricsInputSerializer,
        response_slz=MongoMetricsOutputSerializer,
        tags=[DBMMCPTags.READ],
        mcp=[DBMMcpTools.MONGODB_METRICS],
        name_prefix=DBMMcpTools.MONGODB_METRICS,
    )
    def get_mongodb_connections(self, request, *args, **kwargs):
        start_time = self.get_param("start_time")
        end_time = self.get_param("end_time")
        cluster_domain = self.get_param("cluster_domain")
        instance_host = self.get_param("instance_host") or None
        out = get_mongodb_connections(
            cluster_domain=cluster_domain,
            start_time=start_time,
            end_time=end_time,
            instance_host=instance_host,
        )
        if isinstance(out, dict):
            out["token_count"] = estimate_token_count(out)
        return Response(out)

    @mcp_tools_api_decorator(
        description=str(_("查询 MongoDB 集群锁队列（global_lock current_queue）")),
        request_slz=MongoMetricsInputSerializer,
        response_slz=MongoMetricsOutputSerializer,
        tags=[DBMMCPTags.READ],
        mcp=[DBMMcpTools.MONGODB_METRICS],
        name_prefix=DBMMcpTools.MONGODB_METRICS,
    )
    def get_mongodb_locks(self, request, *args, **kwargs):
        start_time = self.get_param("start_time")
        end_time = self.get_param("end_time")
        cluster_domain = self.get_param("cluster_domain")
        instance_host = self.get_param("instance_host") or None
        out = get_mongodb_locks(
            cluster_domain=cluster_domain,
            start_time=start_time,
            end_time=end_time,
            instance_host=instance_host,
        )
        if isinstance(out, dict):
            out["token_count"] = estimate_token_count(out)
        return Response(out)

    @mcp_tools_api_decorator(
        description=str(_("查询 MongoDB 主机 CPU 使用率")),
        request_slz=MongoMetricsInputSerializer,
        response_slz=MongoMetricsOutputSerializer,
        tags=[DBMMCPTags.READ],
        mcp=[DBMMcpTools.MONGODB_METRICS],
        name_prefix=DBMMcpTools.MONGODB_METRICS,
    )
    def get_mongodb_cpu_usage(self, request, *args, **kwargs):
        start_time = self.get_param("start_time")
        end_time = self.get_param("end_time")
        cluster_domain = self.get_param("cluster_domain")
        instance_host = self.get_param("instance_host") or None
        out = get_mongodb_cpu_usage(
            cluster_domain=cluster_domain,
            start_time=start_time,
            end_time=end_time,
            instance_host=instance_host,
        )
        if isinstance(out, dict):
            out["token_count"] = estimate_token_count(out)
        return Response(out)

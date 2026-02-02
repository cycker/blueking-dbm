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
from backend.dbm_aiagent.mcp_tools.mongodb.impl.mongodb_slowlog import (
    get_cluster_slowlog_static,
    get_host_slowlog,
)
from backend.dbm_aiagent.mcp_tools.mongodb.serializers.mongodb_log import (
    MongoSlowClusterStaticSerializer,
    MongoSlowlog4HostInputSerializer,
    MongoSlowlogInputSerializer,
    MongoSlowlogResponseSerializer,
)
from backend.dbm_aiagent.mcp_tools.views import McpToolsViewSet
from backend.iam_app.handlers.drf_perm.base import RejectPermission


class MongoQueryLogMcpToolsViewSet(McpToolsViewSet):
    default_permission_class = [RejectPermission()]

    @mcp_tools_api_decorator(
        description=str(
            _(
                "功能: 获取MongoDB集群时间范围内慢查询日志统计数据；"
                "展示方式: 分多维表格展示，按实例维度统计并按最大耗时、慢日志条数排序"
            )
        ),
        request_slz=MongoSlowlogInputSerializer,
        response_slz=MongoSlowClusterStaticSerializer,
        tags=[DBMMCPTags.READ],
        mcp=[DBMMcpTools.MONGODB_QUERY_LOG],
        name_prefix="mongodb_query_log",
    )
    def get_cluster_slowlog_statics(self, request, *args, **kwargs):
        start_time = self.get_param("start_time")
        end_time = self.get_param("end_time")
        immute_domain = self.get_param("immute_domain")
        return Response(
            get_cluster_slowlog_static(
                immute_domain=immute_domain, start_time=start_time, end_time=end_time
            )
        )

    @mcp_tools_api_decorator(
        description=str(_("查询某台机器上的MongoDB慢查询日志，包括执行时间、操作类型、命名空间等")),
        request_slz=MongoSlowlog4HostInputSerializer,
        response_slz=MongoSlowlogResponseSerializer,
        tags=[DBMMCPTags.READ],
        mcp=[DBMMcpTools.MONGODB_QUERY_LOG],
        name_prefix="mongodb_query_log",
    )
    def fetch_host_slowlog(self, request, *args, **kwargs):
        start_time = self.get_param("start_time")
        end_time = self.get_param("end_time")
        ip = self.get_param("ip")
        immute_domain = self.get_param("immute_domain")
        return Response(
            get_host_slowlog(
                immute_domain=immute_domain, start_time=start_time, end_time=end_time, host=ip
            )
        )

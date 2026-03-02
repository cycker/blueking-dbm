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
from backend.dbm_aiagent.mcp_tools.mongodb.impl.mongodb_status import (
    get_mongodb_cluster_topology_text,
    get_mongodb_server_status,
)
from backend.dbm_aiagent.mcp_tools.mongodb.serializers.cluster_status import (
    MongoClusterInputSerializer,
    MongoClusterTopologyTextSerializer,
)
from backend.dbm_aiagent.mcp_tools.mongodb.serializers.instance_status import (
    MongoInstanceInputSerializer,
    MongoServerStatusSerializer,
)
from backend.dbm_aiagent.mcp_tools.views import McpToolsViewSet
from backend.iam_app.handlers.drf_perm.base import RejectPermission


class MongoStatusMcpToolsViewSet(McpToolsViewSet):
    default_permission_class = [RejectPermission()]

    @mcp_tools_api_decorator(
        description=str(_("查询MongoDB实例 serverStatus 信息，包括版本、运行时长、连接数、操作计数、内存等")),
        request_slz=MongoInstanceInputSerializer,
        response_slz=MongoServerStatusSerializer,
        tags=[DBMMCPTags.READ],
        mcp=[DBMMcpTools.MONGODB_STATUS],
        name_prefix=DBMMcpTools.MONGODB_STATUS,
    )
    def get_server_status(self, request, *args, **kwargs):
        mongo_addr = self.get_param("mongo_addr")
        immute_domain = self.get_param("immute_domain")
        return Response(get_mongodb_server_status(mongo_addr=mongo_addr, immute_domain=immute_domain))

    @mcp_tools_api_decorator(
        description=str(_("查询MongoDB集群拓扑信息并以文本格式返回")),
        request_slz=MongoClusterInputSerializer,
        response_slz=MongoClusterTopologyTextSerializer,
        tags=[DBMMCPTags.READ],
        mcp=[DBMMcpTools.MONGODB_STATUS],
        name_prefix=DBMMcpTools.MONGODB_STATUS,
    )
    def get_cluster_topology(self, request, *args, **kwargs):
        immute_domain = self.get_param("immute_domain")
        return Response(get_mongodb_cluster_topology_text(immute_domain=immute_domain))

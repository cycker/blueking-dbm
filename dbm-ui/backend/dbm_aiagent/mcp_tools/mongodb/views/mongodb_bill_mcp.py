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

from backend.db_meta.models import Cluster
from backend.dbm_aiagent.mcp_tools.constants import DBMMCPTags, DBMMcpTools
from backend.dbm_aiagent.mcp_tools.decorators import mcp_tools_api_decorator
from backend.dbm_aiagent.mcp_tools.mongodb.serializers.mongodb_bill import (
    SubmitBillMongoBackupInputSerializer,
    SubmitBillOutputSerializer,
)
from backend.dbm_aiagent.mcp_tools.views import McpToolsViewSet
from backend.iam_app.handlers.drf_perm.base import RejectPermission
from backend.ticket.constants import TicketType
from backend.ticket.models import Ticket


class MongoBillMcpToolsViewSet(McpToolsViewSet):
    default_permission_class = [RejectPermission()]

    @mcp_tools_api_decorator(
        description=str(_("MongoDB集群备份单据（库表备份）")),
        request_slz=SubmitBillMongoBackupInputSerializer,
        response_slz=SubmitBillOutputSerializer,
        tags=[DBMMCPTags.READ, DBMMCPTags.WRITE],
        mcp=[DBMMcpTools.MONGODB_BILL],
        name_prefix="mongodb_bill",
    )
    def submit_bill_mongodb_backup(self, request, *args, **kwargs):
        bk_biz_id = self.get_param("bk_biz_id")
        cluster_domain = self.get_param("cluster_domain")
        backup_type = self.get_param("backup_type")
        cluster_obj = Cluster.objects.get(bk_biz_id=bk_biz_id, immute_domain=cluster_domain)
        cluster_id = cluster_obj.id
        ns_filter = {
            "db_patterns": None,
            "table_patterns": None,
            "ignore_dbs": None,
            "ignore_tables": None,
        }
        ticket_param = {
            "bk_biz_id": bk_biz_id,
            "ticket_type": TicketType.MONGODB_BACKUP,
            "creator": request.user.username,
            "helpers": [],
            "remark": "mcp mongodb backup ticket",
            "details": {
                "file_tag": backup_type,
                "infos": [
                    {
                        "cluster_ids": [cluster_id],
                        "cluster_type": cluster_obj.cluster_type,
                        "ns_filter": ns_filter,
                    }
                ],
            },
        }
        tk = Ticket.create_ticket(**ticket_param)
        return Response({"bill_id": tk.pk, "bill_url": tk.url})

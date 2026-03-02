# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
Copyright (C) 2017-2023 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import time
from itertools import chain

from django.utils.translation import gettext_lazy as _
from rest_framework.response import Response

from backend.db_meta.enums import ClusterType
from backend.db_meta.models import Cluster
from backend.dbm_aiagent.mcp_tools.common.impl.job import exec_cluster_query_net_tcp_cmd, get_job_exec_status
from backend.dbm_aiagent.mcp_tools.constants import DBMMCPTags, DBMMcpTools
from backend.dbm_aiagent.mcp_tools.decorators import mcp_tools_api_decorator
from backend.dbm_aiagent.mcp_tools.mongodb.impl.get_source_access_impl import (
    generate_mongodb_cluster_query_report,
)
from backend.dbm_aiagent.mcp_tools.mongodb.serializers.get_source_access import (
    GetMongoSourceAccessInputSerializer,
    GetMongoSourceAccessOutputSerializer,
)
from backend.dbm_aiagent.mcp_tools.views import McpToolsViewSet
from backend.iam_app.handlers.drf_perm.base import DBManagePermission


class MongoJobMcpToolsViewSet(McpToolsViewSet):
    default_permission_class = [DBManagePermission()]

    @mcp_tools_api_decorator(
        description=str(_("查询MongoDB集群访问来源，返回来源列表")),
        request_slz=GetMongoSourceAccessInputSerializer,
        response_slz=GetMongoSourceAccessOutputSerializer,
        tags=[DBMMCPTags.READ],
        mcp=[DBMMcpTools.MONGODB_JOB],
        name_prefix="mongodb_job",
    )
    def get_mongodb_source_access(self, request, *args, **kwargs):
        cluster_domain = self.get_param("cluster_domain")
        cluster_obj = Cluster.objects.get(immute_domain=cluster_domain)  # pyright: ignore[reportAttributeAccessIssue]
        cluster_all_ips = [
            e.machine.ip
            for e in chain(
                cluster_obj.storageinstance_set.all(), cluster_obj.proxyinstance_set.all()
            )
        ]
        if cluster_obj.cluster_type == ClusterType.MongoReplicaSet:
            target_ips = [
                {"ip": e.machine.ip, "bk_cloud_id": cluster_obj.bk_cloud_id}
                for e in cluster_obj.storageinstance_set.all()
            ]
        elif cluster_obj.cluster_type == ClusterType.MongoShardedCluster:
            target_ips = [
                {"ip": e.machine.ip, "bk_cloud_id": cluster_obj.bk_cloud_id}
                for e in chain(
                    cluster_obj.storageinstance_set.all(), cluster_obj.proxyinstance_set.all()
                )
            ]
        else:
            target_ips = [
                {"ip": e.machine.ip, "bk_cloud_id": cluster_obj.bk_cloud_id}
                for e in cluster_obj.proxyinstance_set.all()
            ]
        job_task = exec_cluster_query_net_tcp_cmd(target_ips)
        job_instance_id = job_task["job_instance_id"]
        tcp_report = []
        for i in range(10):
            time.sleep(30)
            job_resp = get_job_exec_status(job_instance_id)
            if job_resp["finished"]:
                tcp_report = generate_mongodb_cluster_query_report(
                    job_resp["job_log_resp"], cluster_domain, cluster_all_ips
                )
                break
        if not tcp_report:
            return Response({"report": [], "failed_hosts": []})
        first = tcp_report[0] if isinstance(tcp_report, list) else tcp_report
        report = first.get("report", [])
        failed = first.get("error", [])
        return Response({"report": report, "failed_hosts": failed})

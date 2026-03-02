"""
TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
Copyright (C) 2017-2023 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from rest_framework.routers import DefaultRouter

# from backend.dbm_aiagent.mcp_tools.mongodb.views.job import MongoJobMcpToolsViewSet
# from backend.dbm_aiagent.mcp_tools.mongodb.views.mongodb_bill_mcp import MongoBillMcpToolsViewSet
from backend.dbm_aiagent.mcp_tools.mongodb.views.query_alarm import MongoAlarmMcpToolsViewSet
from backend.dbm_aiagent.mcp_tools.mongodb.views.query_log import MongoLogMcpToolsViewSet
from backend.dbm_aiagent.mcp_tools.mongodb.views.query_meta import MongoMetaMcpToolsViewSet
# from backend.dbm_aiagent.mcp_tools.mongodb.views.query_status import MongoQueryStatusMcpToolsViewSet
from backend.dbm_aiagent.mcp_tools.mongodb.views.query_metrics import MongoMetricsMcpToolsViewSet
from backend.dbm_aiagent.mcp_tools.mongodb.views.query_time import MongoSystemMcpToolsViewSet

routers = DefaultRouter(trailing_slash=True)

# routers.register(r"", MongoQueryStatusMcpToolsViewSet, basename="mcp-mongodb-query-status")
# routers.register(r"", MongoBillMcpToolsViewSet, basename="mcp-mongodb-bill")
# routers.register(r"", MongoJobMcpToolsViewSet, basename="mcp-mongodb-job")
routers.register(r"", MongoMetaMcpToolsViewSet, basename="mcp-mongodb-meta")
routers.register(r"", MongoLogMcpToolsViewSet, basename="mcp-mongodb-log")
routers.register(r"", MongoAlarmMcpToolsViewSet, basename="mcp-mongodb-alarm")
routers.register(r"", MongoSystemMcpToolsViewSet, basename="mcp-mongodb-system")
routers.register(r"", MongoMetricsMcpToolsViewSet, basename="mcp-mongodb-metrics")

# Meta, Log, Alarm, Metric 相关接口
# Job, Bill, Query, Status 相关接口暂不支持
# Time 相关接口支持

urlpatterns = routers.urls

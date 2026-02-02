"""
TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
Copyright (C) 2017-2023 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import Dict

from backend.dbm_aiagent.mcp_tools.mongodb.tools.mongodb_info_srv import MongoDBInfoService


def get_mongodb_server_status(mongo_addr: str, immute_domain: str) -> Dict:
    """获取MongoDB服务器状态（serverStatus）"""
    service = MongoDBInfoService(addr=mongo_addr, immute_domain=immute_domain)
    return service.get_server_status()


def get_mongodb_cluster_topology_text(immute_domain: str) -> Dict:
    """获取MongoDB集群拓扑信息(文本格式)"""
    service = MongoDBInfoService(addr="", immute_domain=immute_domain)
    return service.get_cluster_topology_text()

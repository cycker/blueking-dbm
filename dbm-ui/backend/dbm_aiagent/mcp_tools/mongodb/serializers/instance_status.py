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
from rest_framework import serializers


class MongoInstanceInputSerializer(serializers.Serializer):
    """MongoDB实例输入序列化器"""

    mongo_addr = serializers.CharField(help_text=_("实例地址 ip:port"))
    immute_domain = serializers.CharField(help_text=_("集群域名"))


class MongoServerStatusSerializer(serializers.Serializer):
    """MongoDB服务器状态信息"""

    host = serializers.CharField(help_text=_("主机"))
    version = serializers.CharField(help_text=_("MongoDB版本"))
    uptime = serializers.FloatField(help_text=_("运行时长（秒）"))
    connections = serializers.DictField(help_text=_("连接信息"))
    opcounters = serializers.DictField(help_text=_("操作计数"))
    mem = serializers.DictField(help_text=_("内存信息"))
    extra_info = serializers.DictField(help_text=_("额外信息"), required=False)

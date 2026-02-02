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


class SubmitBillOutputSerializer(serializers.Serializer):
    bill_id = serializers.IntegerField(
        help_text=_("单据id, 理论上都会返回，如果没有返回说明有错误，需要把错误暴露出来")
    )
    bill_url = serializers.CharField(help_text=_("单据地址"))


class SubmitBillMongoBaseInputSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(help_text=_("业务 id, bk_biz_id"))
    cluster_domain = serializers.CharField(help_text=_("集群域名，格式为xx.xx.xx.db"))


class SubmitBillMongoBackupInputSerializer(SubmitBillMongoBaseInputSerializer):
    backup_type = serializers.CharField(help_text=_("备份类型"), default="logic")
    target = serializers.CharField(help_text=_("备份目标"), default="all", allow_blank=True)

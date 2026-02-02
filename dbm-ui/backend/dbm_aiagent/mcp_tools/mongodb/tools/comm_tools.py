"""
TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
Copyright (C) 2017-2023 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import ipaddress
from datetime import datetime
from typing import Union


def sort_by_ip_port(data_list):
    """按照IP地址和端口号对列表进行排序"""
    def sort_key(item):
        ip_int = int(ipaddress.IPv4Address(item["ip"]))
        port = item["port"]
        return (ip_int, port)
    return sorted(data_list, key=sort_key)


def parse_time2_long(dt: Union[int, str, datetime]) -> int:
    """将时间转换为 Unix 时间戳（秒）"""
    if isinstance(dt, int):
        return dt
    if isinstance(dt, str):
        from dateutil import parser
        return int(parser.parse(dt).timestamp())
    if isinstance(dt, datetime):
        return int(dt.timestamp())
    raise ValueError("unsupported time type")

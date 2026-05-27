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

from types import SimpleNamespace

import pytest

from backend.flow.plugins.components.collections.mongodb import mongodb_capcity_chgs_meta
from backend.flow.plugins.components.collections.mongodb.mongodb_capcity_chgs_meta import MongoDBCapcityMetaService
from backend.ticket.builders.mongodb import mongo_scale_updown


def test_get_cluster_exclusive_hosts_deduplicates_machine():
    machine_1 = SimpleNamespace(bk_host_id=1001)
    machine_2 = SimpleNamespace(bk_host_id=1002)
    fake_instances = [
        SimpleNamespace(machine=machine_1),
        SimpleNamespace(machine=machine_1),
        SimpleNamespace(machine=machine_2),
    ]

    class FakeStorageManager:
        def select_related(self, *_args, **_kwargs):
            return self

        def filter(self, **_kwargs):
            return fake_instances

    original_objects = mongo_scale_updown.StorageInstance.objects
    mongo_scale_updown.StorageInstance.objects = FakeStorageManager()
    try:
        hosts = mongo_scale_updown.MongoDBScaleUpDownResourceParamBuilder.get_cluster_exclusive_hosts(
            cluster=SimpleNamespace(id=1)
        )
    finally:
        mongo_scale_updown.StorageInstance.objects = original_objects

    assert [host.bk_host_id for host in hosts] == [1001, 1002]


def test_build_host_lock_keys_are_sorted_and_unique():
    kwargs = {
        "bk_biz_id": 2,
        "cluster_id": 3,
        "mongodb": [
            {"ip": "1.1.1.2", "target": {"ip": "1.1.1.3"}},
            {"ip": "1.1.1.1", "target": {"ip": "1.1.1.3"}},
        ],
    }
    keys = MongoDBCapcityMetaService._build_host_lock_keys(kwargs)
    assert keys == [
        "dbm:mongodb:capacity_meta:host:2:3:1.1.1.1",
        "dbm:mongodb:capacity_meta:host:2:3:1.1.1.2",
        "dbm:mongodb:capacity_meta:host:2:3:1.1.1.3",
    ]


def test_acquire_lock_rolls_back_when_key_is_busy(monkeypatch):
    set_calls = []
    release_calls = []

    class FakeRedis:
        @staticmethod
        def set(lock_key, lock_value, nx=True, ex=0):
            set_calls.append((lock_key, lock_value, nx, ex))
            return lock_key.endswith("1.1.1.1")

        @staticmethod
        def register_script(_lua):
            def _release(keys, args):
                release_calls.append((keys[0], args[0]))
                return 1

            return _release

    monkeypatch.setattr(mongodb_capcity_chgs_meta, "RedisConn", FakeRedis())
    kwargs = {
        "bk_biz_id": 2,
        "cluster_id": 3,
        "mongodb": [{"ip": "1.1.1.1", "target": {"ip": "1.1.1.2"}}],
    }

    with pytest.raises(Exception, match="host lock busy"):
        MongoDBCapcityMetaService._acquire_host_locks(kwargs)

    assert len(set_calls) == 2
    assert len(release_calls) == 1
    assert release_calls[0][0] == "dbm:mongodb:capacity_meta:host:2:3:1.1.1.1"

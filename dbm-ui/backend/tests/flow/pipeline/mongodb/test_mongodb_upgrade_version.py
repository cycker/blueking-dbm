# -*- coding: utf-8 -*-
import json
from unittest.mock import MagicMock, patch

import pytest

from backend.flow.engine.bamboo.scene.mongodb.mongodb_upgrade_version import MongoUpgradeVersionFlow
from backend.db_meta.enums.cluster_type import ClusterType


def _build_payload(*, cluster_ids, target_db_version, created_by="u", bk_biz_id=1, strategy=None):
    payload = {
        "cluster_ids": cluster_ids,
        "target_db_version": target_db_version,
        "created_by": created_by,
        "bk_biz_id": bk_biz_id,
    }
    if strategy:
        payload["strategy"] = strategy
    return payload


def test_serializer_rejects_missing_required_fields():
    # 缺少 created_by / bk_biz_id
    with pytest.raises(Exception):
        MongoUpgradeVersionFlow(root_id="r", data={"cluster_ids": [1], "target_db_version": "x-1.0.0"}).start()


def test_parse_main_version_works():
    assert MongoUpgradeVersionFlow._parse_main_version("rel-6.0.1") == "6"


def test_build_target_from_machine_storage_device_and_mem():
    flow = MongoUpgradeVersionFlow(
        root_id="r",
        data=_build_payload(
            cluster_ids=[1], target_db_version="rel-6.0.1", created_by="u", bk_biz_id=1, strategy="rolling"
        ),
    )

    machine = MagicMock()
    machine.ip = "1.1.1.1"
    machine.bk_cloud_id = 0
    machine.spec_id = 10
    machine.spec_config = {
        "id": 10,
        "mem": {"min": 1, "max": 2},
        "cpu": {"min": 1, "max": 2},
        "storage_spec": [{"mount_point": "/data1", "min": 10, "max": 20, "type": "ALL"}],
    }
    target = flow._build_target_from_machine(machine)
    assert target["ip"] == "1.1.1.1"
    assert target["bk_mem"] == 1024  # 1GB -> MB
    assert "/data1" in target["storage_device"]
    assert target["storage_device"]["/data1"]["min"] == 10
    assert target["storage_device"]["/data1"]["size"] == 20


@pytest.mark.django_db
def test_start_pipeline_calls_by_strategy_and_cluster_type():
    # Dummy builder: 仅记录 add_sub_pipeline / add_parallel_sub_pipeline 的调用顺序
    class DummyBuilder:
        def __init__(self, root_id, data):
            self.root_id = root_id
            self.data = data
            self.calls = []

        def add_sub_pipeline(self, sub_flow):
            self.calls.append(("add_sub_pipeline", sub_flow))
            return self

        def add_parallel_sub_pipeline(self, sub_flow_list):
            self.calls.append(("add_parallel_sub_pipeline", sub_flow_list))
            return self

        def run_pipeline(self):
            # no-op
            return True

    # 3 个 cluster：RS rolling、Sharded rolling、RS full_stop
    cluster_rs_rolling = MagicMock(
        id=1, cluster_type=ClusterType.MongoReplicaSet.value, major_version="rel-6.0.1", bk_biz_id=1
    )
    cluster_sharded_rolling = MagicMock(
        id=2, cluster_type=ClusterType.MongoShardedCluster.value, major_version="rel-6.0.2", bk_biz_id=1
    )
    cluster_rs_full_stop = MagicMock(
        id=3, cluster_type=ClusterType.MongoReplicaSet.value, major_version="rel-7.0.0", bk_biz_id=1
    )

    # patch Cluster.objects.filter(...).select_related(...).all() => list above
    class DummyQuerySet(list):
        def select_related(self, *args, **kwargs):
            return self

        def all(self):
            return self

    dummy_qs = DummyQuerySet([cluster_rs_rolling, cluster_sharded_rolling, cluster_rs_full_stop])

    def dummy_filter(*args, **kwargs):
        return dummy_qs

    payload = _build_payload(cluster_ids=[1, 2, 3], target_db_version="rel-6.0.9", created_by="u", bk_biz_id=1)

    # 让 flow 的 _parse_main_version 的 major 对比：target_main=6 -> 1,2 rolling；3 full_stop
    # mock build infos + replace functions
    with patch("backend.flow.engine.bamboo.scene.mongodb.mongodb_upgrade_version.Builder", new=DummyBuilder,), patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_upgrade_version.AppCache.get_app_attr",
        return_value="app",
    ), patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_upgrade_version.ActKwargs",
        autospec=True,
    ) as act_kwargs_cls, patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_upgrade_version.Cluster"
    ) as cluster_model, patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_upgrade_version.replicaset_replace"
    ) as mock_replicaset_replace, patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_upgrade_version.cluster_replace_rolling"
    ) as mock_cluster_replace_rolling, patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_upgrade_version.cluster_replace"
    ) as mock_cluster_replace:

        cluster_model.objects.filter.side_effect = dummy_filter
        # select_related 返回自身由 DummyQuerySet 实现

        # dummy ActKwargs
        act_kwargs_inst = MagicMock()
        act_kwargs_cls.return_value = act_kwargs_inst
        act_kwargs_inst.payload = {}
        act_kwargs_inst.get_file_path.return_value = None

        mock_replicaset_replace.side_effect = (
            lambda *args, **kwargs: f"rs_replace_{kwargs.get('info', {}).get('mongodb', ['?'])}"
        )
        mock_cluster_replace_rolling.side_effect = lambda *args, **kwargs: "sharded_rolling_replace"
        mock_cluster_replace.side_effect = lambda *args, **kwargs: "sharded_full_stop_replace"

        flow = MongoUpgradeVersionFlow(root_id="rid", data=payload)
        with patch.object(
            flow, "_build_replicaset_machine_infos", return_value=[{"mongodb": [{"ip": "1.1.1.1"}]}]
        ), patch.object(
            flow, "_build_sharded_cluster_replace_info", return_value={"mongo_config": [], "mongodb": [], "mongos": []}
        ):
            flow.start()

        # 这里用 side effect 的 mock_replicaset_replace/cluster_replace_* 做判断
        assert mock_replicaset_replace.call_count >= 1
        # full_stop RS: should call replicaset_replace as full_stop_subflows, so also part of calls
        # 至少 2 次 RS 替换（cluster 1 rolling + cluster 3 full_stop）
        assert mock_replicaset_replace.call_count == 2
        # rolling sharded: should use cluster_replace_rolling once (cluster 2)
        assert mock_cluster_replace_rolling.call_count == 1
        # full_stop sharded: none in this test
        assert mock_cluster_replace.call_count == 0

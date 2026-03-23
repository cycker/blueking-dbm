# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

import pytest

from backend.flow.engine.bamboo.scene.mongodb.mongodb_restore import MongoRestoreFlow


def _valid_payload(*, dst_cluster_ids=(10,), bk_biz_id=1):
    infos = []
    for cid in dst_cluster_ids:
        infos.append(
            {
                "task_ids": [{"task_id": "tid-1", "file_name": "dump.tgz"}],
                "src_cluster_id": 1,
                "dst_cluster_id": cid,
                "dst_cluster_type": "MongoReplicaSet",
                "dst_time": "2024-01-01T00:00:00",
                "apply_oplog": False,
                "ns_filter": None,
            }
        )
    return {
        "uid": "uid-1",
        "created_by": "tester",
        "bk_biz_id": bk_biz_id,
        "ticket_type": "MONGODB_RESTORE",
        "infos": infos,
    }


def _make_cluster_mock(*, cluster_id=10, bk_biz_id=1, name="mongo-rs"):
    node = MagicMock()
    node.ip = "10.0.0.1"
    node.bk_cloud_id = 0
    node.port = 27017

    rs = MagicMock()
    rs.get_not_backup_nodes.return_value = [node]

    cluster = MagicMock()
    cluster.cluster_id = cluster_id
    cluster.name = name
    cluster.bk_biz_id = bk_biz_id
    cluster.get_shards.return_value = [rs]
    return cluster


def test_check_payload_rejects_missing_fields():
    with pytest.raises(Exception, match="payload is invalid"):
        MongoRestoreFlow(root_id="r1", data={"uid": "x"})


def test_start_raises_on_duplicate_dst_cluster():
    payload = _valid_payload(dst_cluster_ids=(10, 10))
    flow = MongoRestoreFlow(root_id="r1", data=payload)

    with patch("backend.flow.engine.bamboo.scene.mongodb.mongodb_restore.MongoUtil") as mu_cls, patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_restore.GetFileList"
    ) as gfl_cls:
        mu_inst = MagicMock()
        mu_cls.return_value = mu_inst
        mu_inst.get_mongodb_os_conf.return_value = {"file_path": "/opt/actuator"}
        gfl_inst = MagicMock()
        gfl_cls.return_value = gfl_inst
        gfl_inst.get_db_actuator_package.return_value = []

        with pytest.raises(Exception, match="duplicate cluster_id"):
            flow.start()


def test_start_runs_pipeline_with_mocks():
    payload = _valid_payload(dst_cluster_ids=(10,))
    cluster = _make_cluster_mock(cluster_id=10, bk_biz_id=1)

    sub_builder_instances = []

    class DummySubBuilder:
        def __init__(self, root_id, data):
            self.root_id = root_id
            self.data = data
            self.acts = []
            self.parallel = []
            sub_builder_instances.append(self)

        def add_act(self, **kwargs):
            self.acts.append(kwargs)
            return self

        def add_parallel_sub_pipeline(self, sub_flow_list):
            self.parallel.append(sub_flow_list)
            return self

        def build_sub_process(self, name):
            return ("sub", name)

    class DummyBuilder:
        def __init__(self, root_id, data):
            self.root_id = root_id
            self.data = data
            self.parallel = []
            self.ran = False

        def add_parallel_sub_pipeline(self, sub_flow_list):
            self.parallel.append(sub_flow_list)
            return self

        def run_pipeline(self):
            self.ran = True
            return True

    download_sub = MagicMock()
    download_sub.build_sub_process.return_value = "download_sub"

    restore_sub = MagicMock()
    restore_sub.build_sub_process.return_value = "restore_sub"

    dummy_builder = None

    def builder_factory(root_id, data):
        nonlocal dummy_builder
        dummy_builder = DummyBuilder(root_id, data)
        return dummy_builder

    with patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_restore.Builder",
        side_effect=builder_factory,
    ), patch("backend.flow.engine.bamboo.scene.mongodb.mongodb_restore.SubBuilder", new=DummySubBuilder,), patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_restore.MongoUtil"
    ) as mu_cls, patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_restore.GetFileList"
    ) as gfl_cls, patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_restore.MongoRepository.fetch_many_cluster_dict",
        return_value={10: cluster},
    ), patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_restore.DownloadSubTask.process_shard",
        return_value=download_sub,
    ), patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_restore.RestoreSubTask.process_cluster",
        return_value=(restore_sub, []),
    ), patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_restore.ExecShellScript.act",
        return_value={
            "act_name": "prep",
            "act_component_code": "prep",
            "kwargs": {},
        },
    ), patch(
        "backend.flow.engine.bamboo.scene.mongodb.mongodb_restore.SendMedia.act",
        return_value={
            "act_name": "media",
            "act_component_code": "media",
            "kwargs": {},
        },
    ):
        mu_inst = MagicMock()
        mu_cls.return_value = mu_inst
        mu_inst.get_mongodb_os_conf.return_value = {"file_path": "/opt/actuator"}
        gfl_inst = MagicMock()
        gfl_cls.return_value = gfl_inst
        gfl_inst.get_db_actuator_package.return_value = ["pkg.tgz"]

        flow = MongoRestoreFlow(root_id="root-1", data=payload)
        flow.start()

    assert dummy_builder is not None
    assert dummy_builder.ran is True
    assert len(dummy_builder.parallel) == 1
    assert len(dummy_builder.parallel[0]) == 1

    assert len(sub_builder_instances) == 1
    sb = sub_builder_instances[0]
    assert len(sb.acts) == 2
    assert len(sb.parallel) == 2
    download_sub.build_sub_process.assert_called_once()
    restore_sub.build_sub_process.assert_called_once()

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

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from django.utils.translation import gettext as _
from rest_framework import serializers

from backend.db_meta.enums.cluster_type import ClusterType
from backend.db_meta.enums.machine_type import MachineType
from backend.db_meta.models import AppCache, Cluster, Machine
from backend.flow.engine.bamboo.scene.common.builder import Builder
from backend.flow.engine.bamboo.scene.mongodb.base_flow import MongoBaseFlow
from backend.flow.engine.bamboo.scene.mongodb.sub_task.cluster_replace import cluster_replace
from backend.flow.engine.bamboo.scene.mongodb.sub_task.cluster_replace_rolling import cluster_replace_rolling
from backend.flow.engine.bamboo.scene.mongodb.sub_task.replicaset_replace import replicaset_replace
from backend.flow.utils.mongodb.mongodb_dataclass import ActKwargs

logger = logging.getLogger("flow")


@dataclass(frozen=True)
class UpgradeDecision:
    strategy: str  # "rolling" | "full_stop"


class MongoUpgradeVersionFlow(MongoBaseFlow):
    """
    MongoUpgradeVersionFlow: 版本升级 flow（复用现有 mongodb replace 能力）
    """

    class Serializer(serializers.Serializer):
        cluster_ids = serializers.ListField(help_text=_("集群ID列表"), child=serializers.IntegerField())
        target_db_version = serializers.CharField(help_text=_("目标 DB 发行版本（带 release 前缀）"))

        # FlowTestView 场景通常需要这两个字段用于配置/密码/元数据写入
        created_by = serializers.CharField(help_text=_("创建人"))
        bk_biz_id = serializers.IntegerField(help_text=_("业务ID"))

        # 当用户显式指定时以该值为准；不指定则按 major 判断 rolling/full_stop
        strategy = serializers.ChoiceField(help_text=_("升级策略"), choices=["rolling", "full_stop"], required=False)

        # 兼容前端可能传入的透传字段
        ticket_type = serializers.CharField(required=False)
        uid = serializers.CharField(required=False)

    def __init__(self, root_id: str, data: Optional[Dict]):
        super().__init__(root_id, data)
        self.check_payload()

    def check_payload(self):
        s = self.Serializer(data=self.payload)
        if not s.is_valid():
            raise Exception(f"payload is invalid {s.errors}")

    @staticmethod
    def _parse_main_version(db_version: str) -> str:
        """
        db_version 约定：<release>-<main>.<minor>.<patch>
        取 main 版本号用于判断 rolling/full_stop。
        """
        if not db_version or "-" not in db_version:
            raise ValueError(f"bad db_version format: {db_version}")
        return db_version.split("-")[1].split(".")[0]

    def _decide_strategy(self, current_db_version: str) -> UpgradeDecision:
        if self.payload.get("strategy"):
            return UpgradeDecision(strategy=self.payload["strategy"])

        # major 变更 -> full_stop；否则 rolling
        current_main = self._parse_main_version(current_db_version)
        target_main = self._parse_main_version(self.payload["target_db_version"])
        return UpgradeDecision(strategy="full_stop" if current_main != target_main else "rolling")

    @staticmethod
    def _normalize_spec_config(machine: Machine) -> dict:
        spec_config = machine.spec_config or {}
        if isinstance(spec_config, str):
            spec_config = json.loads(spec_config)
        if not isinstance(spec_config, dict):
            return {}
        # 统一补齐 id，避免下游取 spec["id"]
        spec_config = {**spec_config}
        spec_config.setdefault("id", machine.spec_id)
        return spec_config

    @classmethod
    def _spec_config_to_storage_device(cls, spec_config: dict) -> dict:
        """
        将 Machine.spec_config 中的 storage_spec 转成 mongodb_dataclass calc_param_replace 需要的 storage_device 形态：
        {"/data1": {"min": x, "size": y}, "/data": {"min": x, "size": y}}
        """
        storage_device = spec_config.get("storage_device")
        if isinstance(storage_device, dict) and storage_device:
            return storage_device

        storage_spec = spec_config.get("storage_spec") or []
        if not storage_spec:
            return {}

        # storage_spec: [{"mount_point":"/data","min":10,"max":100,"type":"ALL"}, ...]
        result = {}
        for item in storage_spec:
            mount_point = item.get("mount_point")
            if not mount_point:
                continue
            min_size = item.get("min")
            max_size = item.get("max")
            # calc_param_replace 优先使用 "size"，否则用 "min"
            result[mount_point] = {"min": min_size, "size": max_size if max_size is not None else min_size}
        return result

    @classmethod
    def _build_target_from_machine(cls, machine: Machine) -> dict:
        """
        构建 replace 子任务需要的 target 信息（in-place 升级：target ip 与 source ip 相同）。
        """
        spec_config = cls._normalize_spec_config(machine)
        storage_device = cls._spec_config_to_storage_device(spec_config)
        if not storage_device:
            raise ValueError(f"machine {machine.bk_cloud_id}:{machine.ip} missing storage_device")

        mem_cfg = spec_config.get("mem") or {}
        mem_min_gb = mem_cfg.get("min")
        if mem_min_gb is None:
            raise ValueError(f"machine {machine.bk_cloud_id}:{machine.ip} missing mem.min in spec_config")

        cpu_cfg = spec_config.get("cpu") or {}
        cpu_min = cpu_cfg.get("min", "")

        # MongoDB calc_param_replace 需要 bk_mem（MB）
        bk_mem_mb = int(mem_min_gb * 1024)
        return {
            "ip": machine.ip,
            "bk_cloud_id": machine.bk_cloud_id,
            "bk_cpu": cpu_min,
            "bk_mem": bk_mem_mb,
            "storage_device": storage_device,
            # replace 元数据更新需要 spec["id"] 以及 spec_config
            "spec": spec_config,
        }

    def _build_replicaset_machine_infos(self, cluster: Cluster, target_db_version: str) -> List[dict]:
        """
        replica set：按“机器(ip)”粒度构造 replace 所需 info，方便 rolling 时串行。
        返回值：List[replicaset_wrapper]，每个 wrapper 形如 {"mongodb":[machine_info]}，
        其中 machine_info 形如 {"ip","bk_cloud_id","target","instances"}。
        """
        # MongoRepository 的 domain 对 replica set 取值可靠，但为构造 instances/domain 这里直接用 instance 表。
        # cluster.storageinstance_set 可能较大，这里按 cluster id 过滤。
        storage_insts = cluster.storageinstance_set.select_related("machine").prefetch_related("bind_entry")

        # machine 分组
        by_ip: Dict[Tuple[str, int], List] = {}
        for inst in storage_insts.all():
            key = (inst.machine.ip, inst.machine.bk_cloud_id)
            by_ip.setdefault(key, []).append(inst)

        wrappers: List[dict] = []
        for (ip, bk_cloud_id), insts in by_ip.items():
            machine = Machine.objects.get(ip=ip, bk_cloud_id=bk_cloud_id)
            target = self._build_target_from_machine(machine)
            instances = []
            for inst in insts:
                domain = inst.bind_entry.first().entry if inst.bind_entry.exists() else ""
                instances.append(
                    {
                        "cluster_id": cluster.id,
                        "cluster_name": cluster.name,
                        "port": inst.port,
                        "domain": domain,
                        "instance_role": inst.instance_role,
                        "db_version": target_db_version,
                    }
                )
            machine_info = {
                "ip": ip,
                "bk_cloud_id": bk_cloud_id,
                "target": target,
                "instances": instances,
            }
            wrappers.append({"mongodb": [machine_info]})
        return wrappers

    def _build_sharded_cluster_replace_info(self, cluster: Cluster, target_db_version: str) -> dict:
        """
        sharded cluster：构造 cluster_replace 需要的整机 wrapper：
        {
          "mongo_config":[{ip,bk_cloud_id,target,instances}],
          "mongodb":[{ip,bk_cloud_id,target,instances}],
          "mongos":[{ip,bk_cloud_id,target,instances}],
        }
        """
        # config/shard：来自 nosqlstoragesetdtl_set（包含 seg_range 与成员关系）
        mongo_config_groups: Dict[Tuple[str, int], List[dict]] = {}
        mongodb_groups: Dict[Tuple[str, int], List[dict]] = {}

        # nosqlstoragesetdtl_set 为 sharded cluster 专用关系
        for dtl in cluster.nosqlstoragesetdtl_set.select_related("instance__machine").all():
            seg_range = dtl.seg_range
            base_inst = dtl.instance
            is_config = base_inst.machine_type == MachineType.MONOG_CONFIG.value
            role_groups = mongo_config_groups if is_config else mongodb_groups

            member_insts = [base_inst]
            for e in base_inst.as_ejector.all():
                member_insts.append(e.receiver)

            for member in member_insts:
                key = (member.machine.ip, member.machine.bk_cloud_id)
                domain = member.bind_entry.first().entry if member.bind_entry.exists() else ""
                role_groups.setdefault(key, []).append(
                    {
                        "cluster_id": cluster.id,
                        "cluster_name": cluster.name,
                        "seg_range": seg_range,
                        "port": member.port,
                        "domain": domain,
                        "instance_role": member.instance_role,
                        "db_version": target_db_version,
                    }
                )

        mongo_config = []
        for (ip, bk_cloud_id), instances in mongo_config_groups.items():
            machine = Machine.objects.get(ip=ip, bk_cloud_id=bk_cloud_id)
            mongo_config.append(
                {
                    "ip": ip,
                    "bk_cloud_id": bk_cloud_id,
                    "target": self._build_target_from_machine(machine),
                    "instances": instances,
                }
            )

        mongodb = []
        for (ip, bk_cloud_id), instances in mongodb_groups.items():
            machine = Machine.objects.get(ip=ip, bk_cloud_id=bk_cloud_id)
            mongodb.append(
                {
                    "ip": ip,
                    "bk_cloud_id": bk_cloud_id,
                    "target": self._build_target_from_machine(machine),
                    "instances": instances,
                }
            )

        # mongos
        mongos_groups: Dict[Tuple[str, int], List[dict]] = {}
        proxy_insts = cluster.proxyinstance_set.select_related("machine").prefetch_related("bind_entry")
        for inst in proxy_insts.all():
            key = (inst.machine.ip, inst.machine.bk_cloud_id)
            domain = inst.bind_entry.first().entry if inst.bind_entry.exists() else ""
            mongos_groups.setdefault(key, []).append(
                {
                    "cluster_id": cluster.id,
                    "cluster_name": cluster.name,
                    "port": inst.port,
                    "domain": domain,
                    "instance_role": inst.instance_role,
                    "db_version": target_db_version,
                }
            )

        mongos = []
        for (ip, bk_cloud_id), instances in mongos_groups.items():
            machine = Machine.objects.get(ip=ip, bk_cloud_id=bk_cloud_id)
            mongos.append(
                {
                    "ip": ip,
                    "bk_cloud_id": bk_cloud_id,
                    "target": self._build_target_from_machine(machine),
                    "instances": instances,
                }
            )

        return {"mongo_config": mongo_config, "mongodb": mongodb, "mongos": mongos}

    def start(self):
        logger.debug("MongoUpgradeVersionFlow start, payload %s", self.payload)

        cluster_ids = self.payload["cluster_ids"]
        self.check_cluster_id_list(cluster_ids)

        clusters = list(Cluster.objects.filter(id__in=cluster_ids).select_related("bk_city", "bk_biz_id").all())
        cluster_map = {c.id: c for c in clusters}
        missing_ids = [cid for cid in cluster_ids if cid not in cluster_map]
        if missing_ids:
            raise ValueError(f"cluster(s) not found: {sorted(set(missing_ids))}")

        # 校验 bk_biz_id 一致 + major 版本格式可解析
        for cluster_id in set(cluster_ids):
            cluster = cluster_map[cluster_id]
            self.check_cluster_valid(cluster, self.payload)
            # 触发一次解析，提前发现格式问题
            _ = self._parse_main_version(cluster.major_version)

        target_db_version = self.payload["target_db_version"]
        _ = self._parse_main_version(target_db_version)
        created_by = self.payload["created_by"]
        bk_biz_id = self.payload["bk_biz_id"]

        # 全局 payload（给 ActKwargs/replace 子任务使用）
        global_payload = {
            "created_by": created_by,
            "bk_biz_id": bk_biz_id,
            "bk_app_abbr": AppCache.get_app_attr(bk_biz_id),
        }

        # 共享 get_kwargs（每个子任务会 deepcopy）
        get_kwargs = ActKwargs()
        get_kwargs.payload = dict(global_payload)
        get_kwargs.get_file_path()

        full_stop_subflows = []

        # rolling/full_stop 需要在同 root_id 下按拓扑编排
        pipeline = Builder(root_id=self.root_id, data=dict(global_payload))

        # 为避免“回滚/替换”并发过多，滚动策略按输入顺序串行；
        # 停机策略则对同一策略的 cluster 并行。
        for cluster_id in cluster_ids:
            cluster = cluster_map[cluster_id]
            decision = self._decide_strategy(cluster.major_version)
            logger.info(
                "[mongo_upgrade_version] cluster_id=%s cluster_type=%s decision=%s current=%s target=%s",
                cluster.id,
                cluster.cluster_type,
                decision.strategy,
                cluster.major_version,
                target_db_version,
            )

            if cluster.cluster_type == ClusterType.MongoReplicaSet.value:
                try:
                    machine_wrappers = self._build_replicaset_machine_infos(cluster, target_db_version)
                except Exception as exc:
                    logger.exception(
                        "[mongo_upgrade_version] build rs replace infos failed cluster_id=%s error=%s",
                        cluster.id,
                        str(exc),
                    )
                    raise
                if decision.strategy == "full_stop":
                    for wrapper in machine_wrappers:
                        full_stop_subflows.append(
                            replicaset_replace(
                                root_id=self.root_id,
                                ticket_data=dict(global_payload),
                                sub_kwargs=get_kwargs,
                                info=wrapper,
                                cluster_role="",
                            )
                        )
                else:
                    # rolling: replica set 按机器串行
                    for wrapper in machine_wrappers:
                        pipeline.add_sub_pipeline(
                            sub_flow=replicaset_replace(
                                root_id=self.root_id,
                                ticket_data=dict(global_payload),
                                sub_kwargs=get_kwargs,
                                info=wrapper,
                                cluster_role="",
                            )
                        )
            elif cluster.cluster_type == ClusterType.MongoShardedCluster.value:
                try:
                    replace_info = self._build_sharded_cluster_replace_info(cluster, target_db_version)
                except Exception as exc:
                    logger.exception(
                        "[mongo_upgrade_version] build sharded replace infos failed cluster_id=%s error=%s",
                        cluster.id,
                        str(exc),
                    )
                    raise
                if decision.strategy == "full_stop":
                    full_stop_subflows.append(
                        cluster_replace(
                            root_id=self.root_id,
                            ticket_data=dict(global_payload),
                            sub_kwargs=get_kwargs,
                            info=replace_info,
                        )
                    )
                else:
                    pipeline.add_sub_pipeline(
                        sub_flow=cluster_replace_rolling(
                            root_id=self.root_id,
                            ticket_data=dict(global_payload),
                            sub_kwargs=get_kwargs,
                            info=replace_info,
                        )
                    )
            else:
                raise ValueError(f"unsupported cluster_type {cluster.cluster_type}")

        if full_stop_subflows:
            pipeline.add_parallel_sub_pipeline(sub_flow_list=full_stop_subflows)

        pipeline.run_pipeline()

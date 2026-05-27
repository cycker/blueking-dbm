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
import logging
import logging.config
import time
import uuid
from typing import List

from django.db import transaction
from pipeline.component_framework.component import Component
from pipeline.core.flow.activity import Service

from backend.db_meta import api
from backend.db_meta.enums import ClusterType, InstanceRole, InstanceStatus, MachineType
from backend.db_meta.models import Cluster, Machine, StorageInstance, StorageInstanceTuple
from backend.flow.plugins.components.collections.common.base_service import BaseService
from backend.flow.utils.mongodb.mongodb_module_operate import MongoDBCCTopoOperator
from backend.utils.redis import RedisConn

logger = logging.getLogger("flow")


class MongoDBCapcityMetaService(BaseService):
    """
    集群容量变更:
      # 该元数据操作包含 : 1.安装, 2.添加到集群, 3.下架, 4.CC信息维护
    {
      "created_by":"xxxx",
      "immute_domain":"xxx", # 可选
      "cluster_id":1111,  # 必须的
      "bk_biz_id":0,
      "mongodb": [
                {
                    "ip": "1.a.b.c","port":20000,
                    "target": {"ip": "1.a.b.c","port":20000,"spec_id":111,"spec_config":{}},
                }
            ],
    }

    """

    LOCK_TTL_SECONDS = 300
    MAX_RETRY_TIMES = 10
    MAX_EXECUTE_ATTEMPTS = MAX_RETRY_TIMES + 1
    LOCK_KEY_PREFIX = "dbm:mongodb:capacity_meta:host"
    REDIS_LOCK_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

    @classmethod
    def _build_host_lock_keys(cls, kwargs: dict) -> List[str]:
        host_ips = set()
        for item in kwargs.get("mongodb", []):
            if item.get("ip"):
                host_ips.add(item["ip"])
            target = item.get("target") or {}
            if target.get("ip"):
                host_ips.add(target["ip"])

        return [
            "{}:{}:{}:{}".format(cls.LOCK_KEY_PREFIX, kwargs["bk_biz_id"], kwargs["cluster_id"], ip)
            for ip in sorted(host_ips)
        ]

    @classmethod
    def _release_host_locks(cls, lock_keys: List[str], lock_value: str):
        if not lock_keys:
            return

        release_script = RedisConn.register_script(cls.REDIS_LOCK_RELEASE_LUA)
        for lock_key in lock_keys:
            try:
                release_script(keys=[lock_key], args=[lock_value])
            except Exception:  # pylint: disable=broad-except
                logger.warning("failed to release mongo meta lock key=%s", lock_key, exc_info=True)

    @classmethod
    def _acquire_host_locks(cls, kwargs: dict):
        lock_keys = cls._build_host_lock_keys(kwargs)
        lock_value = str(uuid.uuid4())
        acquired_keys = []

        for lock_key in lock_keys:
            locked = RedisConn.set(lock_key, lock_value, nx=True, ex=cls.LOCK_TTL_SECONDS)
            if not locked:
                cls._release_host_locks(acquired_keys, lock_value)
                raise Exception("mongo meta host lock busy, lock_key={}".format(lock_key))
            acquired_keys.append(lock_key)
        return lock_keys, lock_value

    def _execute_meta_change(self, kwargs: dict):
        mongo_cluster = Cluster.objects.get(bk_biz_id=kwargs["bk_biz_id"], id=kwargs["cluster_id"])
        # 仅支持 MongoDB 实例级的容量变更
        if kwargs.get("mongodb"):
            logger.info(
                "mongo cluster capcity specs changes %s mongodb: %s",
                mongo_cluster.immute_domain,
                kwargs.get("mongodb"),
            )
            self.mongdb_instance_spec_modify(
                mongo_cluster,
                kwargs.get("mongodb"),
                MachineType.MONGODB.value,
                kwargs.get("created_by"),
            )
        else:
            raise Exception("unexpected inputs by cluster specs changs. {}".format(kwargs))

    def _execute(self, data, parent_data) -> bool:
        kwargs = data.get_one_of_inputs("kwargs")
        bk_biz_id = kwargs.get("bk_biz_id")
        cluster_id = kwargs.get("cluster_id")
        mongodb_items = kwargs.get("mongodb") or []
        total_attempts = self.MAX_EXECUTE_ATTEMPTS

        for index in range(total_attempts):
            lock_keys = []
            lock_value = ""
            attempt = index + 1
            log_context = "bk_biz_id={}, cluster_id={}, mongodb_items={}, attempt={}/{}".format(
                bk_biz_id, cluster_id, len(mongodb_items), attempt, total_attempts
            )
            try:
                lock_keys, lock_value = self._acquire_host_locks(kwargs)
                self._execute_meta_change(kwargs)
                logger.info(
                    "mongo capacity meta update succeeded, %s, lock_keys=%s",
                    log_context,
                    len(lock_keys),
                )
                return True
            except Exception as err:
                if index < total_attempts - 1:
                    logger.warning(
                        "mongo capacity meta update failed, will retry in 5s, %s, error=%s",
                        log_context,
                        str(err),
                    )
                    time.sleep(5)
                    continue
                logger.error(
                    "mongo capacity meta update failed after all retries, %s, error=%s",
                    log_context,
                    str(err),
                    exc_info=True,
                )
                return False
            finally:
                self._release_host_locks(lock_keys, lock_value)

        return False

    # mongdb/mongo_cofig 替换
    @transaction.atomic
    def mongdb_instance_spec_modify(self, cluster: Cluster, mongodb_info, machine_type, created_by):
        machines, mongdb_insts = {}, []
        for rep_link in mongodb_info:
            old_ip, new_ip = rep_link["ip"], rep_link["target"]["ip"]
            old_port, new_port = rep_link["port"], rep_link["target"]["port"]
            logger.info(
                "cluster {} replace mongodb from {}:{} 【2】 {} begin.".format(
                    cluster.immute_domain, old_ip, old_port, rep_link["target"]
                )
            )
            # 机器
            machines[new_ip] = {
                "ip": new_ip,
                "bk_biz_id": cluster.bk_biz_id,
                "bk_cloud_id": cluster.bk_cloud_id,
                "machine_type": machine_type,
                "spec_id": rep_link["target"]["spec_id"],
                "spec_config": rep_link["target"]["spec_config"],
            }
            # 实例
            old_obj = StorageInstance.objects.get(machine__ip=old_ip, port=old_port, bk_biz_id=cluster.bk_biz_id)
            mongdb_insts.append(
                {
                    "old": {"ip": old_ip, "port": old_port, "instance_role": old_obj.instance_role},
                    "new": {
                        "ip": new_ip,
                        "port": new_port,
                        "instance_role": old_obj.instance_role,
                    },
                }
            )

        # 新增 mongos 到集群
        for machine in machines.values():
            if Machine.objects.filter(
                ip=machine["ip"],
                bk_biz_id=cluster.bk_biz_id,
                bk_cloud_id=cluster.bk_cloud_id,
                machine_type=MachineType.MONGODB.value,
            ).exists():
                logger.info("machine exists 4 replicate ,reuse it. {}".format(machine))
            else:
                api.machine.create(machines=[machine], bk_cloud_id=cluster.bk_cloud_id, creator=created_by)
        api.storage_instance.create(
            instances=[inst["new"] for inst in mongdb_insts], status=InstanceStatus.RUNNING.value, creator=created_by
        )
        self.mongo_package_meta(cluster, mongdb_insts, created_by)

        # # 实例下架
        api.cluster.nosqlcomm.decommission_backends(
            cluster, backends=[inst["old"] for inst in mongdb_insts], is_all=False
        )

    @transaction.atomic
    def mongo_package_meta(self, cluster, rep_insts, created_by):
        """
        Rewire metadata from old mongodb instances to new ones during capacity replace.

        Steps per replacement pair:
        1. Mark old storage instance as UNAVAILABLE.
        2. Copy role/cluster attributes to new storage instance and its machine.
        3. Move cluster relation and bind entries from old instance to new instance.
        4. Rebuild topology relations:
           - M1: proxy links (for sharded mongodb), setdtl master reference, tuple ejector.
           - Slave: tuple receiver.
        5. Transfer new instances to target CC module after all pairs are processed.

        Wrapped by transaction.atomic to keep metadata changes consistent.
        """
        new_objs, ins_is_increment = [], False
        for inst_pair in rep_insts:
            old_ip, old_port = inst_pair["old"]["ip"], inst_pair["old"]["port"]
            new_ip, new_port = inst_pair["new"]["ip"], inst_pair["new"]["port"]
            old_obj = cluster.storageinstance_set.get(machine__ip=old_ip, port=old_port)
            new_obj = StorageInstance.objects.get(
                machine__ip=new_ip,
                port=new_port,
                bk_biz_id=cluster.bk_biz_id,
                machine__bk_cloud_id=cluster.bk_cloud_id,
            )

            # storageinstance  实例信息更新
            old_obj.status = InstanceStatus.UNAVAILABLE
            old_obj.save(update_fields=["status"])

            new_obj.instance_role = old_obj.instance_role
            new_obj.instance_inner_role = old_obj.instance_inner_role
            new_obj.cluster_type = old_obj.cluster_type
            new_obj.save(update_fields=["cluster_type", "instance_role", "instance_inner_role"])
            # machine 实例信息更新
            new_machine = new_obj.machine
            new_machine.cluster_type = old_obj.cluster_type
            new_machine.save(update_fields=["cluster_type"])
            logger.info("update {} role , cluster_type {}".format(new_ip, old_obj.cluster_type))

            # storageinstance_cluster 只做添加
            cluster.storageinstance_set.add(new_obj)

            # storageinstance_bind_entry 表更新
            tmp_entries = old_obj.bind_entry.all()
            new_obj.bind_entry.add(*tmp_entries)
            old_obj.bind_entry.clear()

            # 如果是 Master 节点
            if old_obj.instance_role == InstanceRole.MONGO_M1.value:
                # mongos 关系建立 [M1] / 只有mongodb 才有 ； mongo_config没有
                if (
                    old_obj.machine_type == MachineType.MONGODB.value
                    and cluster.cluster_type == ClusterType.MongoShardedCluster.value
                ):
                    tmp_proxy_objs = list(old_obj.proxyinstance_set.all())
                    new_obj.proxyinstance_set.add(*tmp_proxy_objs)
                    old_obj.proxyinstance_set.clear()
                    logger.info("add mongos link 4 storage {}:{}".format(cluster.immute_domain, new_obj))

                # nosqlstoragesetdtl 表更新
                logger.info(
                    "change cluster {} setdtl master from {} to {}".format(cluster.immute_domain, old_obj, new_obj)
                )
                cluster.nosqlstoragesetdtl_set.filter(instance=old_obj).update(instance=new_obj)

                # storageinstancetuple 表更新
                for tuple in StorageInstanceTuple.objects.filter(ejector=old_obj):
                    StorageInstanceTuple.objects.create(ejector=new_obj, receiver=tuple.receiver, creator=created_by)
                    tuple.delete()
            # slave 节点
            else:
                # tuple 表更新
                old_tuple = StorageInstanceTuple.objects.get(receiver=old_obj)
                StorageInstanceTuple.objects.create(ejector=old_tuple.ejector, receiver=new_obj, creator=created_by)
                old_tuple.delete()
            new_objs.append(new_obj)
            # 转移模块
            if cluster.cluster_type == ClusterType.MongoReplicaSet.value:
                ins_is_increment = True
        MongoDBCCTopoOperator(cluster).transfer_instances_to_cluster_module(
            instances=new_objs, is_increment=ins_is_increment
        )

    # 流程节点输入参数
    def inputs_format(self) -> List:
        return [
            Service.InputItem(name="kwargs", key="kwargs", type="dict", required=True),
            Service.InputItem(name="global_data", key="global_data", type="dict", required=True),
        ]


class MongoDBCapcityMetaComponent(Component):
    """
    Mongo 容量变更
    ShardCluster , ReplicateRet
    """

    name = __name__
    code = "mongodb_capcity_meta"
    bound_service = MongoDBCapcityMetaService

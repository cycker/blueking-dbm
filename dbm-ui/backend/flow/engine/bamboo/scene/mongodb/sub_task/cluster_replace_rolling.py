# -*- coding: utf-8 -*-
"""
滚动升级场景下的 MongoDB sharded 整机替换（config/shard/mongos 串行）。
"""

from copy import deepcopy
from typing import Dict, Optional

from django.utils.translation import gettext as _

from backend.db_meta.enums.cluster_type import ClusterType
from backend.flow.consts import MongoDBClusterRole, MongoDBInstanceType
from backend.flow.engine.bamboo.scene.common.builder import SubBuilder
from backend.flow.engine.bamboo.scene.mongodb.mongodb_install import install_plugin
from backend.flow.engine.bamboo.scene.mongodb.mongodb_install_dbmon import add_install_dbmon
from backend.flow.engine.bamboo.scene.mongodb.sub_task.multi_instance_deinstall import multi_instance_deinstall
from backend.flow.plugins.components.collections.mongodb.exec_actuator_job import ExecuteDBActuatorJobComponent
from backend.flow.plugins.components.collections.mongodb.mongodb_cmr_4_meta import CMRMongoDBMetaComponent
from backend.flow.plugins.components.collections.mongodb.send_media import ExecSendMediaOperationComponent
from backend.flow.utils.mongodb.mongodb_dataclass import ActKwargs

from .mongos_replace import mongos_replace
from .replicaset_replace import replicaset_replace


def cluster_replace_rolling(
    root_id: str, ticket_data: Optional[Dict], sub_kwargs: ActKwargs, info: dict
) -> SubBuilder:
    """
    cluster_replace 的 rolling 版本：
    1) 共享前置准备步骤保持一致（get_host_replace / install_plugin / send_media / os_init）
    2) 替换阶段 config/shard/mongos 改为串行，减少同时中断窗口
    """

    sub_get_kwargs = deepcopy(sub_kwargs)

    # 获取老的 configDB 配置
    mongos_nodes = {}
    old_config_node = ""
    new_config_node = ""
    if info.get("mongo_config"):
        sub_get_kwargs.get_cluster_info_deinstall(cluster_id=info["mongo_config"][0]["instances"][0]["cluster_id"])
        config_port = info["mongo_config"][0]["instances"][0]["port"]
        old_config_node = "{}:{}".format(info["mongo_config"][0]["ip"], config_port)
        new_config_node = "{}:{}".format(info["mongo_config"][0]["target"]["ip"], config_port)
        mongos_nodes = sub_get_kwargs.payload["mongos_nodes"]

    # 创建子流程
    sub_pipeline = SubBuilder(root_id=root_id, data=ticket_data)

    # 获取信息：替换 host / plugin_hosts / deinstall_hosts / payload[db_version] 等
    sub_get_kwargs.get_host_replace(mongodb_type=ClusterType.MongoShardedCluster.value, info=info)
    if info.get("mongo_config"):
        sub_get_kwargs.get_mongos_host_replace()

    # 安装蓝鲸插件
    install_plugin(pipeline=sub_pipeline, get_kwargs=sub_get_kwargs, new_cluster=False)

    # 介质下发
    kwargs = sub_get_kwargs.get_send_media_kwargs(media_type="all")
    sub_pipeline.add_act(
        act_name=_("MongoDB-介质下发"), act_component_code=ExecSendMediaOperationComponent.code, kwargs=kwargs
    )

    # 创建原子任务执行目录
    kwargs = sub_get_kwargs.get_create_dir_kwargs()
    sub_pipeline.add_act(
        act_name=_("MongoDB-创建原子任务执行目录"), act_component_code=ExecuteDBActuatorJobComponent.code, kwargs=kwargs
    )

    # 机器初始化
    kwargs = sub_get_kwargs.get_os_init_kwargs()
    sub_pipeline.add_act(
        act_name=_("MongoDB-机器初始化"), act_component_code=ExecuteDBActuatorJobComponent.code, kwargs=kwargs
    )

    # 先替换 config（以 ip 为维度，串行）
    if info.get("mongo_config"):
        for config_info_by_ip in info.get("mongo_config"):
            sub_sub_pipeline = replicaset_replace(
                root_id=root_id,
                ticket_data=ticket_data,
                sub_kwargs=sub_get_kwargs,
                info=config_info_by_ip,
                cluster_role=MongoDBClusterRole.ConfigSvr.value,
            )
            sub_pipeline.add_sub_pipeline(sub_flow=sub_sub_pipeline)

    # 再替换 shard（以 ip 为维度，串行）
    if info.get("mongodb"):
        for shard_info_by_ip in info.get("mongodb"):
            sub_sub_pipeline = replicaset_replace(
                root_id=root_id,
                ticket_data=ticket_data,
                sub_kwargs=sub_get_kwargs,
                info=shard_info_by_ip,
                cluster_role=MongoDBClusterRole.ShardSvr.value,
            )
            sub_pipeline.add_sub_pipeline(sub_flow=sub_sub_pipeline)

    # 修改 mongos 参数文件（只修改参数，不重启进程）
    if info.get("mongo_config"):
        act_lists = []
        for mongos_node in mongos_nodes:
            mongos_node["role"] = MongoDBInstanceType.MongoS.value
            kwargs = sub_get_kwargs.get_instance_restart_kwargs(
                host=mongos_node,
                cache_size_gb=0,
                mongos_conf_db_old=old_config_node,
                mongos_conf_db_new=new_config_node,
                cluster_id=info.get("mongo_config")[0]["instances"][0]["cluster_id"],
                instance=mongos_node,
                only_change_param=True,
            )
            act_lists.append(
                {
                    "act_name": _("MongoDB-{}-mongos修改参数".format(mongos_node["ip"])),
                    "act_component_code": ExecuteDBActuatorJobComponent.code,
                    "kwargs": kwargs,
                }
            )
        if act_lists:
            sub_pipeline.add_parallel_acts(acts_list=act_lists)

    # 替换 mongos（以 ip 为维度，串行）
    if info.get("mongos"):
        for mongos_info_by_ip in info.get("mongos"):
            for mongos_instance in mongos_info_by_ip["instances"]:
                sub_get_kwargs.db_instance = mongos_instance
                sub_sub_pipeline = mongos_replace(
                    root_id=root_id, ticket_data=ticket_data, sub_sub_kwargs=sub_get_kwargs, info=mongos_info_by_ip
                )
                sub_pipeline.add_sub_pipeline(sub_flow=sub_sub_pipeline)

        # mongos 修改 db_meta 数据
        info["db_type"] = "mongos"
        info["created_by"] = sub_get_kwargs.payload.get("created_by")
        info["bk_biz_id"] = sub_get_kwargs.payload.get("bk_biz_id")
        kwargs = sub_get_kwargs.get_change_meta_replace_kwargs(info=info, instance={})
        sub_pipeline.add_act(
            act_name=_("MongoDB-mongos修改meta"), act_component_code=CMRMongoDBMetaComponent.code, kwargs=kwargs
        )

    # 安装 dbmon
    ip_list = sub_get_kwargs.payload["plugin_hosts"]
    exec_ips = [host["ip"] for host in ip_list]
    add_install_dbmon(
        root_id=root_id,
        flow_data=ticket_data,
        pipeline=sub_pipeline,
        iplist=exec_ips,
        bk_cloud_id=ip_list[0]["bk_cloud_id"],
        allow_empty_instance=True,
    )

    # 下架 mongodb/mongo_config/mongos
    old_hosts, old_instances = sub_get_kwargs.get_old_host_replace(
        info=info, cluster_type=ClusterType.MongoShardedCluster.value
    )
    if info.get("mongodb") or info.get("mongo_config"):
        instance_type = MongoDBInstanceType.MongoD.value
    elif info.get("mongos"):
        instance_type = MongoDBInstanceType.MongoS.value
    else:
        instance_type = MongoDBInstanceType.MongoS.value

    sub_sub_pipeline = multi_instance_deinstall(
        root_id=root_id,
        ticket_data=ticket_data,
        sub_kwargs=sub_get_kwargs,
        old_hosts=old_hosts,
        old_instances=old_instances,
        instance_type=instance_type,
    )
    sub_pipeline.add_sub_pipeline(sub_flow=sub_sub_pipeline)

    return sub_pipeline.build_sub_process(sub_name=_("MongoDB--cluster整机替换-rolling"))

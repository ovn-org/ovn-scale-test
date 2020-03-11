# Copyright (c) 2020, Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from rally_ovs.plugins.ovs.scenarios import ovn
from rally.task import atomic
from rally.task import scenario
import time
import netaddr

"""Scenario to dynamically add/delete ovn nodes running in containers.

This scenario is applicable for clusters deployed using:
https://github.com/ovn-org/ovn-fake-multinode
"""
class OvnFakeMultinode(ovn.OvnScenario):

    def __init__(self, context=None):
        super(OvnFakeMultinode, self).__init__(context)
        self._init_sandboxes(context)

    def _init_sandboxes(self, context):
        self._sandboxes = {sb["farm"]: sb for sb in self.context["sandboxes"]}

    def _get_sandbox(self, sb_name):
        return self._sandboxes[sb_name]

    def _get_sandbox_conn(self, sb_name, sb, host_container=None):
        farm = sb["farm"]
        ssh = self.farm_clients(farm, "ovs-ssh")
        ssh.set_sandbox(sb_name, self.install_method, host_container)
        ssh.enable_batch_mode(False)
        return ssh

    def _add_central(self, ssh_conn, node_net, node_net_len, node_ip,
                     ovn_fake_path, monitor_all=False, cluster_db=False):
        if monitor_all:
            monitor_cmd = "OVN_MONITOR_ALL=yes"
        else:
            monitor_cmd = "OVN_MONITOR_ALL=no"

        if cluster_db:
            cluster_db_cmd = "OVN_DB_CLUSTER=yes"
        else:
            cluster_db_cmd = "OVN_DB_CLUSTER=no"

        cmd = "cd {} && CHASSIS_COUNT=0 GW_COUNT=0 IP_HOST={} IP_CIDR={} IP_START={} {} {} CREATE_FAKE_VMS=no ./ovn_cluster.sh start".format(
            ovn_fake_path, node_net, node_net_len, node_ip, monitor_cmd, cluster_db_cmd
        )
        ssh_conn.run(cmd)

        time.sleep(5)

    def _add_chassis(self, ssh_conn, node_net, node_net_len, node_ip, node_name,
                     ovn_fake_path, monitor_all=False, cluster_db=False):
        invalid_remote = "tcp:0.0.0.1:6642"
        if monitor_all:
            monitor_cmd = "OVN_MONITOR_ALL=yes"
        else:
            monitor_cmd = "OVN_MONITOR_ALL=no"

        if cluster_db:
            cluster_db_cmd = "OVN_DB_CLUSTER=yes"
        else:
            cluster_db_cmd = "OVN_DB_CLUSTER=no"

        cmd = "cd {} && IP_HOST={} IP_CIDR={} IP_START={} {} {} ./ovn_cluster.sh add-chassis {} {}".format(
            ovn_fake_path, node_net, node_net_len, node_ip, monitor_cmd, cluster_db_cmd,
            node_name, invalid_remote
        )
        ssh_conn.run(cmd)

    def _connect_chassis(self, ssh_conn, node_name, central_ip, sb_proto,
                         ovn_fake_path):
        central_ips = [ip.strip() for ip in central_ip.split('-')]
        remote = ",".join(["{}:{}:6642".format(sb_proto, r) for r in central_ips])

        cmd = "cd {} && ./ovn_cluster.sh set-chassis-ovn-remote {} {}".format(
            ovn_fake_path, node_name, remote
        )
        ssh_conn.run(cmd)

    def _wait_chassis(self, sbctl_conn, chassis_name, max_timeout_s):
        for i in range(0, max_timeout_s * 10):
            if sbctl_conn.chassis_bound(chassis_name):
                break
            time.sleep(0.1)

    def _del_chassis(self, ssh_conn, node_name, ovn_fake_path):
        cmd = "cd {} && OVN_BR_CLEANUP=no ./ovn_cluster.sh stop-chassis {}".format(
            ovn_fake_path, node_name
        )
        ssh_conn.run(cmd)

    def _del_central(self, ssh_conn, ovn_fake_path, cluster_db=False):
        if cluster_db:
            cluster_db_cmd = "OVN_DB_CLUSTER=yes"
        else:
            cluster_db_cmd = "OVN_DB_CLUSTER=no"
        cmd = "cd {} && CHASSIS_COUNT=0 GW_COUNT=0 OVN_BR_CLEANUP=no {} ./ovn_cluster.sh stop".format(
            ovn_fake_path, cluster_db_cmd
        )
        ssh_conn.run(cmd)

    def _add_chassis_localnet(self, ssh_conn, physnet):
        cmd = "ovs-vsctl -- set open_vswitch . external-ids:ovn-bridge-mappings={}:br-ex".format(
            physnet
        )
        ssh_conn.run(cmd)

    @scenario.configure(context={})
    @atomic.action_timer("OvnFakeMultinode.add_central_node")
    def add_central_node(self, fake_multinode_args = {}):
        ssh = self.controller_client("ovs-ssh")
        ssh.set_sandbox("controller-sandbox", self.install_method)
        ssh.enable_batch_mode(False)

        node_net = fake_multinode_args.get("node_net")
        node_net_len = fake_multinode_args.get("node_net_len")
        node_ip = fake_multinode_args.get("node_ip")
        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")
        monitor_all = fake_multinode_args.get("ovn_monitor_all")
        cluster_db = fake_multinode_args.get("ovn_cluster_db")

        self._add_central(ssh, node_net, node_net_len, node_ip, ovn_fake_path,
                          monitor_all, cluster_db)

    @scenario.configure(context={})
    @atomic.action_timer("OvnFakeMultinode.add_chassis_node")
    def add_chassis_node(self, fake_multinode_args = {}):
        farm = fake_multinode_args.get("farm")
        sb = self._get_sandbox(farm)
        ssh = self._get_sandbox_conn(sb["name"], sb)

        node_net = fake_multinode_args.get("node_net")
        node_net_len = fake_multinode_args.get("node_net_len")
        node_ip = fake_multinode_args.get("node_ip")
        node_name = sb["host_container"]
        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")
        monitor_all = fake_multinode_args.get("ovn_monitor_all")
        cluster_db = fake_multinode_args.get("ovn_cluster_db")

        self._add_chassis(ssh, node_net, node_net_len, node_ip, node_name,
                          ovn_fake_path, monitor_all, cluster_db)

    @scenario.configure(context={})
    @atomic.action_timer("OvnFakeMultinode.connect_chassis_node")
    def connect_chassis_node(self, fake_multinode_args = {}):
        farm = fake_multinode_args.get("farm")
        sb = self._get_sandbox(farm)
        ssh = self._get_sandbox_conn(sb["name"], sb)

        central_ip = fake_multinode_args.get("central_ip")
        sb_proto = fake_multinode_args.get("sb_proto", "ssl")
        node_name = sb["host_container"]
        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")
        self._connect_chassis(ssh, node_name, central_ip, sb_proto,
                              ovn_fake_path)

    @scenario.configure(context={})
    @atomic.action_timer("ovnFakeMultinode.wait_chassis_node")
    def wait_chassis_node(self, fake_multinode_args = {}):
        farm = fake_multinode_args.get("farm")
        max_timeout_s = fake_multinode_args.get("max_timeout_s", 60)
        sb = self._get_sandbox(farm)
        node_name = sb["host_container"]

        ovn_sbctl = self.controller_client("ovn-sbctl")
        ovn_sbctl.set_sandbox("controller-sandbox", self.install_method,
                              self.context['controller']['host_container'])
        ovn_sbctl.enable_batch_mode(False)
        self._wait_chassis(ovn_sbctl, node_name, max_timeout_s)

    @scenario.configure(context={})
    @atomic.action_timer("OvnFakeMultinode.del_chassis_node")
    def del_chassis_node(self, fake_multinode_args = {}):
        farm = fake_multinode_args.get("farm")
        sb = self._get_sandbox(farm)
        ssh = self._get_sandbox_conn(sb["name"], sb)

        node_name = sb["host_container"]
        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")
        self._del_chassis(ssh, node_name, ovn_fake_path)

    @scenario.configure(context={})
    @atomic.action_timer("OvnFakeMultinode.del_central_node")
    def del_central_node(self, fake_multinode_args = {}):
        ssh = self.controller_client("ovs-ssh")
        ssh.set_sandbox("controller-sandbox", self.install_method)
        ssh.enable_batch_mode(False)

        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")
        cluster_db = fake_multinode_args.get("ovn_cluster_db")
        self._del_central(ssh, ovn_fake_path, cluster_db)

    @scenario.configure(context={})
    @atomic.action_timer("OvnFakeMultinode.add_chassis_node_localnet")
    def add_chassis_node_localnet(self, fake_multinode_args = {}):
        farm = fake_multinode_args.get("farm")
        sb = self._get_sandbox(farm)
        ssh = self._get_sandbox_conn(sb["name"], sb, sb["host_container"])

        physnet = fake_multinode_args.get("physnet", "providernet")
        self._add_chassis_localnet(ssh, physnet)

    @scenario.configure(context={})
    @atomic.action_timer("OvnFakeMultinode.add_chassis_nodes")
    def add_chassis_nodes(self, fake_multinode_args = {}):
        iteration = self.context["iteration"]
        batch_size = fake_multinode_args.get("batch_size", 1)
        node_prefix = fake_multinode_args.get("node_prefix", "")

        node_net = fake_multinode_args.get("node_net")
        node_net_len = fake_multinode_args.get("node_net_len")
        node_cidr = netaddr.IPNetwork("{}/{}".format(node_net, node_net_len))

        monitor_all = fake_multinode_args.get("ovn_monitor_all")
        cluster_db = fake_multinode_args.get("ovn_cluster_db")
        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")

        for i in range(batch_size):
            index = iteration * batch_size + i
            node_ip = str(node_cidr.ip + index + 1)

            farm = "{}{}".format(node_prefix, index % len(self._sandboxes))
            sb = self._get_sandbox(farm)
            ssh = self._get_sandbox_conn(sb["name"], sb)
            node_name = sb["host_container"]

            self._add_chassis(ssh, node_net, node_net_len, node_ip, node_name,
                              ovn_fake_path, monitor_all, cluster_db)

    @scenario.configure(context={})
    @atomic.action_timer("OvnFakeMultinode.connect_chassis_nodes")
    def connect_chassis_nodes(self, fake_multinode_args = {}):
        iteration = self.context["iteration"]
        batch_size = fake_multinode_args.get("batch_size", 1)
        node_prefix = fake_multinode_args.get("node_prefix", "")

        central_ip = fake_multinode_args.get("central_ip")
        sb_proto = fake_multinode_args.get("sb_proto", "ssl")
        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")

        for i in range(batch_size):
            index = iteration * batch_size + i

            farm = "{}{}".format(node_prefix, index % len(self._sandboxes))
            sb = self._get_sandbox(farm)
            ssh = self._get_sandbox_conn(sb["name"], sb)
            node_name = sb["host_container"]

            self._connect_chassis(ssh, node_name, central_ip, sb_proto,
                                  ovn_fake_path)

    @scenario.configure(context={})
    @atomic.action_timer("ovnFakeMultinode.wait_chassis_nodes")
    def wait_chassis_nodes(self, fake_multinode_args = {}):
        iteration = self.context["iteration"]
        batch_size = fake_multinode_args.get("batch_size", 1)
        node_prefix = fake_multinode_args.get("node_prefix", "")
        max_timeout_s = fake_multinode_args.get("max_timeout_s")

        ovn_sbctl = self.controller_client("ovn-sbctl")
        ovn_sbctl.set_sandbox("controller-sandbox", self.install_method,
                              self.context['controller']['host_container'])
        ovn_sbctl.enable_batch_mode(False)
        for i in range(batch_size):
            index = iteration * batch_size + i

            farm = "{}{}".format(node_prefix, index % len(self._sandboxes))
            sb = self._get_sandbox(farm)
            ssh = self._get_sandbox_conn(sb["name"], sb)
            node_name = sb["host_container"]

            self._wait_chassis(ovn_sbctl, node_name, max_timeout_s)

    @scenario.configure(context={})
    @atomic.action_timer("OvnFakeMultinode.del_chassis_nodes")
    def del_chassis_nodes(self, fake_multinode_args = {}):
        iteration = self.context["iteration"]
        batch_size = fake_multinode_args.get("batch_size", 1)
        node_prefix = fake_multinode_args.get("node_prefix", "")

        for i in range(batch_size):
            index = iteration * batch_size + i

            farm = "{}{}".format(node_prefix, index % len(self._sandboxes))
            sb = self._get_sandbox(farm)
            ssh = self._get_sandbox_conn(sb["name"], sb)

            ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")
            node_name = sb["host_container"]

            self._del_chassis(ssh, node_name, ovn_fake_path)

    @scenario.configure(context={})
    @atomic.action_timer("OvnFakeMultinode.add_chassis_nodes_localnet")
    def add_chassis_nodes_localnet(self, fake_multinode_args = {}):
        iteration = self.context["iteration"]
        batch_size = fake_multinode_args.get("batch_size", 1)
        node_prefix = fake_multinode_args.get("node_prefix", "")
        physnet = fake_multinode_args.get("physnet", "providernet")

        for i in range(batch_size):
            index = iteration * batch_size + i

            farm = "{}{}".format(node_prefix, index % len(self._sandboxes))
            sb = self._get_sandbox(farm)
            ssh = self._get_sandbox_conn(sb["name"], sb, sb["host_container"])

            self._add_chassis_localnet(ssh, physnet)


class OvnNorthboundFakeMultinode(OvnFakeMultinode):

    def __init__(self, context):
        super(OvnNorthboundFakeMultinode, self).__init__(context)

    @scenario.configure(context={})
    def setup_switch_per_node(self, fake_multinode_args = {},
                              lswitch_create_args = {},
                              lnetwork_create_args = {},
                              lport_create_args = {},
                              port_bind_args = {},
                              create_mgmt_port = True):
        self.add_chassis_nodes(fake_multinode_args)
        self.connect_chassis_nodes(fake_multinode_args)
        self.wait_chassis_nodes(fake_multinode_args)

        if lnetwork_create_args.get('gw_router_per_network', False):
            self.add_chassis_nodes_localnet(fake_multinode_args)

        lswitch_create_args['amount'] = fake_multinode_args.get('batch_size', 1)
        lswitch_create_args['batch'] = 1
        self._create_routed_network(lswitch_create_args=lswitch_create_args,
                                    lnetwork_create_args=lnetwork_create_args,
                                    lport_create_args=lport_create_args,
                                    port_bind_args=port_bind_args,
                                    create_mgmt_port=create_mgmt_port)

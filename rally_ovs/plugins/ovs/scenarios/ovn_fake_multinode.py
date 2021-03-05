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

ovn-fake-multinode scenario configuration options:
- node_net: fake node underlay subnet.
- node_net_len: fake node underlay subnet mask length.
- node_ip: fake node underlay IP (must be in the subnet defined above).
- node_prefix: fake node prefix from which IPs are generated if batching
  is enabled.
- batch_size: number of fake nodes to provision in a single iteration.
- central_ip: SB remote to which chassis nodes connect to.
- sb_proto: protocol to be used by chassis nodes when connecting to SB.
- cluster_cmd_path: path to ovn-fake-multinode utilities.
- ovn_monitor_all: set to true to disable conditional monitoring or not between
  fake nodes and the Southbound.
- ovn_cluster_db: set to true to enable RAFT clustering for NB/SB databases.
- ovn_dp_type: controls the type of OVS datapath to be used.  Possible values
  are 'system' (for the kernel datapath), 'netdev' (for the userspace
  datapath).
  See 'datapath_type' in:
  https://man7.org/linux/man-pages/man5/ovs-vswitchd.conf.db.5.html#Bridge_TABLE
- max_timeout_s: maximum time to wait for a new chassis to register itself in
  the SB.
- gw_router_per_network: set to true for testing external connectivity through
  a gateway router provisioned for each fake node.
- physnet: Name of the provider bridge when testing external connectivity.
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
        ssh.set_log_cmd(self.context.get("log_cmd", False))
        ssh.enable_batch_mode(False)
        return ssh

    def _add_central(self, ssh_conn, node_net, node_net_len, node_ip,
                     ovn_fake_path, monitor_all=False, cluster_db=False,
                     dp_type="system"):
        if monitor_all:
            monitor_cmd = "OVN_MONITOR_ALL=yes"
        else:
            monitor_cmd = "OVN_MONITOR_ALL=no"

        if cluster_db:
            cluster_db_cmd = "OVN_DB_CLUSTER=yes"
        else:
            cluster_db_cmd = "OVN_DB_CLUSTER=no"

        dp_type_cmd = "OVN_DP_TYPE={}".format(dp_type)

        cmd = "cd {} && CHASSIS_COUNT=0 GW_COUNT=0 IP_HOST={} IP_CIDR={} IP_START={} {} {} {} CREATE_FAKE_VMS=no ./ovn_cluster.sh start".format(
            ovn_fake_path, node_net, node_net_len, node_ip, monitor_cmd,
            cluster_db_cmd, dp_type_cmd
        )
        ssh_conn.run(cmd)

        time.sleep(5)

    def _add_chassis(self, ssh_conn, node_net, node_net_len, node_ip, node_name,
                     ovn_fake_path, monitor_all=False, cluster_db=False,
                     dp_type="system"):
        invalid_remote = "tcp:0.0.0.1:6642"
        if monitor_all:
            monitor_cmd = "OVN_MONITOR_ALL=yes"
        else:
            monitor_cmd = "OVN_MONITOR_ALL=no"

        if cluster_db:
            cluster_db_cmd = "OVN_DB_CLUSTER=yes"
        else:
            cluster_db_cmd = "OVN_DB_CLUSTER=no"
        
        dp_type_cmd = "OVN_DP_TYPE={}".format(dp_type)

        cmd = "cd {} && IP_HOST={} IP_CIDR={} IP_START={} {} {} {} ./ovn_cluster.sh add-chassis {} {}".format(
            ovn_fake_path, node_net, node_net_len, node_ip, monitor_cmd,
            cluster_db_cmd, dp_type_cmd, node_name, invalid_remote
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

    def _add_chassis_external_host(self, ssh_conn, ext_host_cidr):
        gw_ip = self._get_gw_ip(ext_host_cidr, 1)
        host_ip = self._get_gw_ip(ext_host_cidr, 2)

        ssh_conn.enable_batch_mode()
        ssh_conn.run("ip link add veth0 type veth peer name veth1")
        ssh_conn.run("ip netns add ext-ns")
        ssh_conn.run("ip link set netns ext-ns dev veth0")
        ssh_conn.run("ip netns exec ext-ns ip link set dev veth0 up")
        ssh_conn.run("ip netns exec ext-ns ip addr add {}/{} dev veth0".format(
                host_ip, ext_host_cidr.prefixlen))
        ssh_conn.run("ip netns exec ext-ns ip route add default via {}".format(
                gw_ip))
        ssh_conn.run("ip link set dev veth1 up")
        ssh_conn.run("ovs-vsctl add-port br-ex veth1")

        ssh_conn.flush()
        ssh_conn.enable_batch_mode(False)

    @scenario.configure(context={})
    @atomic.action_timer("OvnFakeMultinode.add_central_node")
    def add_central_node(self, fake_multinode_args = {}):
        ssh = self.controller_client("ovs-ssh")
        ssh.set_sandbox("controller-sandbox", self.install_method)
        ssh.set_log_cmd(self.context.get("log_cmd", False))
        ssh.enable_batch_mode(False)

        node_net = fake_multinode_args.get("node_net")
        node_net_len = fake_multinode_args.get("node_net_len")
        node_ip = fake_multinode_args.get("node_ip")
        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")
        monitor_all = fake_multinode_args.get("ovn_monitor_all")
        cluster_db = fake_multinode_args.get("ovn_cluster_db")
        dp_type = fake_multinode_args.get("ovn_dp_type")

        self._add_central(ssh, node_net, node_net_len, node_ip, ovn_fake_path,
                          monitor_all, cluster_db, dp_type)

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
        dp_type = fake_multinode_args.get("ovn_dp_type")

        self._add_chassis(ssh, node_net, node_net_len, node_ip, node_name,
                          ovn_fake_path, monitor_all, cluster_db, dp_type)

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
        ovn_sbctl.set_log_cmd(self.context.get("log_cmd", False))
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
        ssh.set_log_cmd(self.context.get("log_cmd", False))
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
        dp_type = fake_multinode_args.get("ovn_dp_type")

        for i in range(batch_size):
            index = iteration * batch_size + i
            node_ip = str(node_cidr.ip + index + 1)

            farm = "{}{}".format(node_prefix, index % len(self._sandboxes))
            sb = self._get_sandbox(farm)
            ssh = self._get_sandbox_conn(sb["name"], sb)
            node_name = sb["host_container"]

            self._add_chassis(ssh, node_net, node_net_len, node_ip, node_name,
                              ovn_fake_path, monitor_all, cluster_db, dp_type)

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
        ovn_sbctl.set_log_cmd(self.context.get("log_cmd", False))
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

    @scenario.configure(context={})
    @atomic.action_timer("OvnFakeMultinode.add_chassis_external_hosts")
    def add_chassis_external_hosts(self, fake_multinode_args = {},
                                   lnetwork_create_args = {}):
        iteration = self.context["iteration"]
        batch_size = fake_multinode_args.get("batch_size", 1)
        node_prefix = fake_multinode_args.get("node_prefix", "")

        for i in range(batch_size):
            index = iteration * batch_size + i

            farm = "{}{}".format(node_prefix, index % len(self._sandboxes))
            sb = self._get_sandbox(farm)
            ssh = self._get_sandbox_conn(sb["name"], sb, sb["host_container"])
            ext_host_cidr = netaddr.IPNetwork(lnetwork_create_args.get('start_ext_cidr'))

            self._add_chassis_external_host(ssh, ext_host_cidr.next(index))


class OvnNorthboundFakeMultinode(OvnFakeMultinode):

    def __init__(self, context):
        super(OvnNorthboundFakeMultinode, self).__init__(context)

    @scenario.configure(context={})
    def setup_switch_per_node_init(self, fake_multinode_args = {},
                                   lnetwork_create_args = {}):
        self.add_chassis_nodes(fake_multinode_args)
        if lnetwork_create_args.get('gw_router_per_network', False):
            self.add_chassis_nodes_localnet(fake_multinode_args)
            self.add_chassis_external_hosts(fake_multinode_args,
                                            lnetwork_create_args)

    @scenario.configure(context={})
    def setup_switch_per_node(self, fake_multinode_args = {},
                              lswitch_create_args = {},
                              lnetwork_create_args = {},
                              lport_create_args = {},
                              port_bind_args = {},
                              create_mgmt_port = True):
        # TODO: figure out how to not reload the context?
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        lswitches = ovn_nbctl.show()
        self.context["ovn-nb-lbs"] = ovn_nbctl.lb_list()

        self.connect_chassis_nodes(fake_multinode_args)
        self.wait_chassis_nodes(fake_multinode_args)

        lswitch_create_args['amount'] = fake_multinode_args.get('batch_size', 1)
        lswitch_create_args['batch'] = 1
        self._create_routed_network(lswitch_create_args=lswitch_create_args,
                                    lnetwork_create_args=lnetwork_create_args,
                                    lport_create_args=lport_create_args,
                                    port_bind_args=port_bind_args,
                                    create_mgmt_port=create_mgmt_port)

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

    def _get_sandbox_conn(self, sb_name, sb):
        farm = sb["farm"]
        ssh = self.farm_clients(farm, "ovs-ssh")
        ssh.set_sandbox(sb_name, self.install_method)
        ssh.enable_batch_mode(False)
        return ssh

    @atomic.action_timer("OvnFakeMultinode.add_central_node")
    def _add_central(self, ssh_conn, node_net, node_net_len, node_ip,
                     ovn_fake_path):
        cmd = "cd {} && CHASSIS_COUNT=0 GW_COUNT=0 IP_HOST={} IP_CIDR={} IP_START={} ./ovn_cluster.sh start || true".format(
            ovn_fake_path, node_net, node_net_len, node_ip
        )
        ssh_conn.run(cmd)

    @atomic.action_timer("OvnFakeMultinode.add_chassis_node")
    def _add_chassis(self, ssh_conn, node_net, node_net_len, node_ip, node_name,
                     ovn_fake_path):
        invalid_remote = "tcp:0.0.0.1:6642"
        cmd = "cd {} && IP_HOST={} IP_CIDR={} IP_START={} ./ovn_cluster.sh add-chassis {} {} || true".format(
            ovn_fake_path, node_net, node_net_len, node_ip, node_name, invalid_remote
        )
        ssh_conn.run(cmd)

    @atomic.action_timer("OvnFakeMultinode.connect_chassis_node")
    def _connect_chassis(self, ssh_conn, node_name, central_ip, ovn_fake_path):
        cmd = "cd {} && ./ovn_cluster.sh set-chassis-ovn-remote {} tcp:{}:6642 || true".format(
            ovn_fake_path, node_name, central_ip
        )
        ssh_conn.run(cmd)

    @atomic.action_timer("ovnFakeMultinode.wait_chassis_node")
    def _wait_chassis(self, sbctl_conn, chassis_name, max_timeout_s):
        for i in range(0, max_timeout_s * 10):
            if sbctl_conn.chassis_bound(chassis_name):
                break
            time.sleep(0.1)

    @atomic.action_timer("OvnFakeMultinode.del_chassis_node")
    def _del_chassis(self, ssh_conn, node_name, ovn_fake_path):
        cmd = "cd {} && ./ovn_cluster.sh stop-chassis {} || true".format(
            ovn_fake_path, node_name
        )
        ssh_conn.run(cmd)

    @atomic.action_timer("OvnFakeMultinode.del_central_node")
    def _del_central(self, ssh_conn, ovn_fake_path):
        cmd = "cd {} && CHASSIS_COUNT=0 GW_COUNT=0 ./ovn_cluster.sh stop || true".format(
            ovn_fake_path
        )
        ssh_conn.run(cmd)

    @scenario.configure(context={})
    def add_central_node(self, fake_multinode_args = {}):
        ssh = self.controller_client("ovs-ssh")
        ssh.set_sandbox("controller-sandbox", self.install_method)
        ssh.enable_batch_mode(False)

        node_net = fake_multinode_args.get("node_net")
        node_net_len = fake_multinode_args.get("node_net_len")
        node_ip = fake_multinode_args.get("node_ip")
        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")

        self._add_central(ssh, node_net, node_net_len, node_ip, ovn_fake_path)

    @scenario.configure(context={})
    def add_chassis_node(self, fake_multinode_args = {}):
        farm = fake_multinode_args.get("farm")
        sb = self._get_sandbox(farm)
        ssh = self._get_sandbox_conn(sb["name"], sb)

        node_net = fake_multinode_args.get("node_net")
        node_net_len = fake_multinode_args.get("node_net_len")
        node_ip = fake_multinode_args.get("node_ip")
        node_name = sb["host_container"]
        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")
        self._add_chassis(ssh, node_net, node_net_len, node_ip, node_name,
                          ovn_fake_path)

    @scenario.configure(context={})
    def connect_chassis_node(self, fake_multinode_args = {}):
        farm = fake_multinode_args.get("farm")
        sb = self._get_sandbox(farm)
        ssh = self._get_sandbox_conn(sb["name"], sb)

        central_ip = fake_multinode_args.get("central_ip")
        node_name = sb["host_container"]
        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")
        self._connect_chassis(ssh, node_name, central_ip, ovn_fake_path)

    @scenario.configure(context={})
    def wait_chassis_node(self, fake_multinode_args = {}):
        farm = fake_multinode_args.get("farm")
        max_timeout_s = fake_multinode_args.get("max_timeout_s")
        sb = self._get_sandbox(farm)
        node_name = sb["host_container"]

        ovn_sbctl = self.controller_client("ovn-sbctl")
        ovn_sbctl.set_sandbox("controller-sandbox", self.install_method,
                              self.context['controller']['host_container'])
        ovn_sbctl.enable_batch_mode(False)
        self._wait_chassis(ovn_sbctl, node_name, max_timeout_s)

    @scenario.configure(context={})
    def del_chassis_node(self, fake_multinode_args = {}):
        farm = fake_multinode_args.get("farm")
        sb = self._get_sandbox(farm)
        ssh = self._get_sandbox_conn(sb["name"], sb)

        node_name = sb["host_container"]
        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")
        self._del_chassis(ssh, node_name, ovn_fake_path)

    @scenario.configure(context={})
    def del_central_node(self, fake_multinode_args = {}):
        ssh = self.controller_client("ovs-ssh")
        ssh.set_sandbox("controller-sandbox", self.install_method)
        ssh.enable_batch_mode(False)

        ovn_fake_path = fake_multinode_args.get("cluster_cmd_path")
        self._del_central(ssh, ovn_fake_path)

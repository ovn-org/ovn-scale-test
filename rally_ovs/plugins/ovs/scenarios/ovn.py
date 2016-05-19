# Copyright 2016 Ebay Inc.
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

from rally_ovs.plugins.ovs import scenario
from rally.task import atomic
from rally.common import logging
from rally import exceptions
from rally_ovs.plugins.ovs.utils import get_random_sandbox
from rally_ovs.plugins.ovs import utils
import netaddr

LOG = logging.getLogger(__name__)



class OvnScenario(scenario.OvsScenario):


    RESOURCE_NAME_FORMAT = "lswitch_XXXXXX_XXXXXX"


    '''
    return: [{"name": "lswitch_xxxx_xxxxx", "cidr": netaddr.IPNetwork}, ...]
    '''
    @atomic.action_timer("ovn.create_lswitch")
    def _create_lswitches(self, lswitch_create_args):

        print("create lswitch")
        self.RESOURCE_NAME_FORMAT = "lswitch_XXXXXX_XXXXXX"

        amount = lswitch_create_args.get("amount", 1)
        batch = lswitch_create_args.get("batch", amount)
        start_cidr = lswitch_create_args.get("start_cidr", "")
        if start_cidr:
            start_cidr = netaddr.IPNetwork(start_cidr)

        LOG.info("Create lswitches method: %s" % self.install_method)
        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox", self.install_method)
        ovn_nbctl.enable_batch_mode()

        flush_count = batch
        lswitches = []
        for i in range(amount):
            name = self.generate_random_name()

            lswitch = ovn_nbctl.lswitch_add(name)
            if start_cidr:
                lswitch["cidr"] = start_cidr.next(i)

            LOG.info("create %(name)s %(cidr)s" % \
                      {"name": name, "cidr":lswitch["cidr"]})
            lswitches.append(lswitch)

            flush_count -= 1
            if flush_count < 1:
                ovn_nbctl.flush()
                flush_count = batch

        ovn_nbctl.flush() # ensure all commands be run
        ovn_nbctl.enable_batch_mode(False)
        return lswitches


    @atomic.optional_action_timer("ovn.list_lswitch")
    def _list_lswitches(self):
        print("list lswitch")
        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox")
        ovn_nbctl.enable_batch_mode(False)
        ovn_nbctl.lswitch_list()

    @atomic.action_timer("ovn.delete_lswitch")
    def _delete_lswitch(self, lswitches):
        print("delete lswitch")
        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox")
        ovn_nbctl.enable_batch_mode()
        for lswitch in lswitches:
            ovn_nbctl.lswitch_del(lswitch["name"])

        ovn_nbctl.flush()


    def _get_or_create_lswitch(self, lswitch_create_args=None):
        pass

    @atomic.action_timer("ovn.create_lport")
    def _create_lports(self, lswitch, lport_create_args = [], lport_amount=1):
        LOG.info("create %d lports on lswitch %s" % \
                            (lport_amount, lswitch["name"]))

        self.RESOURCE_NAME_FORMAT = "lport_XXXXXX_XXXXXX"

        batch = lport_create_args.get("batch", lport_amount)

        LOG.info("Create lports method: %s" % self.install_method)
        install_method = self.install_method

        network_cidr = lswitch.get("cidr", None)
        ip_addrs = None
        if network_cidr:
            end_ip = network_cidr.ip + lport_amount
            if not end_ip in network_cidr:
                message = _("Network %s's size is not big enough for %d lports.")
                raise exceptions.InvalidConfigException(
                            message  % (network_cidr, lport_amount))

            ip_addrs = netaddr.iter_iprange(network_cidr.ip, network_cidr.last)

        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox", install_method)
        ovn_nbctl.enable_batch_mode()

        base_mac = [i[:2] for i in self.task["uuid"].split('-')]
        base_mac[3:] = ['00']*3


        flush_count = batch
        lports = []
        for i in range(lport_amount):
            name = self.generate_random_name()
            lport = ovn_nbctl.lport_add(lswitch["name"], name)

            ip = str(ip_addrs.next()) if ip_addrs else ""
            mac = utils.get_random_mac(base_mac)

            ovn_nbctl.lport_set_addresses(name, [mac, ip])
            ovn_nbctl.lport_set_port_security(name, mac)

            lports.append(lport)

            flush_count -= 1
            if flush_count < 1:
                ovn_nbctl.flush()
                flush_count = batch

        ovn_nbctl.flush()  # ensure all commands be run
        ovn_nbctl.enable_batch_mode(False)
        return lports


    @atomic.action_timer("ovn.delete_lport")
    def _delete_lport(self, lports):
        print("delete lport")
        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox")
        ovn_nbctl.enable_batch_mode()
        for lport in lports:
            ovn_nbctl.lport_del(lport["name"])

        ovn_nbctl.flush()


    @atomic.action_timer("ovn.action_timer")
    def _list_lports(self, lswitches, install_method = "sandbox"):
        print("list lports")
        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox", install_method)
        ovn_nbctl.enable_batch_mode(False)
        for lswitch in lswitches:
            LOG.info("list lports on lswitch %s" % lswitch["name"])
            ovn_nbctl.lport_list(lswitch["name"])



    @atomic.action_timer("ovn.create_acl")
    def _create_acl(self, lswitch, lports, acl_create_args, acls_per_port):
        sw = lswitch["name"]
        LOG.info("create %d ACLs on lswitch %s" % (acls_per_port, sw))

        direction = acl_create_args.get("direction", "to-lport")
        priority = acl_create_args.get("priority", 1000)
        action = acl_create_args.get("action", "allow")

        if direction == "from-lport":
            p = "inport"
        else:
            p = "outport"

        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox")
        ovn_nbctl.enable_batch_mode()
        for lport in lports:
            for i in range(acls_per_port):
                match = '%s == "%s" && ip4 && udp && udp.src == %d' % \
                        (p, lport["name"], 100 + i)
                ovn_nbctl.acl_add(sw, direction, priority, match, action)

            ovn_nbctl.flush()


    @atomic.action_timer("ovn.list_acl")
    def _list_acl(self, lswitches):
        LOG.info("list ACLs")
        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox")
        ovn_nbctl.enable_batch_mode(False)
        for lswitch in lswitches:
            LOG.info("list ACLs on lswitch %s" % lswitch["name"])
            ovn_nbctl.acl_list(lswitch["name"])


    @atomic.action_timer("ovn.delete_acl")
    def _delete_acl(self, lswitches):
        LOG.info("delete ACLs")

        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox")
        ovn_nbctl.enable_batch_mode(True)
        for lswitch in lswitches:
            LOG.info("delete ACLs on lswitch %s" % lswitch["name"])
            ovn_nbctl.acl_del(lswitch["name"])

        ovn_nbctl.flush()



    @atomic.action_timer("ovn_network.create_network")
    def _create_networks(self, network_create_args):
        physnet = network_create_args.get("physical_network", None)
        lswitches = self._create_lswitches(network_create_args)

        LOG.info("Create network method: %s" % self.install_method)
        if physnet != None:
            ovn_nbctl = self.controller_client("ovn-nbctl")
            ovn_nbctl.set_sandbox("controller-sandbox", self.install_method)
            ovn_nbctl.enable_batch_mode()

            for lswitch in lswitches:
                network = lswitch["name"]
                port = "provnet-%s" % network
                ovn_nbctl.lport_add(network, port)
                ovn_nbctl.lport_set_addresses(port, ["unknown"])
                ovn_nbctl.lport_set_type(port, "localnet")
                ovn_nbctl.lport_set_options(port, "network_name=%s" % physnet)

            ovn_nbctl.flush()

        return lswitches



    @atomic.action_timer("ovn_network.bind_port")
    def _bind_ports(self, lports, sandboxes, port_bind_args):
        port_bind_args = port_bind_args or {}
        wait_up = port_bind_args.get("wait_up", False)

        sandbox_num = len(sandboxes)
        lport_num = len(lports)
        lport_per_sandbox = (lport_num + sandbox_num - 1) / sandbox_num

        LOG.info("Bind lports method: %s" % self.install_method)
        install_method = self.install_method

        j = 0
        for i in range(0, len(lports), lport_per_sandbox):
            lport_slice = lports[i:i+lport_per_sandbox]

            sandbox = sandboxes[j]["name"]
            farm = sandboxes[j]["farm"]
            ovs_vsctl = self.farm_clients(farm, "ovs-vsctl")
            ovs_vsctl.set_sandbox(sandbox, install_method)
            ovs_vsctl.enable_batch_mode()
            for lport in lport_slice:
                port_name = lport["name"]

                LOG.info("bind %s to %s on %s" % (port_name, sandbox, farm))

                ovs_vsctl.add_port('br-int', port_name)
                ovs_vsctl.db_set('Interface', port_name,
                                 ('external_ids', {"iface-id":port_name,
                                                   "iface-status":"active"}),
                                 ('admin_state', 'up'))
            ovs_vsctl.flush()
            j += 1

        if wait_up:
            self._wait_up_port(lports, install_method)


    @atomic.action_timer("ovn_network.wait_port_up")
    def _wait_up_port(self, lports, install_method):
        LOG.info("wait port up" )
        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox", install_method)
        ovn_nbctl.enable_batch_mode(True)

        for lport in lports:
            ovn_nbctl.wait_until('Logical_Port', lport["name"], ('up', 'true'))

        ovn_nbctl.flush()







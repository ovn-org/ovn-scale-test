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

import netaddr
import random
import re
import copy

from rally_ovs.plugins.ovs.scenarios import ovn

from rally.task import scenario
from rally.task import atomic
from rally.task import validation

class OvnNorthbound(ovn.OvnScenario):
    """Benchmark scenarios for OVN northbound."""

    @scenario.configure()
    def create_routed_network(self, lswitch_create_args = None,
                              networks_per_router = None,
                              lport_create_args = None,
                              port_bind_args = None,
                              create_mgmt_port = True):
        lrouters = self.context["datapaths"]["routers"]
        iteration = self.context["iteration"]
        sandboxes = self.context["sandboxes"]

        lswitch_args = copy.copy(lswitch_create_args)
        start_cidr = lswitch_create_args.get("start_cidr", "")
        if start_cidr:
            start_cidr = netaddr.IPNetwork(start_cidr)
            cidr = start_cidr.next(iteration)
            lswitch_args["start_cidr"] = str(cidr)
        lswitches = self._create_lswitches(lswitch_args)

        if networks_per_router:
            self._connect_networks_to_routers(lswitches, lrouters,
                                              networks_per_router)

        if create_mgmt_port == False:
            return

        sandbox = sandboxes[iteration % len(sandboxes)]
        lport = self._create_lports(lswitches[0], lport_create_args)
        self._bind_ports_and_wait(lport, [sandbox], port_bind_args)

    @atomic.action_timer("ovn.create_or_update_address_set")
    def create_or_update_address_set(self, name, ipaddr, create = True):
        if (create):
            self._create_address_set(name, ipaddr)
        else:
            self._address_set_add_addrs(name, ipaddr)

    @atomic.action_timer("ovn.create_port_acls")
    def create_port_acls(self, lswitch, lports, addr_set):
        """
        create two acl for each logical port
        prio 1000: allow inter project traffic
        prio 900: deny all
        """
        match = "%(direction)s == \"%(lport)s\" && ip4.dst == %(address_set)s"
        acl_create_args = { "match" : match, "address_set" : addr_set }
        self._create_acl(lswitch, lports, acl_create_args, 1,
                         atomic_action = False)
        acl_create_args = { "priority" : 900, "action" : "drop", "match" : "%(direction)s == \"%(lport)s\" && ip4" }
        self._create_acl(lswitch, lports, acl_create_args, 1,
                         atomic_action = False)

    def create_lport_acl_addrset(self, lswitch, lport_create_args, port_bind_args,
                                 ip_start_index = 0, addr_set_index = 0,
                                 create_addr_set = True, create_acls = True):
        lports = self._create_lports(lswitch, lport_create_args,
                                     lport_ip_shift = ip_start_index)

        if create_acls:
            network_cidr = lswitch.get("cidr", None)
            if network_cidr:
                ip_list = netaddr.IPNetwork(network_cidr.ip + ip_start_index).iter_hosts()
                ipaddr = str(next(ip_list))
            else:
                ipaddr = ""
            self.create_or_update_address_set("addrset%d" % addr_set_index,
                                              ipaddr, create_addr_set)

            self.create_port_acls(lswitch, lports,
                                  "$addrset%d" % addr_set_index)

        sandboxes = self.context["sandboxes"]
        sandbox = sandboxes[self.context["iteration"] % len(sandboxes)]
        self._bind_ports_and_wait(lports, [sandbox], port_bind_args)

    @scenario.configure()
    def create_routed_lport(self, lport_create_args = None,
                            port_bind_args = None,
                            create_acls = True,
                            address_set_size = 1):
        lswitches = self.context["ovn-nb"]
        ip_offset = lport_create_args.get("ip_offset", 1) if lport_create_args else 1
        address_set_size = 1 if address_set_size == 0 else address_set_size

        iteration = self.context["iteration"]
        lswitch = lswitches[iteration % len(lswitches)]
        addr_set_index = iteration / address_set_size
        ip_start_index = iteration / len(lswitches) + ip_offset

        self.create_lport_acl_addrset(lswitch, lport_create_args,
                                      port_bind_args, ip_start_index,
                                      addr_set_index,
                                      (iteration % address_set_size) == 0,
                                      create_acls)

    @scenario.configure(context={})
    def cleanup_routed_lswitches(self):
        sandboxes = self.context.get("sandboxes", [])
        for sandbox in sandboxes:
            self._flush_ovs_internal_ports(sandbox)
        lswitches = self.context.get("ovn-nb", [])
        self._delete_lswitch(lswitches)
        self._delete_routers()
        for address_set in self._list_address_set():
            self._remove_address_set(address_set)

    @scenario.configure(context={})
    def create_and_list_lswitches(self, lswitch_create_args=None):
        self._create_lswitches(lswitch_create_args)
        self._list_lswitches()


    @scenario.configure(context={})
    def create_and_delete_lswitches(self, lswitch_create_args=None):
        lswitches = self._create_lswitches(lswitch_create_args or {})
        self._delete_lswitch(lswitches)


    @scenario.configure(context={})
    def cleanup_lswitches(self, lswitch_cleanup_args=None):
        lswitch_cleanup_args = lswitch_cleanup_args or {}
        prefix = lswitch_cleanup_args.get("prefix", "")

        lswitches = self.context.get("ovn-nb", [])
        matched_lswitches = []
        for lswitch in lswitches:
            if lswitch["name"].find(prefix) == 0:
                matched_lswitches.append(lswitch)

        self._delete_lswitch(matched_lswitches)


    @validation.number("lports_per_lswitch", minval=1, integer_only=True)
    @scenario.configure(context={})
    def create_and_list_lports(self,
                              lswitch_create_args=None,
                              lport_create_args=None,
                              lports_per_lswitch=None):

        lswitches = self._create_lswitches(lswitch_create_args)

        for lswitch in lswitches:
            self._create_lports(lswitch, lport_create_args, lports_per_lswitch)

        self._list_lports(lswitches)


    @scenario.configure(context={})
    def create_and_delete_lports(self,
                              lswitch_create_args=None,
                              lport_create_args=None,
                              lports_per_lswitch=None):

        lswitches = self._create_lswitches(lswitch_create_args)
        for lswitch in lswitches:
            lports = self._create_lports(lswitch, lport_create_args,
                                        lports_per_lswitch)
            self._delete_lport(lports)

        self._delete_lswitch(lswitches)



    def get_or_create_lswitch_and_lport(self,
                              lswitch_create_args=None,
                              lport_create_args=None,
                              lports_per_lswitch=None):

        lswitches = None
        if lswitch_create_args != None:
            lswitches = self._create_lswitches(lswitch_create_args)
            for lswitch in lswitches:
                lports = self._create_lports(lswitch, lport_create_args,
                                                    lports_per_lswitch)
                lswitch["lports"] = lports
        else:
            lswitches = self.context["ovn-nb"]

        return lswitches



    @validation.number("lports_per_lswitch", minval=1, integer_only=True)
    @validation.number("acls_per_port", minval=1, integer_only=True)
    @scenario.configure(context={})
    def create_and_list_acls(self,
                              lswitch_create_args=None,
                              lport_create_args=None,
                              lports_per_lswitch=None,
                              acl_create_args=None,
                              acls_per_port=None):
        lswitches = self.get_or_create_lswitch_and_lport(lswitch_create_args,
                                    lport_create_args, lports_per_lswitch)

        for lswitch in lswitches:
            self._create_acl(lswitch, lswitch["lports"],
                             acl_create_args, acls_per_port)

        self._list_acl(lswitches)



    @scenario.configure(context={})
    def cleanup_acls(self):

        lswitches = self.context["ovn-nb"]

        self._delete_all_acls_in_lswitches(lswitches)


    @validation.number("lports_per_lswitch", minval=1, integer_only=True)
    @validation.number("acls_per_port", minval=1, integer_only=True)
    @scenario.configure(context={})
    def create_and_delete_acls(self,
                              lswitch_create_args=None,
                              lport_create_args=None,
                              lports_per_lswitch=None,
                              acl_create_args=None,
                              acls_per_port=None):

        lswitches = self.get_or_create_lswitch_and_lport(lswitch_create_args,
                                    lport_create_args, lports_per_lswitch)


        for lswitch in lswitches:
            self._create_acl(lswitch, lswitch["lports"],
                             acl_create_args, acls_per_port)


        self._delete_all_acls_in_lswitches(lswitches)

    @scenario.configure(context={})
    def create_and_remove_address_set(self, name, address_list):
        self._create_address_set(name, address_list)
        self._remove_address_set(name)



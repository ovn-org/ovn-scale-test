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
from rally.common import logging
from rally_ovs.plugins.ovs.scenarios import ovn
from rally_ovs.plugins.ovs import utils
from rally.task import scenario
from rally.task import validation

LOG = logging.getLogger(__name__)



class OvnNetwork(ovn.OvnScenario):
    """scenarios for OVN network."""

    def __init__(self, context=None):
        super(OvnNetwork, self).__init__(context)

    @scenario.configure(context={})
    def create_networks(self, network_create_args):
        self._create_networks(network_create_args)


    @scenario.configure(context={})
    def create_routers(self, router_create_args=None,
                       router_connection_method=None,
                       networks_per_router=None,
                       network_create_args=None):
        lrouters = self._create_routers(router_create_args)

        num_router = int(router_create_args.get("amount", 0))
        num_networks = int(networks_per_router) * num_router
        lnetworks = self._create_networks(network_create_args, num_networks)


        # Connect network to routers
        self._connect_networks_to_routers(lnetworks, lrouters, networks_per_router)

    @validation.number("ports_per_network", minval=1, integer_only=True)
    @scenario.configure(context={})
    def create_routers_bind_ports(self, router_create_args=None,
                                  router_connection_method=None,
                                  networks_per_router=None,
                                  network_create_args=None,
                                  port_create_args=None,
                                  ports_per_network=None,
                                  port_bind_args=None):

        # Create routers and logical networks, and connect them
        lrouters = self._create_routers(router_create_args)

        num_router = int(router_create_args.get("amount", 0))
        num_networks = int(networks_per_router) * num_router
        lnetworks = self._create_networks(network_create_args, num_networks)

        self._connect_networks_to_routers(lnetworks, lrouters, networks_per_router)

        # Create ports on the logical networks
        sandboxes = self.context["sandboxes"]
        if not sandboxes:
            # when there is no sandbox specified, bind on all sandboxes.
            sandboxes = utils.get_sandboxes(self.task["deployment_uuid"])

        lports = self._create_lports(lnetworks, port_create_args, ports_per_network)
        if (len(lports) < len(sandboxes)):
            LOG.warn("Number of ports less than chassis: random binding\n")
        self._bind_ports_and_wait(lports, sandboxes, port_bind_args)


    @validation.number("ports_per_network", minval=1, integer_only=True)
    @scenario.configure(context={})
    def create_and_bind_ports(self,
                              network_create_args=None,
                              port_create_args=None,
                              ports_per_network=None,
                              port_bind_args=None,
                              internal_ports_cleanup=True):

        sandboxes = self.context["sandboxes"]
        if not sandboxes:
            # when there is no sandbox specified, bind on all sandboxes.
            sandboxes = utils.get_sandboxes(self.task["deployment_uuid"])

        use_existing_networks = port_create_args. \
            get("use_existing_networks", False)
        if not use_existing_networks:
            lswitches = self._create_networks(network_create_args)
        else:
            lswitches = self._list_lswitches()
            num_switches = len(lswitches)
            start_cidr = network_create_args.get("start_cidr", "")
            if start_cidr:
                start_cidr = netaddr.IPNetwork(start_cidr)
                for i in range(num_switches):
                    if start_cidr:
                        lswitches[i]["cidr"] = start_cidr.next(i)

        lports = self._create_lports(lswitches, port_create_args,
                                     ports_per_network)
        self._bind_ports_and_wait(lports, sandboxes, port_bind_args)

        if internal_ports_cleanup:
            self._cleanup_ovs_internal_ports(sandboxes)

    def bind_ports(self):
        pass

    def bind_and_unbind_ports(self):
        pass

    @scenario.configure(context={})
    def list_oflow_count_for_sandboxes(self, sandbox_args={}):
        sandboxes = self.context["sandboxes"]
        if not sandboxes:
            # when there is no sandbox specified, get all sandboxes.
            sandboxes = utils.get_sandboxes(self.task["deployment_uuid"])
        self._list_oflow_count_for_sandboxes(sandboxes, sandbox_args)

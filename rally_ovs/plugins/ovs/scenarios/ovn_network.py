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

from rally.common import logging
from rally_ovs.plugins.ovs.scenarios import ovn

from rally.task import scenario
from rally.task import validation

LOG = logging.getLogger(__name__)



class OvnNetwork(ovn.OvnScenario):
    """scenarios for OVN network."""


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
        j = 0
        for i in range(len(lrouters)):
            lrouter = lrouters[i]
            LOG.info("Connect %s networks to router %s" % (networks_per_router, lrouter["name"]))
            for k in range(j, j+int(networks_per_router)):
                lnetwork = lnetworks[k]
                LOG.info("connect networks %s cidr %s" % (lnetwork["name"], lnetwork["cidr"]))
                self._connect_network_to_router(lrouter, lnetwork)

            j += int(networks_per_router)


    @validation.number("ports_per_network", minval=1, integer_only=True)
    @scenario.configure(context={})
    def create_and_bind_ports(self,
                              network_create_args=None,
                              port_create_args=None,
                              ports_per_network=None,
                              port_bind_args=None):

        sandboxes = self.context["sandboxes"]

        lswitches = self._create_networks(network_create_args)
        for lswitch in lswitches:
            lports = self._create_lports(lswitch, port_create_args, ports_per_network)
            self._bind_ports(lports, sandboxes, port_bind_args)


    def bind_ports(self):
        pass

    def bind_and_unbind_ports(self):
        pass



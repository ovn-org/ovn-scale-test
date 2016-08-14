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
            self._of_check_ports(lports, sandboxes, port_bind_args)


    def bind_ports(self):
        pass

    def bind_and_unbind_ports(self):
        pass



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


import six

from rally.task import scenario


from rally_ovs.plugins.ovs import ovsclients
from rally_ovs.plugins.ovs.consts import ResourceType
from rally_ovs.plugins.ovs.utils import *


class OvsScenario(scenario.Scenario):
    """Base class for all OVS scenarios."""


    def __init__(self, context=None):
        super(OvsScenario, self).__init__(context)

        multihost_info = context["ovn_multihost"]

        for k,v in six.iteritems(multihost_info["controller"]):
            cred = v["credential"]
            self._controller_clients = ovsclients.Clients(cred)

        self._farm_clients = {}
        for k,v in six.iteritems(multihost_info["farms"]):
            cred = v["credential"]
            self._farm_clients[k] = ovsclients.Clients(cred)

        self.install_method = multihost_info["install_method"]


    def controller_client(self, client_type="ssh"):
        client = getattr(self._controller_clients, client_type)
        return client()


    def farm_clients(self, name, client_type="ssh"):
        clients = self._farm_clients[name]
        client = getattr(clients, client_type)
        return client()












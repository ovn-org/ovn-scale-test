# Copyright 2018 Red Hat, Inc.
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

# TODO(jkbs):
# - Use constants for order
# - Require ovn_multihost context when common validators are available

from rally import consts
from rally.common import logging
from rally.task import context

from rally_ovs.plugins.ovs import ovnclients


LOG = logging.getLogger(__name__)


@context.configure(name="datapath", order=115)
class Datapath(ovnclients.OvnClientMixin, context.Context):
    """Create datapath resources.

    This context creates datapath resources, like logical routers or logical
    switches, and optionally connects switches to routers.
    """

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "properties": {
            "router_create_args": {
                "type": "object",
                "properties": {
                    "amount": {"type": "integer", "minimum": 0},
                    "batch": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": False,
            },
            "lswitch_create_args": {
                "type": "object",
                "properties": {
                    "amount": {"type": "integer", "minimum": 0},
                    "batch": {"type": "integer", "minimum": 1},
                    "start_cidr": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "networks_per_router": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    }

    DEFAULT_CONFIG = {
        "router_create_args": {"amount": 0},
        "lswitch_create_args": {"amount": 0},
        "networks_per_router": 0,
    }

    def setup(self):
        super(Datapath, self).setup()

        router_create_args = self.config["router_create_args"]
        lswitch_create_args = self.config["lswitch_create_args"]
        networks_per_router = self.config["networks_per_router"]

        routers = []
        if router_create_args["amount"]:
            routers = self._create_routers(router_create_args)

        lswitches = []
        if lswitch_create_args["amount"]:
            lswitches = self._create_lswitches(lswitch_create_args)

        if networks_per_router:
            self._connect_networks_to_routers(lswitches, routers,
                                              networks_per_router)

        self.context["datapaths"] = {
            "routers": routers,
            "lswitches": lswitches,
        }

    def cleanup(self):
        pass  # Not implemented

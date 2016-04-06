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

from rally_ovs.plugins.ovs.scenarios import sandbox

from rally.task import scenario
from rally.common import db
from rally.exceptions import NoSuchConfigField


class OvnSandbox(sandbox.SandboxScenario):

    @scenario.configure(context={})
    def create_controller(self, controller_create_args):
        multihost_dep = db.deployment_get(self.task["deployment_uuid"])

        config = multihost_dep["config"]
        controller_cidr = config["controller"].get("controller_cidr", None)
        net_dev = config["controller"].get("net_dev", None)
        deployment_name = config["controller"].get("deployment_name")

        controller_cidr = controller_create_args.get("controller_cidr",
                                                            controller_cidr)
        net_dev = controller_create_args.get("net_dev", net_dev)

        if controller_cidr == None:
            raise NoSuchConfigField(name="controller_cidr")

        if net_dev == None:
            raise NoSuchConfigField(name="net_dev")

        self._create_controller(deployment_name, controller_cidr, net_dev)



    @scenario.configure(context={})
    def create_sandbox(self, sandbox_create_args=None):
        self._create_sandbox(sandbox_create_args)


    @scenario.configure(context={})
    def create_and_delete_sandbox(self, sandbox_create_args=None):
        sandboxes = self._create_sandbox(sandbox_create_args)
        self.sleep_between(1, 2) # xxx: add min and max sleep args - l8huang
        self._delete_sandbox(sandboxes)


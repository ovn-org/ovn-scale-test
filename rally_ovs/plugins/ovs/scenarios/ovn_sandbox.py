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

import copy
import netaddr
import six

from rally.task import scenario
from rally.common import db
from rally.exceptions import NoSuchConfigField

from rally_ovs.plugins.ovs.scenarios import sandbox
from rally_ovs.plugins.ovs import utils


class OvnSandbox(sandbox.SandboxScenario):

    @scenario.configure(context={})
    def create_controller(self, controller_create_args):
        """Create ovn centralized controller on ovn controller node.

        Contains ovn-northd, northbound ovsdb-server, sourthbound ovsdb-server.
        If not exist, create a new one; otherwise, cleanup old ones then create
        a new one.

        :param controller_create_args: dict, contains below values:

            ===========         ========
            key                 desc
            ===========         ========
            controller_cidr     str, the CIDR on which ovsdb-server listening
            net_dev             str, the dev name used to add CIDR to, e.g. eth0
            ===========         ========

        """
        multihost_dep = db.deployment_get(self.task["deployment_uuid"])

        config = multihost_dep["config"]
        controller_cidr = config["controller"].get("controller_cidr", None)
        net_dev = config["controller"].get("net_dev", None)
        deployment_name = config["controller"].get("deployment_name")
        host_container = config["controller"].get("host_container")

        controller_cidr = controller_create_args.get("controller_cidr",
                                                            controller_cidr)
        net_dev = controller_create_args.get("net_dev", net_dev)

        if controller_cidr == None:
            raise NoSuchConfigField(name="controller_cidr")

        if net_dev == None:
            raise NoSuchConfigField(name="net_dev")

        self._create_controller(deployment_name, host_container,
                                controller_cidr, net_dev)



    @scenario.configure(context={})
    def create_sandbox(self, sandbox_create_args=None):
        """Create one or more sandboxes on a farm node.

         Sample configuration:

        .. code-block:: json

            {
                "farm": "ovn-farm-node-0",
                "amount": 3,
                "batch" : 10,
                "start_cidr": "192.168.64.0/16",
                "net_dev": "eth1",
                "tag": "ToR1"
            }

        :param sandbox_create_args: dict, contains below values:

            ===========    ========
            key            desc
            ===========    ========
            farm           str, the name of farm node
            farm-prefix    str, the prefix of farm node names to be used with
                           iterative runners.
            amount         int, the number of sandbox to be created
            batch          int, the number of sandbox to be created in one session
            start_cidr     str, start value for CIDR used by sandboxes
            net_dev        str, the dev name used to add CIDR to, e.g. eth0
            tag            str, a tag used to identify a set of sandboxes
            ===========    ========

        """
        start_cidr = netaddr.IPNetwork(sandbox_create_args.get("start_cidr",
                                                               "1.0.0.0/8"))
        farm = sandbox_create_args.get("farm", "")
        if not farm:
            iteration = self.context["iteration"]
            amount = sandbox_create_args.get("amount", 1)
            farm_prefix = sandbox_create_args.get("farm-prefix", "")
            farm = "{}{}".format(farm_prefix, iteration)

            # Increment sandbox cidr based on iteration.
            sandbox_create_args = copy.copy(sandbox_create_args)
            sandbox_create_args["start_cidr"] = "{}/{}".format(
                str(start_cidr.ip + iteration * amount + 1),
                start_cidr.prefixlen)

        self._create_sandbox(sandbox_create_args, farm)


    @scenario.configure(context={})
    def create_and_delete_sandbox(self, sandbox_create_args=None):
        """Create and delete sandboxes.

        Create a set of sandboxes then delete them gracefully.

        :param sandbox_create_args: see OvnSandbox.create_sandbox

        """
        sandboxes = self._create_sandbox(sandbox_create_args)
        self.sleep_between(1, 2) # xxx: add min and max sleep args - l8huang

        farm = sandbox_create_args["farm"]
        to_delete = []
        for k,v in six.iteritems(sandboxes):
            sandbox = {"name": k, "tag": v, "farm": farm}
            to_delete.append(sandbox)

        self._delete_sandbox(to_delete, True)


    @scenario.configure(context={})
    def delete_sandbox(self, sandbox_delete_args=None):
        """Delete sandboxes specified by 'sandbox_delete_args' or 'sandbox' context.

        :param sandbox_delete_args: dict, contains below values:

            ===========    ========
            key            desc
            ===========    ========
            farm           str, the name of farm node
            tag            str, a tag used to identify a set of sandboxes
            graceful       bool, exit processes gracefully, cleanup records in southbound DB
            ===========    ========

        If 'sandbox' context is set, then the sandboxes specified by the
        context will be used.

        """
        farm = sandbox_delete_args.get("farm", "")
        tag = sandbox_delete_args.get("tag", "")
        graceful = sandbox_delete_args.get("graceful", False)

        sandboxes = self._get_sandbox(farm, tag)
        self._delete_sandbox(sandboxes, graceful)


    def _get_sandbox(self, farm="", tag=""):
        if "sandboxes" in self.context:
            ret = self.context["sandboxes"]
        else:
            ret = utils.get_sandboxes(self.task["deployment_uuid"], farm, tag)

        return ret


    @scenario.configure(context={})
    def start_sandbox(self, sandbox_start_args=None):
        """Start sandboxes specified by 'sandbox_stop_args' or 'sandbox' context.
        If they are already running, do nothing.

        :param sandbox_start_args: dict, contains below values:

            ===========    ========
            key            desc
            ===========    ========
            farm           str, the name of farm node
            tag            str, a tag used to identify a set of sandboxes
            ===========    ========

        If 'sandbox' context is set, then the sandboxes specified by the
        context will be used.

        """

        farm = sandbox_start_args.get("farm", "")
        tag = sandbox_start_args.get("tag", "")
        sandboxes = self._get_sandbox(farm, tag)

        self._start_sandbox(sandboxes)


    @scenario.configure(context={})
    def stop_sandbox(self, sandbox_stop_args=None):
        """Stop sandboxes specified by 'sandbox_stop_args' or 'sandbox' context.

        :param sandbox_stop_args: dict, contains below values:

            ===========    ========
            key            desc
            ===========    ========
            farm           str, the name of farm node
            tag            str, a tag used to identify a set of sandboxes
            graceful       bool, exit processes gracefully, cleanup records in southbound DB
            ===========    ========

        If 'sandbox' context is set, then the sandboxes specified by the
        context will be used.

        """

        farm = sandbox_stop_args.get("farm", "")
        tag = sandbox_stop_args.get("tag", "")
        graceful = sandbox_stop_args.get("graceful", False)

        sandboxes = self._get_sandbox(farm, tag)
        self._stop_sandbox(sandboxes, graceful)


    @scenario.configure(context={})
    def stop_and_start_sandbox(self, sandbox_stop_args=None,
                               sandbox_start_args=None):

        """Stop sandboxes specified by 'sandbox_stop_args' or 'sandbox' context,
        then start up them again.

        :param sandbox_stop_args: see OvnSandbox.stop_sandbox
        :param sandbox_start_args: see OvnSandbox.star_sandbox

        """
        farm = sandbox_stop_args.get("farm", "")
        tag = sandbox_stop_args.get("tag", "")
        graceful = sandbox_stop_args.get("graceful", False)

        sandboxes = self._get_sandbox(farm, tag)
        self._stop_sandbox(sandboxes, graceful)
        self._start_sandbox(sandboxes)


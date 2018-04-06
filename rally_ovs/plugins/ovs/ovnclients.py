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

import netaddr

from rally.common import logging
from rally.common import utils
from rally_ovs.plugins.ovs import ovsclients


LOG = logging.getLogger(__name__)


class OvnClientMixin(ovsclients.ClientsMixin, utils.RandomNameGeneratorMixin):

    def _create_lswitches(self, lswitch_create_args, num_switches=-1):
        self.RESOURCE_NAME_FORMAT = "lswitch_XXXXXX_XXXXXX"

        if (num_switches == -1):
            num_switches = lswitch_create_args.get("amount", 1)
        batch = lswitch_create_args.get("batch", num_switches)

        start_cidr = lswitch_create_args.get("start_cidr", "")
        if start_cidr:
            start_cidr = netaddr.IPNetwork(start_cidr)

        LOG.info("Create lswitches method: %s" % self.install_method)
        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox", self.install_method)
        ovn_nbctl.enable_batch_mode()

        flush_count = batch
        lswitches = []
        for i in range(num_switches):
            name = self.generate_random_name()

            lswitch = ovn_nbctl.lswitch_add(name)
            if start_cidr:
                lswitch["cidr"] = start_cidr.next(i)

            LOG.info("create %(name)s %(cidr)s" % \
                      {"name": name, "cidr": lswitch.get("cidr", "")})
            lswitches.append(lswitch)

            flush_count -= 1
            if flush_count < 1:
                ovn_nbctl.flush()
                flush_count = batch

        ovn_nbctl.flush() # ensure all commands be run
        ovn_nbctl.enable_batch_mode(False)
        return lswitches

    def _create_routers(self, router_create_args):
        self.RESOURCE_NAME_FORMAT = "lrouter_XXXXXX_XXXXXX"

        amount = router_create_args.get("amount", 1)
        batch = router_create_args.get("batch", 1)

        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox", self.install_method)
        ovn_nbctl.enable_batch_mode()

        flush_count = batch
        lrouters = []

        for i in range(amount):
            name = self.generate_random_name()
            lrouter = ovn_nbctl.lrouter_add(name)
            lrouters.append(lrouter)

            flush_count -= 1
            if flush_count < 1:
                ovn_nbctl.flush()
                flush_count = batch

        ovn_nbctl.flush() # ensure all commands be run
        ovn_nbctl.enable_batch_mode(False)

        return lrouters

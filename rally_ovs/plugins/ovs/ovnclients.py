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


from rally.common import utils
from rally_ovs.plugins.ovs import ovsclients


class OvnClientMixin(ovsclients.ClientsMixin, utils.RandomNameGeneratorMixin):

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

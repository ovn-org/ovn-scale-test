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

import ddt
import mock

from rally_ovs.plugins.ovs import ovsclients
# We won't be using ovsclients_impl directly but we need decorators to run.
from rally_ovs.plugins.ovs import ovsclients_impl
from tests.unit import test


@ddt.ddt
class OvnNbctlTestCase(test.TestCase):

    @ddt.data(
        # no addresses
        { "port"      : "lp0",
          "addresses" : (),
          "run_args"  : ["lp0"] },
        # empty L2 address
        { "port"      : "lp0",
          "addresses" : ([""],),
          "run_args"  : ["lp0"] },
        # empty L2 & L3 address
        { "port"      : "lp0",
          "addresses" : (["", ""],),
          "run_args"  : ["lp0"] },
        # one L2 address
        { "port"      : "lp0",
          "addresses" : (["02:03:04:05:06"],),
          "run_args"  : ["lp0", "02:03:04:05:06"] },
        # one L2 address and empty L3 address
        { "port"      : "lp0",
          "addresses" : (["02:03:04:05:06", ""],),
          "run_args"  : ["lp0", "02:03:04:05:06"] },
        # one L2 address, one L3 address
        { "port"      : "lp0",
          "addresses" : (["02:03:04:05:06", "1.2.3.4"],),
          "run_args"  : ["lp0", "02:03:04:05:06\ 1.2.3.4"] },
        # one L2 address, two L3 addresses
        { "port"      : "lp0",
          "addresses" : (["02:03:04:05:06", "1.2.3.4", "5.6.7.8"],),
          "run_args"  : ["lp0", "02:03:04:05:06\ 1.2.3.4\ 5.6.7.8"] },
        # two L2 addresses
        { "port"      : "lp0",
          "addresses" : (["02:03:04:05:06"], ["0a:0b:0c:0d:0e:0f"]),
          "run_args"  : ["lp0", "02:03:04:05:06", "0a:0b:0c:0d:0e:0f"] },
        # two pairs of L2 & L3 addresses
        { "port"      : "lp0",
          "addresses" : (["02:03:04:05:06", "1.2.3.4"], ["0a:0b:0c:0d:0e:0f", "10.20.30.40"]),
          "run_args"  : ["lp0", "02:03:04:05:06\ 1.2.3.4", "0a:0b:0c:0d:0e:0f\ 10.20.30.40"] },
    )
    @ddt.unpack
    def test_lport_set_addresses(self, port, addresses, run_args):
        fake_creds = {
            "user"     : None,
            "host"     : None,
            "port"     : None,
            "key"      : None,
            "password" : None,
        }

        clients = ovsclients.Clients(fake_creds)
        client = getattr(clients, "ovn-nbctl")
        nbctl = client()

        nbctl.run = mock.Mock()
        nbctl.lport_set_addresses(port, *addresses)
        nbctl.run.assert_called_once_with("lsp-set-addresses", args=run_args)

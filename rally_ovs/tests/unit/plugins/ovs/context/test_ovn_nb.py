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

import mock

from rally_ovs.plugins.ovs.context import ovn_nb
from rally_ovs.tests.unit.plugins.ovs import utils
from tests.unit import test

class OvnNorthboundContextTestCase(test.TestCase):

    @mock.patch("rally_ovs.plugins.ovs.ovsclients_impl.OvnNbctl.create_client")
    def test_setup(self, mock_create_client):
        ovn_nbctl_show_output = """\
switch 48732e5d-b018-4bad-a1b6-8dbc762f4126 (lswitch_c52f4c_xFG42O)
    port lport_c52f4c_LXzXCE
    port lport_c52f4c_dkZSDg
switch 7f55c582-c007-4fba-810d-a14ead480851 (lswitch_c52f4c_Rv0Jcj)
    port lport_c52f4c_cm8SIf
    port lport_c52f4c_8h7hn2
switch 9fea76cf-d73e-4dc8-a2a3-1e98b9d8eab0 (lswitch_c52f4c_T0m6Ce)
    port lport_c52f4c_X3px3u
    port lport_c52f4c_92dhqb
"""
        mock_client = mock_create_client.return_value
        mock_client.show.return_value = ovn_nbctl_show_output

        context = utils.get_fake_context(ovn_nb={})
        nb_context = ovn_nb.OvnNorthboundContext(context)
        nb_context.setup()

        expected_setup_output = ovn_nbctl_show_output
        actual_setup_output = nb_context.context["ovn-nb"]
        self.assertEqual(expected_setup_output, actual_setup_output)

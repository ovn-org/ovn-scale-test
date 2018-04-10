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

import collections
import itertools

import mock
from netaddr import IPNetwork
from jsonschema.exceptions import ValidationError

import ddt
from rally_ovs.plugins.ovs.context.datapath import Datapath
from rally_ovs.tests.unit.plugins.ovs import utils
from tests.unit import test


def gen_datapath_name(prefix, start=1):
    n = itertools.count(start)
    while True:
        yield {"name": prefix + str(next(n))}


@ddt.ddt
class DatapathTestCase(test.TestCase):

    @ddt.data({},
              {"amount": 0},
              {"amount": 1},
              {"amount": 2},
              {"amount": 0, "batch": 1},
              {"amount": 1, "batch": 1},
              {"amount": 2, "batch": 1},
              {"amount": 2, "batch": 2})
    def test_valid_router_config(self, router_create_args):
        config = {"router_create_args": router_create_args}
        Datapath.validate(config)

    @ddt.data({"amount": -1},
              {"amount": 0, "batch": 0},
              {"amount": 1, "batch": -1})
    def test_invalid_router_config(self, router_create_args):
        config = {"router_create_args": router_create_args}
        with self.assertRaisesRegexp(ValidationError, ""):  # Ignore message
            Datapath.validate(config)

    def test_setup_default(self):
        context = utils.get_fake_context(datapath={})
        dp_context = Datapath(context)
        dp_context.setup()

    @ddt.data({
        "config": {
            "router_create_args": {"amount": 1},
        },
        "datapaths": {
            "routers": [
                {"name": "lrouter_1"},
            ],
        },
    }, {
        "config": {
            "router_create_args": {"amount": 2},
        },
        "datapaths": {
            "routers": [
                {"name": "lrouter_1"},
                {"name": "lrouter_2"},
            ],
        },
    }, {
        "config": {
            "router_create_args": {"amount": 3},
        },
        "datapaths": {
            "routers": [
                {"name": "lrouter_1"},
                {"name": "lrouter_2"},
                {"name": "lrouter_3"},
            ],
        },
    })
    @ddt.unpack
    @mock.patch("rally_ovs.plugins.ovs.ovsclients_impl.OvnNbctl.create_client")
    def test_only_routers(self, mock_create_client, config, datapaths):
        mock_client = mock_create_client.return_value
        mock_client.lrouter_add.side_effect = gen_datapath_name("lrouter_")

        context = utils.get_fake_context(datapath=config)
        dp_context = Datapath(context)
        dp_context.setup()

        expected_routers = datapaths["routers"]
        actual_routers = dp_context.context["datapaths"]["routers"]
        self.assertSequenceEqual(sorted(expected_routers),
                                 sorted(actual_routers))

    @ddt.data({
        "config": {
            "lswitch_create_args": {"amount": 1, "start_cidr": "10.1.0.0/16"},
        },
        "datapaths": {
            "lswitches": [
                {"name": "lswitch_1", "cidr": IPNetwork("10.1.0.0/16")},
            ],
        },
    }, {
        "config": {
            "lswitch_create_args": {"amount": 2, "start_cidr": "10.1.0.0/16"},
        },
        "datapaths": {
            "lswitches": [
                {"name": "lswitch_1", "cidr": IPNetwork("10.1.0.0/16")},
                {"name": "lswitch_2", "cidr": IPNetwork("10.2.0.0/16")},
            ],
        },
    }, {
        "config": {
            "lswitch_create_args": {"amount": 3, "start_cidr": "10.1.0.0/16"},
        },
        "datapaths": {
            "lswitches": [
                {"name": "lswitch_1", "cidr": IPNetwork("10.1.0.0/16")},
                {"name": "lswitch_2", "cidr": IPNetwork("10.2.0.0/16")},
                {"name": "lswitch_3", "cidr": IPNetwork("10.3.0.0/16")},
            ],
        },
    })
    @ddt.unpack
    @mock.patch("rally_ovs.plugins.ovs.ovsclients_impl.OvnNbctl.create_client")
    def test_only_lswitches(self, mock_create_client, config, datapaths):
        mock_client = mock_create_client.return_value
        mock_client.lswitch_add.side_effect = gen_datapath_name("lswitch_")

        context = utils.get_fake_context(datapath=config)
        dp_context = Datapath(context)
        dp_context.setup()

        expected_lswitches = datapaths["lswitches"]
        actual_lswitches = dp_context.context["datapaths"]["lswitches"]
        self.assertSequenceEqual(sorted(expected_lswitches),
                                 sorted(actual_lswitches))

    @ddt.data({
        "config": {
            "router_create_args": {"amount": 1},
            "lswitch_create_args": {"amount": 1, "start_cidr": "10.0.0.0/16"},
        },
        "datapaths": {
            "routers": [
                {"name": "lrouter_1"},
            ],
            "lswitches": [
                {"name": "lswitch_1", "cidr": IPNetwork("10.0.0.0/16")},
            ],
        }
    }, {
        "config": {
            "router_create_args": {"amount": 2},
            "lswitch_create_args": {"amount": 4, "start_cidr": "10.0.0.0/16"},
        },
        "datapaths": {
            "routers": [
                {"name": "lrouter_1"},
                {"name": "lrouter_2"},
            ],
            "lswitches": [
                {"name": "lswitch_1", "cidr": IPNetwork("10.0.0.0/16")},
                {"name": "lswitch_2", "cidr": IPNetwork("10.1.0.0/16")},
                {"name": "lswitch_3", "cidr": IPNetwork("10.2.0.0/16")},
                {"name": "lswitch_4", "cidr": IPNetwork("10.3.0.0/16")},
            ],
        },
    })
    @ddt.unpack
    @mock.patch("rally_ovs.plugins.ovs.ovsclients_impl.OvnNbctl.create_client")
    def test_lswitches_and_routers(self, mock_create_client, config,
                                   datapaths):
        mock_client = mock_create_client.return_value
        mock_client.lrouter_add.side_effect = gen_datapath_name("lrouter_")
        mock_client.lswitch_add.side_effect = gen_datapath_name("lswitch_")

        context = utils.get_fake_context(datapath=config)
        dp_context = Datapath(context)
        dp_context.setup()

        expected_routers = datapaths["routers"]
        actual_routers = dp_context.context["datapaths"]["routers"]
        self.assertSequenceEqual(sorted(expected_routers),
                                 sorted(actual_routers))

        expected_lswitches = datapaths["lswitches"]
        actual_lswitches = dp_context.context["datapaths"]["lswitches"]
        self.assertSequenceEqual(sorted(expected_lswitches),
                                 sorted(actual_lswitches))

    @ddt.data({
        "config": {
            "router_create_args": {"amount": 1},
            "lswitch_create_args": {"amount": 1, "start_cidr": "10.0.0.0/16"},
            "networks_per_router": 1,
        },
    }, {
        "config": {
            "router_create_args": {"amount": 2},
            "lswitch_create_args": {"amount": 4, "start_cidr": "10.0.0.0/16"},
            "networks_per_router": 2,
        },
    }, {
        "config": {
            "router_create_args": {"amount": 2},
            "lswitch_create_args": {"amount": 5, "start_cidr": "10.0.0.0/16"},
            "networks_per_router": 3,
        },
    })
    @ddt.unpack
    @mock.patch("rally_ovs.plugins.ovs.ovsclients_impl.OvnNbctl.create_client")
    def test_connected_lswitches_and_routers_port_count(self,
                                                        mock_create_client,
                                                        config):
        mock_client = mock_create_client.return_value

        mock_client.lrouter_add.side_effect = gen_datapath_name("lrouter_")
        mock_client.lswitch_add.side_effect = gen_datapath_name("lswitch_")

        router_port_count = collections.Counter()
        switch_port_count = collections.Counter()

        def fake_lrouter_port_add(name, *args, **kwargs):
            router_port_count[name] += 1

        def fake_lswitch_port_add(name, *args, **kwargs):
            switch_port_count[name] += 1

        mock_client.lrouter_port_add = fake_lrouter_port_add
        mock_client.lswitch_port_add = fake_lswitch_port_add

        context = utils.get_fake_context(datapath=config)
        dp_context = Datapath(context)
        dp_context.setup()

        router_count = config["router_create_args"]["amount"]
        switch_count = config["lswitch_create_args"]["amount"]
        networks_per_router = config["networks_per_router"]

        expected_router_port_count = [networks_per_router] * router_count
        if switch_count % networks_per_router:
            expected_router_port_count[0] = switch_count % networks_per_router
        expected_switch_port_count = [1] * switch_count

        actual_router_port_count = router_port_count.values()
        actual_switch_port_count = switch_port_count.values()

        self.assertSequenceEqual(sorted(expected_router_port_count),
                                 sorted(actual_router_port_count))
        self.assertSequenceEqual(sorted(expected_switch_port_count),
                                 sorted(actual_switch_port_count))

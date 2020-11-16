# Copyright (c) 2019 Red Hat Inc.
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
from rally_ovs.plugins.ovs.scenarios import ovn
from rally_ovs.plugins.ovs.scenarios import ovn_network
from rally.task import scenario
from rally.task import validation
from rally.task import atomic

import time

LOG = logging.getLogger(__name__)

class OvnIGMP(ovn_network.OvnNetwork):
    """scenarios for OVN IGMP"""

    def __init__(self, context=None):
        super(OvnIGMP, self).__init__(context)

    def _lport_idx_inc(self, idx, max, inc=1):
        idx += inc
        return idx % max

    @atomic.action_timer("ovn_igmp.run_mcast")
    def _run_mcast(self, expected_count, lswitches, error=10):

        for iteration in range(0, 60):
            LOG.info('Iteration {}'.format(iteration))
            ovn_sbctl = self.controller_client("ovn-sbctl")
            ovn_sbctl.set_log_cmd(self.context.get("log_cmd", False))
            igmp_flow_count = 0
            for lswitch in lswitches:
                igmp_flow_count += ovn_sbctl.count_igmp_flows(lswitch['name'])

            LOG.info('IGMP flows: {} Expected {}'.format(
                igmp_flow_count, expected_count))

            if igmp_flow_count >= expected_count - error:
                break;

            time.sleep(0.5)

    def _install_mcast_tester(self, sandboxes, path):
        for sandbox in sandboxes:
            ovs_ssh = self._get_conn(sandbox["name"])
            ovs_ssh.ssh.put_file(path, '/tmp/test.c')

        self._flush_conns(cmds=[
            'gcc -lpthread -o /tmp/test /tmp/test.c'
        ])

    def _build_config_testers(self, lswitches, ports, lports_per_lswitch,
                              mc_groups_per_network,
                              test_dest_count,
                              test_mcast_batch):
        def _init_iteration():
            return {
                lport['name']: {'n_groups': 0, 'groups': []}
                for lport in ports
            }

        iterations = []
        current_iteration = _init_iteration()
        current_total = 0

        for lswitch in lswitches:
            lports = lports_per_lswitch[lswitch["name"]]
            if len(lports) == 0:
                continue

            lport_idx = 0
            max_idx = len(lports)

            mc_groups = [netaddr.IPAddress('239.0.0.1') + gid
                            for gid in range(0, mc_groups_per_network)]

            for mc_group in mc_groups:
                for i in range(0, test_dest_count):
                    lport = lports[lport_idx]
                    lport_idx = self._lport_idx_inc(lport_idx, max_idx)

                    current_iteration[lport['name']]['n_groups'] += 1
                    current_iteration[lport['name']]['groups'].append(mc_group)
                    current_total += 1

                    if current_total == test_mcast_batch:
                        iterations.append((current_total, current_iteration))
                        current_iteration = _init_iteration()
                        current_total = 0

        if current_total != 0:
            iterations.append((current_total, current_iteration))
        return iterations

    def _config_mcast_testers(self, ports, iterations):
        for lport in ports:
            port_name = lport["name"]
            _, sandbox = self.context["ovs-internal-ports"][port_name]
            ovs_ssh = self._get_conn(sandbox["name"])
            ovs_ssh.run(
                'echo {n} > /tmp/test-{p}-input'.format(
                    n=len(iterations), p=port_name))

        for expected_count, lport_map in iterations:
            for port_name, port_groups in lport_map.items():
                _, sandbox = self.context["ovs-internal-ports"][port_name]
                ovs_ssh = self._get_conn(sandbox["name"])
                ovs_ssh.run(
                    'echo {n} >> /tmp/test-{p}-input'.format(
                        n=port_groups['n_groups'], p=port_name))
                for mc_group in port_groups['groups']:
                    ovs_ssh.run(
                        'echo {g} >> /tmp/test-{p}-input'.format(
                            g=mc_group, p=port_name))
            self._flush_conns()

    def _start_mcast_tester(self, port_name):
        _, sandbox = self.context["ovs-internal-ports"][port_name]
        ovs_ssh = self._get_conn(sandbox["name"])
        input_file = '/tmp/test-{p}-input'.format(p=port_name)
        ovs_ssh.run(
            'ip netns exec {p} /tmp/test {ifile}'.format(
                p=port_name, ifile=input_file))

    def _trigger_mcast_tester(self, port_name):
        _, sandbox = self.context["ovs-internal-ports"][port_name]
        ovs_ssh = self._get_conn(sandbox["name"])
        ovs_ssh.run(
            "kill -s SIGUSR1 `ps aux | grep {p} | grep -v grep | "
            "awk '{{print $2}}'` &> /dev/null || /bin/true".format(
        p=port_name))

    def _start_mcast(self, lswitches, all_lports, lports_per_lswitch,
                     mc_groups_per_network, test_dest_count, test_mcast_batch):

        # Avoid lazy connection creation:
        ovn_sbctl = self.controller_client("ovn-sbctl")
        ovn_sbctl.set_log_cmd(self.context.get("log_cmd", False))

        # Build configuration for each port for each iteration
        iterations = self._build_config_testers(lswitches, all_lports,
                                                lports_per_lswitch,
                                                mc_groups_per_network,
                                                test_dest_count,
                                                test_mcast_batch)

        # Write the config on the DUTs (for each port).
        self._config_mcast_testers(all_lports, iterations)

        # Start the tester apps (one for each port).
        for lport in all_lports:
            port_name = lport["name"]
            self._start_mcast_tester(port_name)
        self._flush_conns()

        LOG.info('Finished configuring multicast receivers')

        time.sleep(10)

        # Run the test iterations. Every iteration is triggered by sending
        # SIGUSR1 to the test apps.
        total_expected = 0
        for iteration, (expected_count, port_map) in enumerate(iterations):
            for port_name in port_map.iterkeys():
                self._trigger_mcast_tester(port_name)

            self._flush_conns()
            total_expected += expected_count

            LOG.info(
                'Started {} multicast receivers. Total until now: {}'.format(
            expected_count, total_expected))
            self._run_mcast(total_expected, lswitches)

    def _cleanup_mcast_tests(self):
        self._flush_conns(cmds=[
            'killall -s KILL test &> /dev/null || /bin/true',
            'rm -rf /tmp/test*input'
        ])

    def _cleanup_mcast(self, lswitches, sandboxes):
        LOG.info('Cleaning up setup...')

        self._delete_lswitch(lswitches)
        self._cleanup_ovs_internal_ports(sandboxes)

    @validation.number("ports_per_network", minval=4, integer_only=True)
    @scenario.configure(context={})
    def igmp_scale(self, network_create_args=None,
                   port_create_args=None,
                   ports_per_network=None,
                   port_bind_args=None,
                   cleanup=True,
                   igmp_args=None):
        sandboxes = self.context["sandboxes"]
        if not sandboxes:
            # when there is no sandbox specified, bind on all sandboxes.
            sandboxes = utils.get_sandboxes(self.task["deployment_uuid"])

        lswitches = self._create_networks(network_create_args)

        lports = []
        lports_per_lswitch = {}

        mc_groups_per_network = igmp_args.get("group_count", 1)
        test_dest_count = igmp_args.get("receivers", 2)
        test_pkt_size = igmp_args.get("pkt_size", 64)
        test_bw = igmp_args.get("bw", "1K")
        test_mcast_batch = igmp_args.get("mcast_batch", 200)
        test_mcast_rcv_path = igmp_args.get("mcast_recv_path");

        if cleanup:
            self._cleanup_mcast_tests()

        for lswitch in lswitches:
            switch_lports = self._create_switch_lports(lswitch,
                                                       port_create_args,
                                                       ports_per_network)
            lports_per_lswitch[lswitch["name"]] = switch_lports
            lports += switch_lports

        self._bind_ports_and_wait(lports, sandboxes, port_bind_args)

        LOG.info('Sleeping for a bit before starting multicast..')
        time.sleep(10)

        self._install_mcast_tester(sandboxes, test_mcast_rcv_path)

        self._start_mcast(lswitches, lports, lports_per_lswitch,
                          mc_groups_per_network, test_dest_count,
                          test_mcast_batch)

        if cleanup:
            LOG.info('Sleeping for a bit before cleaning up..')
            time.sleep(20)
            self._cleanup_mcast(lswitches, sandboxes)

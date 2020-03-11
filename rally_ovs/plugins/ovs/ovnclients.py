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
from rally.common.utils import RandomNameGeneratorMixin

from rally_ovs.plugins.ovs import ovsclients
from rally_ovs.plugins.ovs import utils


LOG = logging.getLogger(__name__)


class OvnClientMixin(ovsclients.ClientsMixin, RandomNameGeneratorMixin):
    def _get_ovn_controller(self, install_method="sandbox"):
        ovn_nbctl = self.controller_client("ovn-nbctl")
        ovn_nbctl.set_sandbox("controller-sandbox", install_method,
                              self.context['controller']['host_container'])
        ovn_nbctl.set_daemon_socket(self.context.get("daemon_socket", None))
        return ovn_nbctl

    def _start_daemon(self, nbctld_config):
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        return ovn_nbctl.start_daemon(nbctld_config)

    def _stop_daemon(self):
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.stop_daemon()

    def _restart_daemon(self, nbctld_config):
        self._stop_daemon()
        return self._start_daemon(nbctld_config)

    def _get_gw_ip(self, network_cidr, offset=1):
        # Use the last IP (- offset) in the CIDR as gateway IP.
        return netaddr.IPAddress(network_cidr.last - offset)

    def _create_lswitches(self, lswitch_create_args, num_switches=-1):
        self.RESOURCE_NAME_FORMAT = "lswitch_XXXXXX_XXXXXX"

        if (num_switches == -1):
            num_switches = lswitch_create_args.get("amount", 1)
        batch = lswitch_create_args.get("batch", num_switches)

        start_cidr = lswitch_create_args.get("start_cidr", "")
        if start_cidr:
            start_cidr = netaddr.IPNetwork(start_cidr)

        mcast_snoop = lswitch_create_args.get("mcast_snoop", "false")
        mcast_idle = lswitch_create_args.get("mcast_idle_timeout", 300)
        mcast_table_size = lswitch_create_args.get("mcast_table_size", 2048)

        LOG.info("Create lswitches method: %s" % self.install_method)
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.enable_batch_mode()

        flush_count = batch
        lswitches = []
        for i in range(num_switches):
            name = self.generate_random_name()
            if start_cidr:
                cidr = start_cidr.next(i)
                name = "lswitch_%s" % cidr
            else:
                name = self.generate_random_name()

            other_cfg = {
                'mcast_snoop': mcast_snoop,
                'mcast_idle_timeout': mcast_idle,
                'mcast_table_size': mcast_table_size
            }

            lswitch = ovn_nbctl.lswitch_add(name, other_cfg)
            if start_cidr:
                lswitch["cidr"] = cidr

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

        ovn_nbctl = self._get_ovn_controller(self.install_method)
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

    def _connect_network_to_router(self, router, network):
        LOG.info("Connect network %s to router %s" % (network["name"], router["name"]))

        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.enable_batch_mode(False)


        base_mac = [i[:2] for i in self.task["uuid"].split('-')]
        base_mac[0] = str(hex(int(base_mac[0], 16) & 254))
        base_mac[3:] = ['00']*3
        mac = utils.get_random_mac(base_mac)

        gw = self._get_gw_ip(network["cidr"])
        lrouter_port_ip = '{}/{}'.format(gw, network["cidr"].prefixlen)
        lrouter_port = ovn_nbctl.lrouter_port_add(router["name"], network["name"], mac,
                                                  lrouter_port_ip)
        ovn_nbctl.flush()


        switch_router_port = "rp-" + network["name"]
        lport = ovn_nbctl.lswitch_port_add(network["name"], switch_router_port)
        ovn_nbctl.db_set('Logical_Switch_Port', switch_router_port,
                         ('options', {"router-port":network["name"]}),
                         ('type', 'router'),
                         ('address', 'router'))
        ovn_nbctl.flush()

    def _connect_networks_to_routers(self, lnetworks, lrouters, networks_per_router):
        for lrouter in lrouters:
            LOG.info("Connect %s networks to router %s" % (networks_per_router, lrouter["name"]))
            for lnetwork in lnetworks[:networks_per_router]:
                LOG.info("connect networks %s cidr %s" % (lnetwork["name"], lnetwork["cidr"]))
                self._connect_network_to_router(lrouter, lnetwork)

            lnetworks = lnetworks[networks_per_router:]

    def _connect_gateway_router(self, router, network, gw_cidr, ext_cidr, sandbox):
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.enable_batch_mode()

        base_mac = [i[:2] for i in self.task["uuid"].split('-')]
        base_mac[0] = str(hex(int(base_mac[0], 16) & 254))
        base_mac[3:] = ['00']*3

        # Create a join switch to connect the GW router to the cluster router.
        join_switch_name = "join_" + str(gw_cidr)
        join_switch = ovn_nbctl.lswitch_add(join_switch_name)

        # Create ports between the join switch and the cluster router.
        router_port_join_switch = "rpj-" + str(gw_cidr)
        rp_gw = self._get_gw_ip(gw_cidr, 1)
        router_port_join_switch_ip = '{}/{}'.format(rp_gw, gw_cidr.prefixlen)
        ovn_nbctl.lrouter_port_add(router["name"], router_port_join_switch,
                                   utils.get_random_mac(base_mac),
                                   router_port_join_switch_ip)

        join_switch_router_port = "jrp-" + str(gw_cidr)
        ovn_nbctl.lswitch_port_add(join_switch_name, join_switch_router_port)
        ovn_nbctl.db_set('Logical_Switch_Port', join_switch_router_port,
                         ('options', {"router-port":router_port_join_switch}),
                         ('type', 'router'),
                         ('address', 'router'))

        # Create a gateway router and bind it to the local chassis.
        gw_router_name = "grouter_" + str(gw_cidr)
        gw_router = ovn_nbctl.lrouter_add(gw_router_name)
        ovn_nbctl.db_set('Logical_Router', gw_router_name,
                         ('options', {'chassis': sandbox["host_container"]}))

        # Create ports between the join switch and the gateway router.
        grouter_port_join_switch = "grpj-" + str(gw_cidr)
        gr_gw = self._get_gw_ip(gw_cidr, 2)
        grouter_port_join_switch_ip = '{}/{}'.format(gr_gw, gw_cidr.prefixlen)
        ovn_nbctl.lrouter_port_add(gw_router_name, grouter_port_join_switch,
                                   utils.get_random_mac(base_mac),
                                   grouter_port_join_switch_ip)

        join_switch_gw_router_port = "jrpg-" + str(gw_cidr)
        ovn_nbctl.lswitch_port_add(join_switch_name, join_switch_gw_router_port)
        ovn_nbctl.db_set('Logical_Switch_Port', join_switch_gw_router_port,
                         ('options', {"router-port":grouter_port_join_switch}),
                         ('type', 'router'),
                         ('address', 'router'))

        # Create an external switch connecting the gateway router to the
        # physnet.
        ext_switch_name = "ext_" + str(ext_cidr)
        ext_switch = ovn_nbctl.lswitch_add(ext_switch_name)

        # Create ports between the external switch and the gateway router.
        grouter_port_ext_switch = "grpe-" + str(ext_cidr)
        gw = self._get_gw_ip(ext_cidr, 1)
        gr_def_gw = self._get_gw_ip(ext_cidr, 2)
        grouter_port_ext_switch_ip = '{}/{}'.format(gw, ext_cidr.prefixlen)
        ovn_nbctl.lrouter_port_add(gw_router_name, grouter_port_ext_switch,
                                   utils.get_random_mac(base_mac),
                                   grouter_port_ext_switch_ip)
    
        ext_switch_gw_router_port = "erpg-" + str(ext_cidr)
        ovn_nbctl.lswitch_port_add(ext_switch_name, ext_switch_gw_router_port)
        ovn_nbctl.db_set('Logical_Switch_Port', ext_switch_gw_router_port,
                         ('options', {"router-port":grouter_port_ext_switch}),
                         ('type', 'router'),
                         ('address', 'router'))

        # Store gateway router relevant IPs.
        gw_router['def_gw'] = gr_def_gw
        gw_router['gw'] = gr_gw
        gw_router['rp_gw'] = rp_gw

        ovn_nbctl.flush()
        ovn_nbctl.enable_batch_mode(False)
        return network, router, join_switch, gw_router, ext_switch

    def _connect_networks_to_gw_routers(self, lnetworks, lrouters, sandboxes,
                                        lnetwork_args, networks_per_router):
        gw_cidr = lnetwork_args.get('start_gw_cidr')
        if not gw_cidr:
            LOG.error("_connect_networks_to_gw_routers: missing start_gw_cidr")
            return []

        ext_cidr = lnetwork_args.get('start_ext_cidr')
        if not ext_cidr:
            LOG.error("_connect_networks_to_gw_routers: missing start_ext_cidr")
            return []

        dps = []
        for lrouter in lrouters:
            for i, lnetwork in enumerate(lnetworks[:networks_per_router]):
                LOG.info("Connect router %s to gateway router for network %s cidr %s gw_cidr %s ext_cidr %s" %
                            (lrouter["name"], lnetwork["name"], lnetwork["cidr"],
                             str(gw_cidr), str(ext_cidr)))
                dps.append(self._connect_gateway_router(lrouter, lnetwork,
                                                        gw_cidr, ext_cidr,
                                                        sandboxes[i]))
                gw_cidr = gw_cidr.next()
                ext_cidr = ext_cidr.next()
            lnetworks = lnetworks[networks_per_router:]
            sandboxes = sandboxes[networks_per_router:]
        return dps

    def _connect_gw_routers_routes(self, dps, lnetwork_args):
        cluster_cidr = lnetwork_args.get('cluster_cidr')
        if not cluster_cidr:
            LOG.error('_connect_gw_routers_routes: missing cluser_cidr')
            return

        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.enable_batch_mode()
        for network, router, join_switch, gw_router, ext_switch in dps:

            router_name = router['name']
            gw_router_name = gw_router['name']

            # Force return traffic to return on the same node.
            ovn_nbctl.db_set('Logical_Router', gw_router_name,
                             ('options', {'lb_force_snat_ip': str(gw_router['gw'])}))

            # Default route to get out of cluster via physnet.
            ovn_nbctl.lrouter_route_add(gw_router_name, "0.0.0.0/0",
                                        str(gw_router['def_gw']))

            # Route for traffic entering the cluster.
            ovn_nbctl.lrouter_route_add(gw_router_name, cluster_cidr,
                                        str(gw_router['rp_gw']))

            # Route for traffic that needs to exit the cluster
            # (via gw router).
            ovn_nbctl.lrouter_route_add(router_name, str(network["cidr"]),
                                        str(gw_router['gw']), policy="src-ip")

            # SNAT traffic leaving the cluster.
            ovn_nbctl.lrouter_nat_add(gw_router_name, "snat",
                                      str(gw_router['gw']), cluster_cidr)
            ovn_nbctl.flush()
        ovn_nbctl.enable_batch_mode(False)

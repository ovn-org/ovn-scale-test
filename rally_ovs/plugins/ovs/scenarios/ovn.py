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

from rally_ovs.plugins.ovs import scenario
from rally.task import atomic
from rally.common import logging
from rally import exceptions
from rally_ovs.plugins.ovs import ovnclients
from rally_ovs.plugins.ovs import utils
import copy
import random
import netaddr
from datetime import datetime
from io import StringIO

LOG = logging.getLogger(__name__)


class OvnScenario(ovnclients.OvnClientMixin, scenario.OvsScenario):
    RESOURCE_NAME_FORMAT = "lswitch_XXXXXX_XXXXXX"

    def __init__(self, context=None):
        super(OvnScenario, self).__init__(context)
        self._ssh_conns = None

    def __del__(self):
        if self._ssh_conns:
            self._ssh_conns.clear()

    def _build_conn_hash(self, context):
        if not self._ssh_conns is None:
            return

        if not context:
            return

        self._ssh_conns = {}

        for sandbox in context["sandboxes"]:
            sb_name = sandbox["name"]
            farm = sandbox["farm"]
            ovs_ssh = self.farm_clients(farm, "ovs-ssh")
            ovs_ssh.set_sandbox(sb_name, self.install_method,
                                sandbox["host_container"])
            ovs_ssh.enable_batch_mode()
            self._ssh_conns[sb_name] = ovs_ssh

    def _get_conn(self, sb_name):
        self._build_conn_hash(self.context)
        return self._ssh_conns[sb_name]

    def _flush_conns(self, cmds=[]):
        if self._ssh_conns is None:
            return

        for _, ovs_ssh in self._ssh_conns.items():
            for cmd in cmds:
                ovs_ssh.run(cmd)
            ovs_ssh.flush()

    '''
    return: [{"name": "lswitch_xxxx_xxxxx", "cidr": netaddr.IPNetwork}, ...]
    '''
    @atomic.action_timer("ovn.create_lswitch")
    def _create_lswitches(self, lswitch_create_args, num_switches=-1):
        print("create lswitch")
        return super(OvnScenario, self)._create_lswitches(lswitch_create_args, num_switches)

    @atomic.optional_action_timer("ovn.list_lswitch")
    def _list_lswitches(self):
        print("list lswitch")
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        return ovn_nbctl.lswitch_list()

    @atomic.action_timer("ovn.delete_lswitch")
    def _delete_lswitch(self, lswitches):
        print("delete lswitch")
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.enable_batch_mode()
        for lswitch in lswitches:
            ovn_nbctl.lswitch_del(lswitch["name"])

        ovn_nbctl.flush()
        ovn_nbctl.enable_batch_mode(False)

    def _get_or_create_lswitch(self, lswitch_create_args=None):
        pass

    @atomic.action_timer("ovn.create_lport")
    def _create_lports(self, lswitches, lport_create_args = [], lport_amount=1,
                       lport_ip_shift=1, ext_cidr=None):
        lports = []
        for idx, lswitch in enumerate(lswitches):
            lports += self._create_switch_lports(lswitch, lport_create_args,
                                                 lport_amount,
                                                 lport_ip_shift,
                                                 ext_cidr.next(idx) if ext_cidr else None)
        return lports

    def _create_switch_lports(self, lswitch, lport_create_args = [],
                              lport_amount=1, lport_ip_shift = 1,
                              ext_cidr = None):
        LOG.info("create %d lports on lswitch %s" % \
                            (lport_amount, lswitch["name"]))

        self.RESOURCE_NAME_FORMAT = "lpXXXXXX_XXXXXX"

        batch = lport_create_args.get("batch", lport_amount)
        port_security = lport_create_args.get("port_security", True)

        LOG.info("Create lports method: %s" % self.install_method)

        network_cidr = lswitch.get("cidr", None)
        ip_addrs = None
        if network_cidr:
            end_ip = network_cidr.ip + lport_amount + lport_ip_shift
            if not end_ip in network_cidr:
                message = _("Network %s's size is not big enough for %d lports.")
                raise exceptions.InvalidConfigException(
                            message  % (network_cidr, lport_amount))

            ip_addrs = netaddr.iter_iprange(network_cidr.ip + lport_ip_shift,
                                            network_cidr.last)

        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.enable_batch_mode()

        base_mac = [i[:2] for i in self.task["uuid"].split('-')]
        base_mac[0] = str(hex(int(base_mac[0], 16) & 254))
        base_mac[3:] = ['00']*3

        flush_count = batch
        lports = []
        for i in range(lport_amount):
            ip = str(next(ip_addrs)) if ip_addrs else ""
            if len(ip):
                name = "lp_%s" % ip
            else:
                name = self.generate_random_name()
            mac = utils.get_random_mac(base_mac)
            ip_mask = '{}/{}'.format(ip, network_cidr.prefixlen)
            gw = str(self._get_gw_ip(network_cidr))
            ext_gw = str(self._get_gw_ip(ext_cidr, 2)) if ext_cidr else None
            lport = ovn_nbctl.lswitch_port_add(lswitch["name"], name, mac,
                                               ip_mask, gw, ext_gw)

            ovn_nbctl.lport_set_addresses(name, [mac, ip])
            if port_security:
                ovn_nbctl.lport_set_port_security(name, mac)

            lports.append(lport)

            flush_count -= 1
            if flush_count < 1:
                ovn_nbctl.flush()
                flush_count = batch

        ovn_nbctl.flush()  # ensure all commands be run
        ovn_nbctl.enable_batch_mode(False)
        return lports


    @atomic.action_timer("ovn.delete_lport")
    def _delete_lport(self, lports):
        print("delete lport")
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.enable_batch_mode()
        for lport in lports:
            ovn_nbctl.lport_del(lport["name"])

        ovn_nbctl.flush()
        ovn_nbctl.enable_batch_mode(False)


    @atomic.action_timer("ovn.list_lports")
    def _list_lports(self, lswitches):
        print("list lports")
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        for lswitch in lswitches:
            LOG.info("list lports on lswitch %s" % lswitch["name"])
            ovn_nbctl.lport_list(lswitch["name"])



    @atomic.optional_action_timer("ovn.create_acl")
    def _create_acl(self, lswitch, lports, acl_create_args, acls_per_port):
        sw = lswitch["name"]
        LOG.info("create %d ACLs on %s" % (acls_per_port, sw))

        direction = acl_create_args.get("direction", "to-lport")
        priority = acl_create_args.get("priority", 1000)
        action = acl_create_args.get("action", "allow")
        address_set = acl_create_args.get("address_set", "")
        acl_type = acl_create_args.get("type", "switch")

        '''
        match template: {
            "direction" : "<inport/outport>",
            "lport" : "<switch port or port-group>",
            "address_set" : "<address_set id>"
            "l4_port" : "<l4 port number>",
        }
        '''
        match_template = acl_create_args.get("match",
                                             "%(direction)s == %(lport)s && \
                                             ip4 && udp && udp.src == %(l4_port)s")
        if direction == "from-lport":
            p = "inport"
        else:
            p = "outport"

        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.enable_batch_mode()
        for lport in lports:
            for i in range(acls_per_port):
                match = match_template % { 'direction' : p,
                                           'lport' : lport["name"],
                                           'address_set' : address_set,
                                           'l4_port' : 100 + i }
                ovn_nbctl.acl_add(sw, direction, priority, match, action,
                                  entity = acl_type)
            ovn_nbctl.flush()
        ovn_nbctl.enable_batch_mode(False)


    @atomic.action_timer("ovn.list_acl")
    def _list_acl(self, lswitches):
        LOG.info("list ACLs")
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        for lswitch in lswitches:
            LOG.info("list ACLs on lswitch %s" % lswitch["name"])
            ovn_nbctl.acl_list(lswitch["name"])


    @atomic.action_timer("ovn.delete_all_acls")
    def _delete_all_acls_in_lswitches(self, lswitches):
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.enable_batch_mode()
        for lswitch in lswitches:
            self._delete_acls(lswitch)
        ovn_nbctl.flush()
        ovn_nbctl.enable_batch_mode(False)

    def _delete_acls(self, lswitch, direction=None, priority=None,
                     match=None, flush=False):
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        LOG.info("delete ACLs on lswitch %s" % lswitch["name"])
        ovn_nbctl.acl_del(lswitch["name"], direction, priority, match)
        if flush:
            ovn_nbctl.flush()

    @atomic.optional_action_timer("ovn.pg-add")
    def _port_group_add(self, port_group, port_list):
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        LOG.info("create %s port_group [%s]" % (port_group, port_list))
        ovn_nbctl.port_group_add(port_group, port_list)

    @atomic.optional_action_timer("ovn.pg-set")
    def _port_group_set(self, port_group, port_list):
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        LOG.info("Add %s to port_group %s" % (port_list, port_group))
        ovn_nbctl.port_group_set(port_group, port_list)

    @atomic.optional_action_timer("ovn.pg-add-port")
    def _port_group_add_port(self, port_group, port):
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.enable_batch_mode(False)

        port_uuid = ovn_nbctl.get("logical_switch_port", port, '_uuid')
        ovn_nbctl.add("port_group", port_group, ('ports', ' ', port_uuid))

    @atomic.optional_action_timer("ovn.pg-del")
    def _port_group_del(self, port_group):
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        LOG.info("Delete %s port_group" % port_group)
        ovn_nbctl.port_group_del(port_group, port_list)

    @atomic.action_timer("ovn_network.create_routers")
    def _create_routers(self, router_create_args):
        LOG.info("Create Logical routers")
        return super(OvnScenario, self)._create_routers(router_create_args)

    @atomic.action_timer("ovn_network.delete_routers")
    def _delete_routers(self):
        LOG.info("Delete Logical routers")
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        for lrouter in ovn_nbctl.lrouter_list():
            ovn_nbctl.lrouter_del(lrouter["name"])

    @atomic.action_timer("ovn_network.connect_network_to_router")
    def _connect_networks_to_routers(self, lnetworks, lrouters, networks_per_router):
        super(OvnScenario, self)._connect_networks_to_routers(lnetworks,
                                                              lrouters,
                                                              networks_per_router)

    @atomic.action_timer("ovn_network.connect_gw_routers")
    def _connect_networks_to_gw_routers(self, lnetworks, lrouters, sandboxes,
                                        lnetwork_args, networks_per_router):
        return super(OvnScenario, self)._connect_networks_to_gw_routers(
            lnetworks, lrouters, sandboxes, lnetwork_args, networks_per_router)

    @atomic.action_timer("ovn_network.add_gw_routers_routes_nat")
    def _connect_gw_routers_routes(self, dps, lnetwork_args):
        super(OvnScenario, self)._connect_gw_routers_routes(dps, lnetwork_args)

    @atomic.action_timer("ovn_network.create_phynet")
    def _create_phynet(self, lswitches, physnet, batch):
        LOG.info("Create phynet method: %s" % self.install_method)
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.enable_batch_mode()

        flush_count = batch
        for lswitch in lswitches:
            network = lswitch["name"]
            port = "provnet-%s" % network
            ovn_nbctl.lswitch_port_add(network, port)
            ovn_nbctl.lport_set_addresses(port, ["unknown"])
            ovn_nbctl.lport_set_type(port, "localnet")
            ovn_nbctl.lport_set_options(port, "network_name=%s" % physnet)

            flush_count -= 1
            if flush_count < 1:
                ovn_nbctl.flush()
                flush_count = batch

        ovn_nbctl.flush()
        ovn_nbctl.enable_batch_mode(False)

    # NOTE(huikang): num_networks overides the "amount" in network_create_args
    def _create_networks(self, network_create_args, num_networks=-1):
        physnet = network_create_args.get("physical_network", None)
        lswitches = self._create_lswitches(network_create_args, num_networks)
        batch = network_create_args.get("batch", len(lswitches))

        if physnet != None:
            self._create_phynet(lswitches, physnet, batch)

        return lswitches

    def _create_routed_network(self, lswitch_create_args = {},
                               lnetwork_create_args = {},
                               lport_create_args = {},
                               port_bind_args = {},
                               create_mgmt_port = True):
        lrouters = self.context["datapaths"]["routers"]
        iteration = self.context["iteration"]
        sandboxes = self.context["sandboxes"]

        lswitch_args = copy.copy(lswitch_create_args)
        amount = lswitch_create_args.get('amount', 1)

        sandboxes = [
            sandboxes[i % len(sandboxes)]
                for i in range(iteration * amount, (iteration + 1) * amount)
        ]

        start_cidr = lswitch_create_args.get("start_cidr", "")
        if start_cidr:
            start_cidr = netaddr.IPNetwork(start_cidr)
            cidr = start_cidr.next(iteration * amount)
            lswitch_args["start_cidr"] = str(cidr)
        lswitches = self._create_lswitches(lswitch_args)

        networks_per_router = lnetwork_create_args.get('networks_per_router', 0)
        if networks_per_router:
            self._connect_networks_to_routers(lswitches, lrouters,
                                              networks_per_router)

        port_ext_cidr = None
        if lnetwork_create_args.get('gw_router_per_network', False):
            lnetwork_args = copy.copy(lnetwork_create_args)
            start_gw_cidr = lnetwork_create_args.get("start_gw_cidr", "")
            if start_gw_cidr:
                start_gw_cidr = netaddr.IPNetwork(start_gw_cidr)
                cidr = start_gw_cidr.next(iteration * amount)
                lnetwork_args["start_gw_cidr"] = cidr

            start_ext_cidr = lnetwork_create_args.get("start_ext_cidr", "")
            if start_ext_cidr:
                start_ext_cidr = netaddr.IPNetwork(start_ext_cidr)
                cidr = start_ext_cidr.next(iteration * amount)
                lnetwork_args["start_ext_cidr"] = cidr
                port_ext_cidr = cidr
            dps = \
                self._connect_networks_to_gw_routers(lswitches, lrouters,
                                                     sandboxes, lnetwork_args,
                                                     networks_per_router)
            ext_switches = [ext_switch for _, _, _, _, ext_switch in dps]
            self._create_phynet(ext_switches,
                                lnetwork_args.get('physnet', "providernet"),
                                1)

            self._connect_gw_routers_routes(dps, lnetwork_args)
        else:
            start_ext_cidr = None

        if create_mgmt_port == False:
            return

        lports = self._create_lports(lswitches, lport_create_args,
                                     ext_cidr=port_ext_cidr)
        self._bind_ports_and_wait(lports, sandboxes, port_bind_args)

    def _bind_ports_and_wait(self, lports, sandboxes, port_bind_args):
        port_bind_args = port_bind_args or {}
        wait_up = port_bind_args.get("wait_up", False)
        # "wait_sync" takes effect only if wait_up is True.
        # By default we wait for all HVs catching up with the change.
        wait_sync = port_bind_args.get("wait_sync", "hv")
        if wait_sync.lower() not in ['hv', 'sb', 'ping', 'none']:
            raise exceptions.InvalidConfigException(_(
                "Unknown value for wait_sync: %s. "
                "Only 'hv', 'sb' and 'none' are allowed.") % wait_sync)
        wait_timeout_s = port_bind_args.get("wait_timeout_s", 20)

        LOG.info("Bind lports method: %s" % self.install_method)

        self._bind_ports(lports, sandboxes, port_bind_args)
        if wait_up:
            self._wait_up_port(lports, wait_sync, wait_timeout_s)

    @atomic.action_timer("ovn.bind_ovs_vm")
    def _bind_ovs_port(self, lport_sbs, internal=True):
        for sb_name, (sandbox, lports) in lport_sbs.items():
            farm = sandbox['farm']
            ovs_vsctl = self.farm_clients(farm, "ovs-vsctl")
            ovs_vsctl.set_sandbox(sb_name, self.install_method,
                                  sandbox['host_container'])
            ovs_vsctl.enable_batch_mode()
            for lport in lports:
                port_name = lport["name"]
                LOG.info("bind %s to %s on %s" % (port_name, sb_name, farm))

                ovs_vsctl.add_port('br-int', port_name, internal=internal)
                ovs_vsctl.db_set('Interface', port_name,
                                ('external_ids', {"iface-id":port_name,
                                                  "iface-status":"active"}),
                                ('admin_state', 'up'))
            ovs_vsctl.flush()
            ovs_vsctl.enable_batch_mode(False)

    @atomic.action_timer("ovn.bind_internal_vm")
    def _bind_ovs_internal_vm(self, lport_sbs):
        for sb_name, (sandbox, lports) in lport_sbs.items():
            farm = sandbox['farm']
            ovs_ssh = self.farm_clients(farm, "ovs-ssh")
            ovs_ssh.set_sandbox(sb_name, self.install_method,
                                sandbox['host_container'])
            for lport in lports:
                port_name = lport["name"]
                port_mac = lport["mac"]
                port_ip = lport["ip"]
                port_gw = lport["gw"]
                # TODO: some containers don't have ethtool installed
                if not sandbox["host_container"]:
                    # Disable tx offloading on the port
                    ovs_ssh.run('ethtool -K {p} tx off &> /dev/null'.format(p=port_name))
                ovs_ssh.run('ip netns add {p}'.format(p=port_name))
                ovs_ssh.run('ip link set {p} netns {p}'.format(p=port_name))
                ovs_ssh.run('ip netns exec {p} ip link set {p} address {m}'.format(
                    p=port_name, m=port_mac)
                )
                ovs_ssh.run('ip netns exec {p} ip addr add {ip} dev {p}'.format(
                    p=port_name, ip=port_ip)
                )
                ovs_ssh.run('ip netns exec {p} ip link set {p} up'.format(
                    p=port_name)
                )

                # Add default route.
                ovs_ssh.run('ip netns exec {p} ip route add default via {gw}'.format(
                    p=port_name, gw=port_gw)
                )
                ovs_ssh.flush()

                # Store the port in the context so we can use its information later
                # on or at cleanup
                self.context["ovs-internal-ports"][port_name] = (lport, sandbox)

    def _delete_ovs_internal_vm(self, port_name, ovs_ssh, ovs_vsctl):
        ovs_vsctl.del_port(port_name)
        ovs_ssh.run('ip netns del {p}'.format(p=port_name))

    def _flush_ovs_internal_ports(self, sandbox):
        stdout = StringIO()
        host_container = sandbox["host_container"]
        sb_name = sandbox["name"]
        farm = sandbox["farm"]

        ovs_vsctl = self.farm_clients(farm, "ovs-vsctl")
        ovs_vsctl.set_sandbox(sandbox, self.install_method, host_container)
        ovs_vsctl.run("find interface type=internal", ["--bare", "--columns", "name"], stdout=stdout)
        output = stdout.getvalue()

        ovs_ssh = self.farm_clients(farm, "ovs-ssh")
        ovs_ssh.set_sandbox(sb_name, self.install_method, host_container)

        for name in list(filter(None, output.splitlines())):
            if "lp" not in name:
                continue
            self._delete_ovs_internal_vm(name, ovs_ssh, ovs_vsctl)

    def _cleanup_ovs_internal_ports(self, sandboxes):
        conns = {}
        for sandbox in sandboxes:
            sb_name = sandbox["name"]
            farm = sandbox["farm"]
            host_container = sandbox["host_container"]
            ovs_ssh = self.farm_clients(farm, "ovs-ssh")
            ovs_ssh.set_sandbox(sb_name, self.install_method,
                                host_container)
            ovs_ssh.enable_batch_mode()
            ovs_vsctl = self.farm_clients(farm, "ovs-vsctl")
            ovs_vsctl.set_sandbox(sandbox, self.install_method,
                                  host_container)
            ovs_vsctl.enable_batch_mode()
            conns[sb_name] = (ovs_ssh, ovs_vsctl)

        for _, (lport, sandbox) in self.context["ovs-internal-ports"].items():
            sb_name = sandbox["name"]
            (ovs_ssh, ovs_vsctl) = conns[sb_name]
            self._delete_ovs_internal_vm(lport["name"], ovs_ssh, ovs_vsctl)

        for _, (ovs_ssh, ovs_vsctl) in conns.items():
            ovs_vsctl.flush()
            ovs_ssh.flush()

    @atomic.action_timer("ovn_network.bind_port")
    def _bind_ports(self, lports, sandboxes, port_bind_args):
        internal = port_bind_args.get("internal", False)
        internal_vm = port_bind_args.get("internal_vm", True)
        batch = port_bind_args.get("batch", True)
        sandbox_num = len(sandboxes)
        lport_num = len(lports)
        lport_per_sandbox = int((lport_num + sandbox_num - 1) / sandbox_num)

        lport_sbs = {}
        if len(lports) < len(sandboxes):
            for lport in lports:
                sandbox = random.choice(sandboxes)
                sb_name = sandbox['name']
                _, lports_sb = lport_sbs.get(sb_name, (sandbox, []))
                lport_sbs[sb_name] = (sandbox, lports_sb + [lport])
        else:
            j = 0
            for i in range(j * lport_per_sandbox, len(lports), lport_per_sandbox):
                lport_slice = lports[i : i + lport_per_sandbox]
                for index, lport in enumerate(lport_slice):
                    sandbox = sandboxes[j]
                    sb_name = sandbox['name']
                    _, lports_sb = lport_sbs.get(sb_name, (sandbox, []))
                    lport_sbs[sb_name] = (sandbox, lports_sb + [lport])
                j += 1

        self._bind_ovs_port(lport_sbs, internal)
        if internal and internal_vm:
            self._bind_ovs_internal_vm(lport_sbs)

    def _ping_port(self, lport, wait_timeout_s):
        _, sandbox = self.context["ovs-internal-ports"][lport["name"]]
        ovs_ssh = self.farm_clients(sandbox["farm"], "ovs-ssh")
        ovs_ssh.set_sandbox(sandbox, self.install_method,
                            sandbox['host_container'])
        ovs_ssh.enable_batch_mode(False)

        if lport.get("ext-gw"):
            dest = lport["ext-gw"]
        else:
            dest = lport["gw"]

        start_time = datetime.now()
        while True:
            try:
                ovs_ssh.run("ip netns exec {} ping -q -c 1 -W 0.1 {}".format(
                                lport["name"], dest))
                break
            except:
                pass

            if (datetime.now() - start_time).seconds > wait_timeout_s:
                LOG.info("Timeout waiting for port {} to be able to ping gateway {}".format(
                        lport["name"], lport["gw"]))
                raise exceptions.ThreadTimeoutException()

    @atomic.action_timer("ovn_network.wait_port_lsp_up")
    def _wait_up_port_lsp(self, lports, ovn_nbctl):
        for index, lport in enumerate(lports):
            ovn_nbctl.wait_until('Logical_Switch_Port', lport["name"],
                                 ('up', 'true'))
            if index % 400 == 0:
                ovn_nbctl.flush()
        ovn_nbctl.flush()

    @atomic.action_timer("ovn_network.wait_port_ping")
    def _wait_up_port_ping(self, lports, wait_timeout_s):
        for lport in lports:
            self._ping_port(lport, wait_timeout_s)

    @atomic.action_timer("ovn_network.wait_port_sync")
    def _wait_up_port_sync(self, wait_sync, ovn_nbctl):
        ovn_nbctl.sync(wait_sync)

    def _wait_up_port(self, lports, wait_sync, wait_timeout_s):
        LOG.info("wait port up. sync: %s" % wait_sync)

        if wait_sync == 'ping':
            self._wait_up_port_ping(lports, wait_timeout_s)
        else:
            ovn_nbctl = self._get_ovn_controller(self.install_method)
            ovn_nbctl.enable_batch_mode()
            self._wait_up_port_lsp(lports, ovn_nbctl)
            if wait_sync != 'none':
                self._wait_up_port_sync(wait_sync, ovn_nbctl)
            ovn_nbctl.flush()
            ovn_nbctl.enable_batch_mode(False)

    @atomic.action_timer("ovn_network.list_oflow_count_for_sandboxes")
    def _list_oflow_count_for_sandboxes(self, sandboxes,
                                           sandbox_args):
        oflow_data = []
        for sandbox in sandboxes:
            sandbox_name = sandbox["name"]
            farm = sandbox["farm"]
            host_container = sandbox_name["host_container"]
            ovs_ofctl = self.farm_clients(farm, "ovs-ofctl")
            ovs_ofctl.set_sandbox(sandbox_name, self.install_method,
                                  host_container)
            bridge = sandbox_args.get('bridge', 'br-int')
            lflow_count = ovs_ofctl.dump_flows(bridge)

            LOG.debug('openflow count on %s is %s' % (sandbox_name, lflow_count))
            oflow_data.append([sandbox_name, lflow_count])

        # Leverage additive plot as each sandbox has just one openflow count.
        additive_oflow_data = {
            "title": "Openflow count on each sandbox in StackedArea",
            "description": "Openflow count on each sandbox",
            "chart_plugin": "StackedArea", "data": oflow_data
        }
        self.add_output(additive_oflow_data)

    def _create_address_set(self, set_name, address_list):
        LOG.info("create %s address_set [%s]" % (set_name, address_list))

        name = "name=\"" + set_name + "\""
        addr_list="\"" + address_list + "\""

        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.create("Address_Set", name, ('addresses', addr_list))

    def _address_set_add_addrs(self, set_name, address_list):
        LOG.info("add [%s] to address_set %s" % (address_list, set_name))

        name = "\"" + set_name + "\""
        addr_list="\"" + address_list + "\""

        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.add("Address_Set", name, ('addresses', ' ', addr_list))

    def _address_set_remove_addrs(self, set_name, address_list):
        LOG.info("remove [%s] from address_set %s" % (address_list, set_name))

        name = "\"" + set_name + "\""
        addr_list="\"" + address_list + "\""

        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.remove("Address_Set", name, ('addresses', ' ', addr_list))

    def _list_address_set(self):
        stdout = StringIO()
        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.run("list address_set", ["--bare", "--columns", "name"], stdout=stdout)
        output = stdout.getvalue()
        return output.splitlines()

    def _remove_address_set(self, set_name):
        LOG.info("remove %s address_set" % set_name)

        ovn_nbctl = self._get_ovn_controller(self.install_method)
        ovn_nbctl.destroy("Address_Set", set_name)

    def _get_address_set(self, set_name):
        LOG.info("get %s address_set" % set_name)

        ovn_nbctl = self._get_ovn_controller(self.install_method)
        return ovn_nbctl.get("Address_Set", set_name, 'addresses')

    def runCmd(self, ssh, cmd="", pid_opt="", pid="", background_opt=False):
        ssh.enable_batch_mode(False)

        if pid_opt and pid:
            cmd = cmd + " " + pid_opt + " " + pid

        if background_opt:
            cmd = cmd + " &"

        stdout = StringIO()
        ssh.run(cmd, stdout=stdout)
        return stdout.getvalue().rstrip()

    def runFarmCmd(self, sandbox, cmd="", pid_opt="", pid_proc_name="",
                   background_opt=False):
        LOG.info("running %s on %s" % (cmd, sandbox["name"]))

        ssh = self.farm_clients(sandbox["farm"], "ovs-ssh")
        ssh.set_sandbox(sandbox["name"], self.install_method,
                        sandbox["host_container"])

        if pid_proc_name:
            pid = self.runCmd(ssh, "pidof -s " + pid_proc_name)
        else:
            pid = ""

        self.runCmd(ssh, cmd, pid_opt, pid, background_opt)

    def runControllerCmd(self, cmd="", pid_opt="", pid_proc_name="",
                         background_opt=False):
        LOG.info("running %s on controller-sandbox" % cmd)

        ssh = self.controller_client("ovs-ssh")
        ssh.set_sandbox("controller-sandbox", self.install_method,
                        self.context["controller"]["host_container"])

        if pid_proc_name:
            pid = self.runCmd(ssh, "pidof -s " + pid_proc_name)
        else:
            pid = ""

        self.runCmd(ssh, cmd, pid_opt, pid, background_opt)

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

import sys
import itertools
import logging
import pipes
from io import StringIO
from rally_ovs.plugins.ovs.ovsclients import *
from rally_ovs.plugins.ovs.utils import get_ssh_from_credential
from rally_ovs.plugins.ovs.utils import is_root_credential

LOG = logging.getLogger(__name__)

@configure("ssh")
class SshClient(OvsClient):


    def create_client(self):
        print("*********   call OvnNbctl.create_client")
        return get_ssh_from_credential(self.credential)


@configure("ovn-nbctl")
class OvnNbctl(OvsClient):


    class _OvnNbctl(DdCtlMixin):
        def __init__(self, credential):
            self.ssh = get_ssh_from_credential(credential)
            self.is_root = is_root_credential(credential)
            self.context = {}
            self.sandbox = None
            self.batch_mode = False
            self.cmds = None
            self.socket = None

        def enable_batch_mode(self, value=True):
            self.batch_mode = bool(value)

        def set_sandbox(self, sandbox, install_method="sandbox",
                        host_container=None):
            self.sandbox = sandbox
            self.install_method = install_method
            self.host_container = host_container

        def set_daemon_socket(self, socket=None):
            self.socket = socket

        def run(self, cmd, opts=[], args=[], stdout=sys.stdout,
                stderr=sys.stderr, raise_on_error=True):
            self.cmds = self.cmds or []

            if self.batch_mode:
                cmd = itertools.chain([" -- "], opts, [cmd], args)
                self.cmds.append(" ".join(cmd))
                return

            if self.sandbox:
                sudo_s = "sudo " if not self.is_root else ""
                cmd_prefix = []
                if self.install_method == "sandbox":
                    self.cmds.append(". %s/sandbox.rc" % self.sandbox)
                elif self.install_method == "docker":
                    cmd_prefix = [sudo_s + "docker exec ovn-north-database"]
                elif self.install_method == "physical":
                    if self.host_container:
                        cmd_prefix = [sudo_s + "docker exec " + self.host_container]
                    else:
                        cmd_prefix = [sudo_s]

                if cmd == "exit":
                    if self.socket:
                        ovn_cmd = "ovs-appctl -t " + self.socket
                    else:
                        LOG.error("Called 'ovn-nbctl exit' without daemon mode")
                        return
                elif self.socket:
                    ovn_cmd = "ovn-nbctl -u " + self.socket
                else:
                    ovn_cmd = "ovn-nbctl"

                cmd = itertools.chain(cmd_prefix, [ovn_cmd], opts, [cmd], args)
                self.cmds.append(" ".join(cmd))

            self.ssh.run("\n".join(self.cmds),
                         stdout=stdout, stderr=stderr, raise_on_error=raise_on_error)

            self.cmds = None


        def flush(self):
            if self.cmds == None or len(self.cmds) == 0:
                return

            run_cmds = []
            if self.sandbox:
                sudo_s = "sudo " if not self.is_root else ""
                if self.install_method == "sandbox":
                    run_cmds.append(". %s/sandbox.rc" % self.sandbox)
                    run_cmds.append("ovn-nbctl" + " ".join(self.cmds))
                elif self.install_method == "docker":
                    run_cmds.append(sudo_s + "docker exec ovn-north-database ovn-nbctl " + " ".join(self.cmds))
                elif self.install_method == "physical":
                    if self.host_container:
                        cmd_prefix = sudo_s + "docker exec " + self.host_container
                    else:
                        cmd_prefix = sudo_s

                    if self.socket:
                        ovn_cmd = "ovn-nbctl -u " + self.socket
                    else:
                        ovn_cmd = "ovn-nbctl"

                    run_cmds.append("{} {} {}".format(cmd_prefix, ovn_cmd,
                                                      " ".join(self.cmds)))

            self.ssh.run("\n".join(run_cmds),
                         stdout=sys.stdout, stderr=sys.stderr)

            self.cmds = None


        def db_set(self, table, record, *col_values):
            args = [table, record]
            args += set_colval_args(*col_values)
            self.run("set", args=args)


        def lrouter_port_add(self, lrouter, name, mac=None, ip_addr=None):
            params =[lrouter, name, mac, ip_addr]
            self.run("lrp-add", args=params)
            return {"name":name}


        def lrouter_add(self, name):
            params = [name]
            self.run("lr-add", args=params)
            return {"name":name}

        def lrouter_route_add(self, lrouter, dest, gw, policy=None):
            params = [lrouter, dest, gw]
            if policy:
                opts = ["--policy={}".format(policy)]
            else:
                opts = []
            self.run("lr-route-add", opts=opts, args=params)

        def lrouter_nat_add(self, lrouter, nat_type, external_ip, logical_ip):
            params = [lrouter, nat_type, external_ip, logical_ip]
            self.run("lr-nat-add", args=params)

        def lswitch_add(self, name, other_cfg={}):
            params = [name]


            self.run("ls-add", args=params)

            for cfg, val in other_cfg.items():
                param_cfg = 'other_config:{c}="{v}"'.format(c=cfg, v=val)
                params = ['Logical_Switch', name, param_cfg]
                self.run("set", args=params)

            return {"name":name}

        def lswitch_del(self, name):
            params = [name]
            self.run("ls-del", args=params)


        def lswitch_list(self):
            stdout = StringIO()
            self.run("ls-list", stdout=stdout)
            output = stdout.getvalue()
            return parse_lswitch_list(output)

        def lrouter_list(self):
            stdout = StringIO()
            self.run("lr-list", stdout=stdout)
            output = stdout.getvalue()
            return parse_lswitch_list(output)

        def lrouter_del(self, name):
            params = [name]
            self.run("lr-del", args=params)

        def lswitch_port_add(self, lswitch, name, mac='', ip='', gw='', ext_gw=None):
            params =[lswitch, name]
            self.run("lsp-add", args=params)

            return {"name":name, "mac":mac, "ip":ip, "gw":gw, "ext-gw":ext_gw}


        def lport_list(self, lswitch):
            params =[lswitch]
            self.run("lsp-list", args=params)


        def lport_del(self, name):
            params = [name]
            self.run("lsp-del", args=params)

        '''
        param address: [mac], [mac,ip], [mac,ip1,ip2] ...
        '''
        def lport_set_addresses(self, name, *addresses):
            params = [name]

            for i in addresses:
                i = filter(lambda x: x, i)
                i = "\ ".join(i)
                if i:
                    params += [i]

            self.run("lsp-set-addresses", args=params)


        def lport_set_port_security(self, name, *addresses):
            params = [name]
            params += addresses
            self.run("lsp-set-port-security", args=params)


        def lport_set_type(self, name, type):
            params = [name, type]
            self.run("lsp-set-type", args=params)


        def lport_set_options(self, name, *options):
            params = [name]
            params += options
            self.run("lsp-set-options", args=params)

        def acl_add(self, lswitch, direction, priority, match, action,
                    log=False, entity="switch"):
            opts = ["--log"] if log else []
            opts.append("--type=%s" % entity)
            match = pipes.quote(match)
            params = [lswitch, direction, str(priority), match, action]
            self.run("acl-add", opts, params)

        def acl_list(self, lswitch, entity="switch"):
            opts = ["--type=" + entity]
            params = [lswitch]
            self.run("acl-list", opts, args=params)


        def acl_del(self, lswitch, direction=None,
                    priority=None, match=None, entity="switch"):
            opts = ["--type=" + entity]
            params = [lswitch]
            if direction:
                params.append(direction)
            if priority:
                params.append(priority)
            if match:
                params.append(match)
            self.run("acl-del", opts, args=params)

        def port_group_add(self, port_group, port_list):
            params = [port_group, port_list]
            self.run("pg-add", [], params)

        def port_group_set(self, port_group, port_list):
            params = [port_group, port_list]
            self.run("pg-set-ports", [], params)

        def port_group_del(self, port_group):
            params = [port_group]
            self.run("pg-del", [], params)

        def show(self, lswitch=None):
            params = [lswitch] if lswitch else []
            stdout = StringIO()
            self.run("show", args=params, stdout=stdout)
            output = stdout.getvalue()

            return get_lswitch_info(output)

        def sync(self, wait='hv'):
            # sync command should always be flushed
            opts = ["--wait=%s" % wait]
            batch_mode = self.batch_mode
            if batch_mode:
                self.flush()
                self.batch_mode = False

            self.run("sync", opts)
            self.batch_mode = batch_mode

        def start_daemon(self, nbctld_config):
            stdout = StringIO()
            opts = ["--detach",  "--pidfile", "--log-file"]

            if "remote" in nbctld_config:
                ovn_remote = nbctld_config["remote"]
                prot = nbctld_config["prot"]
                central_ips = [ip.strip() for ip in ovn_remote.split('-')]
                # If there is only one ip, then we can use unixctl socket.
                if len(central_ips) > 1:
                    remote = ",".join(["{}:{}:6641".format(prot, r)
                                      for r in central_ips])
                    opts.append("--db=" + remote)
                    if prot == "ssl":
                        opts.append("-p {} -c {} -C {}".format(
                            nbctld_config["privkey"], nbctld_config["cert"],
                            nbctld_config["cacert"]))

            self.run("", opts=opts, stdout=stdout, raise_on_error=False)
            return stdout.getvalue().rstrip()

        def stop_daemon(self):
            self.run("exit", raise_on_error=False)
            self.socket = None

    def create_client(self):
        print("*********   call OvnNbctl.create_client")

        client = self._OvnNbctl(self.credential)

        return client

@configure("ovn-sbctl")
class OvnSbctl(OvsClient):

    class _OvnSbctl(DdCtlMixin):
        def __init__(self, credential):
            self.ssh = get_ssh_from_credential(credential)
            self.is_root = is_root_credential(credential)
            self.context = {}
            self.sandbox = None
            self.batch_mode = False
            self.cmds = None
            self.sbctl_cmd = "ovn-sbctl --no-leader-only"

        def enable_batch_mode(self, value=True):
            self.batch_mode = bool(value)

        def set_sandbox(self, sandbox, install_method="sandbox",
                        host_container=None):
            self.sandbox = sandbox
            self.install_method = install_method
            self.host_container = host_container

        def run(self, cmd, opts=[], args=[], stdout=sys.stdout, stderr=sys.stderr):
            self.cmds = self.cmds or []

            if self.batch_mode:
                cmd = itertools.chain([" -- "], opts, [cmd], args)
                self.cmds.append(" ".join(cmd))
                return

            if self.sandbox:
                sudo_s = "sudo " if not self.is_root else ""
                cmd_prefix = []
                if self.install_method == "sandbox":
                    self.cmds.append(". %s/sandbox.rc" % self.sandbox)
                elif self.install_method == "docker":
                    cmd_prefix = [sudo_s + "docker exec ovn-north-database"]
                elif self.install_method == "physical":
                    if self.host_container:
                        cmd_prefix = [sudo_s + "docker exec " + self.host_container]
                    else:
                        cmd_prefix = [sudo_s]

                cmd = itertools.chain(cmd_prefix, [self.sbctl_cmd], opts, [cmd], args)
                self.cmds.append(" ".join(cmd))

            self.ssh.run("\n".join(self.cmds),
                         stdout=stdout, stderr=stderr)

            self.cmds = None


        def flush(self):
            if self.cmds == None or len(self.cmds) == 0:
                return

            run_cmds = []
            if self.sandbox:
                sudo_s = "sudo " if not self.is_root else ""
                if self.install_method == "sandbox":
                    run_cmds.append(". %s/sandbox.rc" % self.sandbox)
                    run_cmds.append(self.sbctl_cmd + " ".join(self.cmds))
                elif self.install_method == "docker":
                    run_cmds.append(sudo_s + "docker exec ovn-north-database " + self.sbctl_cmd + " ".join(self.cmds))
                elif self.install_method == "physical":
                    if self.host_container:
                        run_cmds.append(sudo_s + "docker exec " + self.host_container + " " + self.sbctl_cmd  + " ".join(self.cmds))
                    else:
                        run_cmds.append(sudo_s + self.sbctl_cmd + " ".join(self.cmds))

            self.ssh.run("\n".join(run_cmds),
                         stdout=sys.stdout, stderr=sys.stderr)

            self.cmds = None


        def db_set(self, table, record, *col_values):
            args = [table, record]
            args += set_colval_args(*col_values)
            self.run("set", args=args)

        def count_igmp_flows(self, lswitch, network_prefix='239'):
            stdout = StringIO()
            self.ssh.run(
                self.sbctl_cmd + " list datapath_binding | grep {sw} -B 1 | "
                "grep uuid | cut -f 2 -d ':'".format(sw=lswitch),
                stdout=stdout)
            uuid = stdout.getvalue().rstrip()
            stdout = StringIO()
            self.ssh.run(
                self.sbctl_cmd + " list logical_flow | grep 'dst == {nw}' -B 1 | "
                "grep {uuid} -B 1 | wc -l".format(
                uuid=uuid, nw=network_prefix),
                stdout=stdout
            )
            return int(stdout.getvalue())

        def sync(self, wait='hv'):
            # sync command should always be flushed
            opts = ["--wait=%s" % wait]
            batch_mode = self.batch_mode
            if batch_mode:
                self.flush()
                self.batch_mode = False

            self.run("sync", opts)
            self.batch_mode = batch_mode

        def chassis_bound(self, chassis_name):
            batch_mode = self.batch_mode
            if batch_mode:
                self.flush()
                self.batch_mode = False
            stdout = StringIO()
            self.run("find chassis", ["--bare", "--columns _uuid"],
                     ["name={}".format(chassis_name)],
                     stdout=stdout)
            self.batch_mode = batch_mode
            return len(stdout.getvalue().splitlines()) == 1

    def create_client(self):
        print("*********   call OvnSbctl.create_client")

        client = self._OvnSbctl(self.credential)

        return client

@configure("ovs-ssh")
class OvsSsh(OvsClient):

    class _OvsSsh(object):
        def __init__(self, credential):
            self.ssh = get_ssh_from_credential(credential)
            self.is_root = is_root_credential(credential)
            self.batch_mode = False
            self.cmds = None

        def enable_batch_mode(self, value=True):
            self.batch_mode = bool(value)

        def set_sandbox(self, sandbox, install_method="sandbox",
                        host_container=None):
            self.sandbox = sandbox
            self.install_method = install_method
            self.host_container = host_container

        def run(self, cmd, stdout=sys.stdout):
            self.cmds = self.cmds or []

            if self.host_container:
                sudo_s = "sudo " if not self.is_root else ""
                self.cmds.append(sudo_s + 'docker exec ' + self.host_container + ' ' + cmd)
            else:
                self.cmds.append(cmd)

            if self.batch_mode:
                return

            self.flush(stdout)

        def run_immediate(self, cmd, stdout=sys.stdout, stderr=sys.stderr):
            self.ssh.run(cmd, stdout)

        def flush(self, stdout=sys.stdout):
            if self.cmds == None:
                return

            cmds = "\n".join(self.cmds)
            self.cmds = None

            self.ssh.run(cmds, stdout=stdout, stderr=sys.stderr)

    def create_client(self):
        print("*********   call OvsSsh.create_client")
        client = self._OvsSsh(self.credential)
        return client


@configure("ovs-vsctl")
class OvsVsctl(OvsClient):

    class _OvsVsctl(object):

        def __init__(self, credential):
            self.ssh = get_ssh_from_credential(credential)
            self.is_root = is_root_credential(credential)
            self.context = {}
            self.batch_mode = False
            self.sandbox = None
            self.cmds = None

        def enable_batch_mode(self, value=True):
            self.batch_mode = bool(value)

        def set_sandbox(self, sandbox, install_method="sandbox",
                        host_container=None):
            self.sandbox = sandbox
            self.install_method = install_method
            self.host_container = host_container

        def run(self, cmd, opts=[], args=[], extras=[], stdout=sys.stdout, stderr=sys.stderr):
            self.cmds = self.cmds or []

            # TODO: tested with non batch_mode only for docker
            if self.install_method == "docker" or self.host_container:
                self.batch_mode = False

            if self.batch_mode:
                cmd = itertools.chain([" -- "], opts, [cmd], args, extras)
                self.cmds.append(" ".join(cmd))
                return

            sudo_s = "sudo " if not self.is_root else ""
            if self.sandbox and self.batch_mode == False:
                if self.install_method == "sandbox":
                    self.cmds.append(". %s/sandbox.rc" % self.sandbox)
                elif self.install_method == "docker":
                    self.cmds.append(sudo_s + "docker exec %s ovs-vsctl " % \
                                     self.sandbox + cmd + \
                                     " " + " ".join(args) + \
                                     " " + " ".join(extras))

            if self.install_method != "docker":
                if self.host_container:
                    cmd_prefix = [sudo_s + "docker exec " + self.host_container + " ovs-vsctl"]
                else:
                    cmd_prefix = ["ovs-vsctl"]
                cmd = itertools.chain(cmd_prefix, opts, [cmd], args, extras)
                self.cmds.append(" ".join(cmd))

            self.ssh.run("\n".join(self.cmds), stdout=stdout, stderr=stderr)

            self.cmds = None

        def flush(self):
            if self.cmds == None:
                return

            run_cmds = []
            if self.sandbox:
                if self.install_method == "sandbox":
                    run_cmds.append(". %s/sandbox.rc" % self.sandbox)
                    run_cmds.append("ovs-vsctl" + " ".join(self.cmds))

            self.ssh.run("\n".join(run_cmds),
                         stdout=sys.stdout, stderr=sys.stderr)

            self.cmds = None


        def add_port(self, bridge, port, may_exist=True, internal=False):
            opts = ['--may-exist'] if may_exist else []
            extras = ['--', 'set interface {} type=internal'.format(port)] if internal else []
            self.run('add-port', opts, [bridge, port], extras)

        def del_port(self, port):
            self.run('del-port', args=[port])

        def db_set(self, table, record, *col_values):
            args = [table, record]
            args += set_colval_args(*col_values)
            self.run("set", args=args)

    def create_client(self):
        print("*********   call OvsVsctl.create_client")
        client = self._OvsVsctl(self.credential)
        return client



@configure("ovs-ofctl")
class OvsOfctl(OvsClient):

    class _OvsOfctl(object):

        def __init__(self, credential):
            self.ssh = get_ssh_from_credential(credential)
            self.is_root = is_root_credential(credential)
            self.context = {}
            self.sandbox = None

        def set_sandbox(self, sandbox, install_method="sandbox",
                        host_container=None):
            self.sandbox = sandbox
            self.install_method = install_method
            self.host_container = host_container

        def run(self, cmd, opts=[], args=[], stdout=sys.stdout, stderr=sys.stderr):
            # TODO: add support for docker
            cmds = []

            if self.sandbox:
                if self.install_method == "sandbox":
                    cmds.append(". %s/sandbox.rc" % self.sandbox)

            if self.install_method == "physical" and self.host_container:
                sudo_s = "sudo " if not self.is_root else ""
                cmd_prefix = [sudo_s + "docker exec " + self.host_container + " ovs-ofctl"]
            else:
                cmd_prefix = ["ovs-ofctl"]
            cmd = itertools.chain(cmd_prefix, opts, [cmd], args)
            cmds.append(" ".join(cmd))
            self.ssh.run("\n".join(cmds),
                         stdout=stdout, stderr=stderr)

        def dump_flows(self, bridge):
            stdout = StringIO()
            opts = []
            self.run("dump-flows", opts, [bridge], stdout=stdout)
            oflow_data = stdout.getvalue().strip()
            oflow_data = oflow_data.split('\n')
            return len(oflow_data)

    def create_client(self):
        print("*********   call OvsOfctl.create_client")
        client = self._OvsOfctl(self.credential)
        return client

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
import pipes
from io import StringIO
from rally_ovs.plugins.ovs.ovsclients import *
from rally_ovs.plugins.ovs.utils import get_ssh_from_credential

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
                cmd_prefix = []
                if self.install_method == "sandbox":
                    self.cmds.append(". %s/sandbox.rc" % self.sandbox)
                elif self.install_method == "docker":
                    cmd_prefix = ["sudo docker exec ovn-north-database"]
                elif self.install_method == "physical":
                    if self.host_container:
                        cmd_prefix = ["sudo docker exec " + self.host_container]
                    else:
                        cmd_prefix = ["sudo"]

                if cmd == "exit":
                    cmd_prefix.append("  ovs-appctl -t ")

                if self.socket:
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
                if self.install_method == "sandbox":
                    run_cmds.append(". %s/sandbox.rc" % self.sandbox)
                    run_cmds.append("ovn-nbctl" + " ".join(self.cmds))
                elif self.install_method == "docker":
                    run_cmds.append("sudo docker exec ovn-north-database ovn-nbctl " + " ".join(self.cmds))
                elif self.install_method == "physical":
                    if self.host_container:
                        cmd_prefix = "sudo docker exec " + self.host_container + " ovn-nbctl"
                    else:
                        cmd_prefix = "sudo ovn-nbctl"

                    run_cmds.append(cmd_prefix + " ".join(self.cmds))

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

        def lswitch_port_add(self, lswitch, name, mac='', ip=''):
            params =[lswitch, name]
            self.run("lsp-add", args=params)

            return {"name":name, "mac":mac, "ip":ip}


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
                    log=False):
            opts = ["--log"] if log else []
            match = pipes.quote(match)
            params = [lswitch, direction, str(priority), match, action]
            self.run("acl-add", opts, params)

        def acl_list(self, lswitch):
            params = [lswitch]
            self.run("acl-list", args=params)


        def acl_del(self, lswitch, direction=None,
                    priority=None, match=None):
            params = [lswitch]
            if direction:
                params.append(direction)
            if priority:
                params.append(priority)
            if match:
                params.append(match)
            self.run("acl-del", args=params)

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

        def start_daemon(self):
            stdout = StringIO()
            opts = ["--detach",  "--pidfile", "--log-file"]
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
            self.context = {}
            self.sandbox = None
            self.batch_mode = False
            self.cmds = None

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
                cmd_prefix = []
                if self.install_method == "sandbox":
                    self.cmds.append(". %s/sandbox.rc" % self.sandbox)
                elif self.install_method == "docker":
                    cmd_prefix = ["sudo docker exec ovn-north-database"]
                elif self.install_method == "physical":
                    if self.host_container:
                        cmd_prefix = ["sudo docker exec " + self.host_container]
                    else:
                        cmd_prefix = ["sudo"]

                cmd = itertools.chain(cmd_prefix, ["ovn-sbctl"], opts, [cmd], args)
                self.cmds.append(" ".join(cmd))

            self.ssh.run("\n".join(self.cmds),
                         stdout=stdout, stderr=stderr)

            self.cmds = None


        def flush(self):
            if self.cmds == None or len(self.cmds) == 0:
                return

            run_cmds = []
            if self.sandbox:
                if self.install_method == "sandbox":
                    run_cmds.append(". %s/sandbox.rc" % self.sandbox)
                    run_cmds.append("ovn-sbctl" + " ".join(self.cmds))
                elif self.install_method == "docker":
                    run_cmds.append("sudo docker exec ovn-north-database ovn-sbctl " + " ".join(self.cmds))
                elif self.install_method == "physical":
                    if self.host_container:
                        run_cmds.append("sudo docker exec " + self.host_container + " ovn-sbctl" + " ".join(self.cmds))
                    else:
                        run_cmds.append("sudo ovn-sbctl" + " ".join(self.cmds))

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
                "ovn-sbctl list datapath_binding | grep {sw} -B 1 | "
                "grep uuid | cut -f 2 -d ':'".format(sw=lswitch),
                stdout=stdout)
            uuid = stdout.getvalue().rstrip()
            stdout = StringIO()
            self.ssh.run(
                "ovn-sbctl list logical_flow | grep 'dst == {nw}' -B 1 | "
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
            self.batch_mode = False
            self.cmds = None

        def enable_batch_mode(self, value=True):
            self.batch_mode = bool(value)

        def set_sandbox(self, sandbox, install_method="sandbox",
                        host_container=None):
            self.sandbox = sandbox
            self.install_method = install_method
            self.host_container = host_container

        def run(self, cmd):
            self.cmds = self.cmds or []

            if self.host_container:
                self.cmds.append('sudo docker exec ' + self.host_container + ' ' + cmd)
            else:
                self.cmds.append(cmd)

            if self.batch_mode:
                return

            self.flush()

        def run_immediate(self, cmd, stdout=sys.stdout, stderr=sys.stderr):
            self.ssh.run(cmd, stdout)

        def flush(self):
            if self.cmds == None:
                return

            self.ssh.run("\n".join(self.cmds),
                         stdout=sys.stdout, stderr=sys.stderr)

            self.cmds = None

    def create_client(self):
        print("*********   call OvsSsh.create_client")
        client = self._OvsSsh(self.credential)
        return client


@configure("ovs-vsctl")
class OvsVsctl(OvsClient):

    class _OvsVsctl(object):

        def __init__(self, credential):
            self.ssh = get_ssh_from_credential(credential)
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
            if self.install_method == "docker":
                self.batch_mode = False

            if self.sandbox and self.batch_mode == False:
                if self.install_method == "sandbox":
                    self.cmds.append(". %s/sandbox.rc" % self.sandbox)
                elif self.install_method == "docker":
                    self.cmds.append("sudo docker exec %s ovs-vsctl " % \
                                     self.sandbox + cmd + \
                                     " " + " ".join(args) + \
                                     " " + " ".join(extras))

            if self.install_method != "docker":
                if self.host_container:
                    cmd_prefix = ["sudo docker exec " + self.host_container + " ovs-vsctl"]
                else:
                    cmd_prefix = ["ovs-vsctl"]
                cmd = itertools.chain(cmd_prefix, opts, [cmd], args, extras)
                self.cmds.append(" ".join(cmd))

            if self.batch_mode:
                return

            self.ssh.run("\n".join(self.cmds), stdout=stdout, stderr=stderr)

            self.cmds = None

        def flush(self):
            if self.cmds == None:
                return

            if self.sandbox:
                if self.install_method == "sandbox":
                    self.cmds.insert(0, ". %s/sandbox.rc" % self.sandbox)

            self.ssh.run("\n".join(self.cmds),
                         stdout=sys.stdout, stderr=sys.stderr)

            self.cmds = None


        def add_port(self, bridge, port, may_exist=True, internal=False):
            opts = ['--may-exist'] if may_exist else None
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
                cmd_prefix = ["sudo docker exec " + self.host_container + " ovs-ofctl"]
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

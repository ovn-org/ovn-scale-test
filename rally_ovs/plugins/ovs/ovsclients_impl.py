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
        print "*********   call OvnNbctl.create_client"
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


        def close(self):
            self.ssh.close()


        def enable_batch_mode(self, value=True):
            self.batch_mode = bool(value)

        def set_sandbox(self, sandbox, install_method="sandbox"):
            self.sandbox = sandbox
            self.install_method = install_method

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

                cmd = itertools.chain(cmd_prefix, ["ovn-nbctl"], opts, [cmd], args)
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
                    run_cmds.append("ovn-nbctl" + " ".join(self.cmds))
                elif self.install_method == "docker":
                    run_cmds.append("sudo docker exec ovn-north-database ovn-nbctl " + " ".join(self.cmds))

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


        def lswitch_add(self, name):
            params = [name]


            self.run("ls-add", args=params)

            return {"name":name}

        def lswitch_del(self, name):
            params = [name]
            self.run("ls-del", args=params)


        def lswitch_list(self):
            stdout = StringIO()
            self.run("ls-list", stdout=stdout)
            output = stdout.getvalue()
            return parse_lswitch_list(output)

        def lswitch_port_add(self, lswitch, name):
            params =[lswitch, name]
            self.run("lsp-add", args=params)

            return {"name":name}


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


        def acl_del(self, lswitch):
            params = [lswitch]
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

    def create_client(self):
        print "*********   call OvnNbctl.create_client"

        client = self._OvnNbctl(self.credential)

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


        def close(self):
            self.ssh.close()


        def enable_batch_mode(self, value=True):
            self.batch_mode = bool(value)

        def set_sandbox(self, sandbox, install_method="sandbox"):
            self.sandbox = sandbox
            self.install_method = install_method

        def run(self, cmd, opts=[], args=[]):
            self.cmds = self.cmds or []

            # TODO: tested with non batch_mode only for docker
            if self.install_method == "docker":
                self.batch_mode = False

            if self.sandbox and self.batch_mode == False:
                if self.install_method == "sandbox":
                    self.cmds.append(". %s/sandbox.rc" % self.sandbox)
                elif self.install_method == "docker":
                    self.cmds.append("sudo docker exec %s ovs-vsctl " % self.sandbox + cmd + " " + " ".join(args))

            if self.install_method != "docker":
                cmd = itertools.chain(["ovs-vsctl"], opts, [cmd], args)
                self.cmds.append(" ".join(cmd))

            if self.batch_mode:
                return

            self.ssh.run("\n".join(self.cmds),
                         stdout=sys.stdout, stderr=sys.stderr)

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


        def add_port(self, bridge, port, may_exist=True):
            opts = ['--may-exist'] if may_exist else None
            self.run('add-port', opts, [bridge, port])


        def db_set(self, table, record, *col_values):
            args = [table, record]
            args += set_colval_args(*col_values)
            self.run("set", args=args)

    def create_client(self):
        print "*********   call OvsVsctl.create_client"
        client = self._OvsVsctl(self.credential)
        return client



@configure("ovs-ofctl")
class OvsOfctl(OvsClient):

    class _OvsOfctl(object):

        def __init__(self, credential):
            self.ssh = get_ssh_from_credential(credential)
            self.context = {}
            self.sandbox = None

        def set_sandbox(self, sandbox, install_method="sandbox"):
            self.sandbox = sandbox
            self.install_method = install_method

        def run(self, cmd, opts=[], args=[], stdout=sys.stdout, stderr=sys.stderr):
            # TODO: add support for docker
            cmds = []

            if self.sandbox:
                if self.install_method == "sandbox":
                    cmds.append(". %s/sandbox.rc" % self.sandbox)

            cmd = itertools.chain(["ovs-ofctl"], opts, [cmd], args)
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
        print "*********   call OvsOfctl.create_client"
        client = self._OvsOfctl(self.credential)
        return client

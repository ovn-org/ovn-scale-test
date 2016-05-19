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
                if self.install_method == "sandbox":
                    self.cmds.append(". %s/sandbox.rc" % self.sandbox)
                    cmd = itertools.chain(["ovn-nbctl"], opts, [cmd], args)
                    self.cmds.append(" ".join(cmd))
                elif self.install_method == "docker":
                    self.cmds.append("sudo docker exec ovn-database ovn-nbctl " + cmd + " " + " ".join(args))

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
                    run_cmds.append("sudo docker exec ovn-database ovn-nbctl " + " ".join(self.cmds))

            self.ssh.run("\n".join(run_cmds),
                         stdout=sys.stdout, stderr=sys.stderr)

            self.cmds = None


        def lswitch_add(self, name):
            params = [name]


            self.run("lswitch-add", args=params)

            return {"name":name}

        def lswitch_del(self, name):
            params = [name]
            self.run("lswitch-del", args=params)



        def lswitch_list(self):
            self.run("lswitch-list")

        def lport_add(self, lswitch, name):
            params =[lswitch, name]
            self.run("lport-add", args=params)

            return {"name":name}


        def lport_list(self, lswitch):
            params =[lswitch]
            self.run("lport-list", args=params)


        def lport_del(self, name):
            params = [name]
            self.run("lport-del", args=params)

        '''
        param address: [mac,ip], [mac] ...
        '''
        def lport_set_addresses(self, name, *addresses):
            params = [name]

            for i in addresses:
                params += ["\ ".join(i)]

            self.run("lport-set-addresses", args=params)


        def lport_set_port_security(self, name, *addresses):
            params = [name]
            params += addresses
            self.run("lport-set-port-security", args=params)


        def lport_set_type(self, name, type):
            params = [name, type]
            self.run("lport-set-type", args=params)


        def lport_set_options(self, name, *options):
            params = [name]
            params += options
            self.run("lport-set-options", args=params)

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
                    cmd = itertools.chain(["ovs-vsctl"], opts, [cmd], args)
                    self.cmds.append(" ".join(cmd))
                elif self.install_method == "docker":
                    self.cmds.append("sudo docker exec %s ovs-vsctl " % self.sandbox + cmd + " " + " ".join(args))

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
        print "*********   call OvnNbctl.create_client"
        client = self._OvsVsctl(self.credential)
        return client

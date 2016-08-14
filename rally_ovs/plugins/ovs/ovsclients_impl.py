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

import pipes
import sys
import itertools
import StringIO
from rally.common import logging
from rally_ovs.plugins.ovs.ovsclients import *
from rally_ovs.plugins.ovs.utils import get_ssh_from_credential

LOG = logging.getLogger(__name__)

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
                    self.cmds.append("sudo docker exec ovn-north-database ovn-nbctl " + cmd + " " + " ".join(args))

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


        def lswitch_add(self, name):
            params = [name]


            self.run("ls-add", args=params)

            return {"name":name}

        def lswitch_del(self, name):
            params = [name]
            self.run("ls-del", args=params)



        def lswitch_list(self):
            self.run("ls-list")

        def lport_add(self, lswitch, name):
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
        param address: [mac,ip], [mac] ...
        '''
        def lport_set_addresses(self, name, *addresses):
            params = [name]

            for i in addresses:
                params += ["\ ".join(i)]

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
            stdout = StringIO.StringIO()
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

        def run(self, ovs_cmd, cmd, opts=[], args=[], stdout=sys.stdout):
            self.cmds = self.cmds or []

            # TODO: tested with non batch_mode only for docker
            if self.install_method == "docker":
                self.batch_mode = False

            if self.sandbox and self.batch_mode == False:
                if self.install_method == "sandbox":
                    self.cmds.append(". %s/sandbox.rc" % self.sandbox)
                    cmd = itertools.chain([ovs_cmd], opts, [cmd], args)
                    self.cmds.append(" ".join(cmd))
                elif self.install_method == "docker":
                    self.cmds.append("sudo docker exec %s " % self.sandbox + " "
                                     + ovs_cmd + " " + cmd + " " + " ".join(args))

            if self.batch_mode:
                return

            self.ssh.run("\n".join(self.cmds),
                         stdout=stdout, stderr=sys.stderr)

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
            self.run("ovs-vsctl", 'add-port', opts, [bridge, port])


        def db_set(self, table, record, *col_values):
            args = [table, record]
            args += set_colval_args(*col_values)
            self.run("ovs-vsctl", "set", args=args)

        def of_check(self, bridge, port, mac_addr, may_exist=True):
            in_port = ""
            stdout = StringIO.StringIO()
            self.run("ovs-ofctl", "show br-int", stdout=stdout)
            show_br_int_output = stdout.getvalue()
            in_port = get_of_in_port(show_br_int_output, port)
            LOG.info("Check port: in_port: %s; mac: %s" % (in_port.strip(), mac_addr))
            appctl_cmd = " ofproto/trace br-int in_port=" + in_port.strip()
            appctl_cmd += ",dl_src=" + mac_addr
            appctl_cmd += ",dl_dst=00:00:00:00:00:03 -generate "
            self.run("ovs-appctl", appctl_cmd, stdout=stdout)
            of_trace_output = stdout.getvalue()

            # NOTE(HuiKang): if success, the flow goes through table 1 to table
            # 32. However, since we use sandbox, table 32 seems not setup
            # correctly. Therefore after table 34, the datapath action is
            # Datapath actions: 100. If failed, the datapatch action is "drop"
            for line in of_trace_output.splitlines():
                if (line.find("Datapath actions") >= 0):
                    if (line.find("drop") >= 0):
                        return False
            return True

    def create_client(self):
        print "*********   call OvnNbctl.create_client"
        client = self._OvsVsctl(self.credential)
        return client

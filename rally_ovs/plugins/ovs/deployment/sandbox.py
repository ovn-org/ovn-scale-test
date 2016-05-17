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
from six.moves.urllib import parse


from rally.deployment import engine # XXX: need a ovs one?

from rally_ovs.plugins.ovs.deployment.engines import get_script
from rally_ovs.plugins.ovs.deployment.engines import get_script_path
from rally_ovs.plugins.ovs.deployment.engines import get_updated_server
from rally_ovs.plugins.ovs.deployment.engines import OVS_USER
from rally_ovs.plugins.ovs.deployment.engines import OVS_REPO
from rally_ovs.plugins.ovs.deployment.engines import OVS_BRANCH



class SandboxEngine(engine.Engine):
    """ base engine
    """


    def __init__(self, deployment):
        super(SandboxEngine, self).__init__(deployment)


    '''
        create user in host if necessary

        :param user A user name used to run test, give it sudo premission with
                    no password.
    '''
    def _prepare(self, server, user):
        server.ssh.run("/bin/bash -e -s %s" % user, stdin=get_script("prepare.sh"),
                            stdout=sys.stdout, stderr=sys.stderr);

        if server.password:
            server.ssh.run("chpasswd",
                           stdin="%s:%s" % (user, server.password))


    def _put_file(self, server, filename):
        localpath = get_script_path(filename)
        server.ssh.put_file(localpath, filename)



    '''
        install ovs from source code as
    '''
    def _install_ovs(self, server):
        ovs_repo = self.config.get("ovs_repo", OVS_REPO)
        ovs_branch = self.config.get("ovs_branch", OVS_BRANCH)
        ovs_user = self.config.get("ovs_user", OVS_USER)
        repo_action = self.config.get("repo_action", "")

        http_proxy = self.config.get("http_proxy", None)
        https_proxy = self.config.get("https_proxy", None)

        ovs_server = get_updated_server(server, user=ovs_user)
        self._put_file(ovs_server, "install.sh")
        self._put_file(ovs_server, "ovs-sandbox.sh")


        cmds = []
        if http_proxy or https_proxy :
            cmd = '''cat > proxy_env.sh <<EOF
export http_proxy=%s
export https_proxy=%s
EOF''' % (http_proxy, https_proxy)
            cmds.append(cmd)
            cmds.append("echo 'use http proxy in proxy_env.sh'")
            cmds.append(". proxy_env.sh")


        cmd = "./install.sh %s %s %s %s" % (ovs_repo, ovs_branch, ovs_user, repo_action)
        cmds.append(cmd)
        print("install ovs:", cmds)
        ovs_server.ssh.run("\n".join(cmds),
                            stdout=sys.stdout, stderr=sys.stderr);




    def _deploy(self, server, install_method="sandbox"):

        ovs_user = self.config.get("ovs_user", OVS_USER)
        self._prepare(server, ovs_user)

        if install_method == "sandbox":
            self._install_ovs(server)










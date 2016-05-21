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
import netaddr
import six
from collections import defaultdict

from rally import exceptions
from rally_ovs.plugins.ovs import scenario
from rally.task import atomic
from rally.common import logging
from rally.common import objects

from netaddr.ip import IPRange
from rally_ovs.plugins.ovs.consts import ResourceType

LOG = logging.getLogger(__name__)


class SandboxScenario(scenario.OvsScenario):


    def _add_controller_resource(self, deployment, controller_cidr):
        dep = objects.Deployment.get(deployment)
        resources = dep.get_resources(type=ResourceType.CONTROLLER)
        if resources == None:
            dep.add_resource(provider_name=deployment,
                            type=ResourceType.CONTROLLER,
                            info={"ip":controller_cidr.split('/')[0],
                                  "deployment_name":deployment})
            return

        resources[0].update({"info": {"ip":controller_cidr.split('/')[0],
                                        "deployment_name":deployment}})
        resources[0].save()



    def _create_controller(self, dep_name, controller_cidr, net_dev):

        cmd = "./ovs-sandbox.sh --controller --ovn \
                            --controller-ip %s --device %s;" % \
                            (controller_cidr, net_dev)
        ssh = self.controller_client()
        ssh.run(cmd, stdout=sys.stdout, stderr=sys.stderr)

        self._add_controller_resource(dep_name, controller_cidr)



    """
        @param farm_dep  A name or uuid of farm deployment
        @param sandboxes A list of 'sandbox:tag' dict, e.g.
                         "sandbox-192.168.64.1": "ToR1"
    """
    def _add_sandbox_resource(self, farm_dep, sandboxes):
        dep = objects.Deployment.get(farm_dep)
        res = dep.get_resources(type=ResourceType.SANDBOXES)[0]

        info = res["info"]
        sandbox_set = set(info["sandboxes"])
        sandbox_set |= set(sandboxes)


        for i in sandbox_set:
            if sandboxes.has_key(i):
                continue
            sandboxes[i] = info["sandboxes"][i]


        info["sandboxes"] = sandboxes
        res.update({"info": info})
        res.save()


    """
        @param farm_dep  A name or uuid of farm deployment
        @param sandboxes A list of sandboxes' name
    """
    def _delete_sandbox_resource(self, farm_dep, to_delete):
        dep = objects.Deployment.get(farm_dep)
        res = dep.get_resources(type=ResourceType.SANDBOXES)[0]

        info = res["info"]
        sandboxes = info["sandboxes"]
        for i in to_delete:
            if info["sandboxes"].has_key(i):
                del info["sandboxes"][i]

        info["sandboxes"] = sandboxes
        res.update({"info": info})
        res.save()


    @atomic.action_timer("sandbox.create_sandbox")
    def _do_create_sandbox(self, ssh, cmds):
        ssh.run("\n".join(cmds), stdout=sys.stdout, stderr=sys.stderr);


    def _create_sandbox(self, sandbox_create_args):
        """
        :param sandbox_create_args from task config file
        """

        print("create sandbox")

        amount = sandbox_create_args.get("amount", 1)
        batch = sandbox_create_args.get("batch", 1)

        farm = sandbox_create_args.get("farm")
        controller_ip = self.context["controller"]["ip"]

        start_cidr = sandbox_create_args.get("start_cidr")
        net_dev = sandbox_create_args.get("net_dev", "eth0")
        tag = sandbox_create_args.get("tag", "")

        LOG.info("-------> Create sandbox  method: %s" % self.install_method)
        install_method = self.install_method

        if controller_ip == None:
            raise exceptions.NoSuchConfigField(name="controller_ip")

        sandbox_cidr = netaddr.IPNetwork(start_cidr)
        end_ip = sandbox_cidr.ip + amount
        if not end_ip in sandbox_cidr:
            message = _("Network %s's size is not big enough for %d sandboxes.")
            raise exceptions.InvalidConfigException(
                        message  % (start_cidr, amount))


        sandbox_hosts = netaddr.iter_iprange(sandbox_cidr.ip, sandbox_cidr.last)

        ssh = self.farm_clients(farm)


        sandboxes = {}
        batch_left = min(batch, amount)
        i = 0
        while i < amount:

            i += batch_left
            host_ip_list = []
            while batch_left > 0:
                host_ip_list.append(str(sandbox_hosts.next()))
                batch_left -= 1

            cmds = []
            for host_ip in host_ip_list:
                cmd = "./ovs-sandbox.sh --ovn --controller-ip %s \
                             --host-ip %s/%d --device %s" % \
                         (controller_ip, host_ip, sandbox_cidr.prefixlen,
                                net_dev)
                cmds.append(cmd)

                sandboxes["sandbox-%s" % host_ip] = tag

            if install_method == "docker":
                print "Do not run ssh; sandbox installed by ansible-docker"
            elif install_method == "sandbox":
                self._do_create_sandbox(ssh, cmds)
            else:
                print "Invalid install method for controller"
                exit(1)

            batch_left = min(batch, amount - i)
            if batch_left <= 0:
                break;

        self._add_sandbox_resource(farm, sandboxes)

        return sandboxes


    @atomic.action_timer("sandbox.delete_sandbox")
    def _delete_sandbox(self, sandboxes, graceful=False):
        print("delete sandbox")

        graceful = "--graceful" if graceful else ""

        farm_map = defaultdict(list)
        for i in sandboxes:
            farm_map[i["farm"]].append(i["name"])

        for k,v in six.iteritems(farm_map):
            ssh = self.farm_clients(k)

            cmds = []
            to_delete = []
            for sandbox in v:
                cmd = "./ovs-sandbox.sh --ovn %s --cleanup  %s" % \
                        (graceful, sandbox)
                cmds.append(cmd)
                to_delete.append(sandbox)

            ssh.run("\n".join(cmds), stdout=sys.stdout, stderr=sys.stderr);

            self._delete_sandbox_resource(k, to_delete)


    @atomic.action_timer("sandbox.start_sandbox")
    def _start_sandbox(self, sandboxes):

        for sandbox in sandboxes:
            name = sandbox["name"]
            ssh = self.farm_clients(sandbox["farm"])
            LOG.info("Start sandbox %s on %s" % (name, sandbox["farm"]))
            cmd = "./ovs-sandbox.sh --ovn --start %s" % name
            ssh.run(cmd, stdout=sys.stdout, stderr=sys.stderr);


    @atomic.action_timer("sandbox.stop_sandbox")
    def _stop_sandbox(self, sandboxes, graceful=False):

        graceful = "--graceful" if graceful else ""

        for sandbox in sandboxes:
            ssh = self.farm_clients(sandbox["farm"])
            name = sandbox["name"]
            LOG.info("Stop sandbox %s on %s" % (name, sandbox["farm"]))
            cmd = "./ovs-sandbox.sh --ovn %s --stop  %s" % \
                    (graceful, name)
            ssh.run(cmd, stdout=sys.stdout, stderr=sys.stderr);

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


import six
from six.moves.urllib import parse

from rally.common import db
from rally.common import objects
from rally import consts
from rally.deployment import engine


import rally

@engine.configure(name="OvnMultihostEngine")
class OvnMultihostEngine(engine.Engine):
    """Deploy multihost cloud with existing engines.


    """
    def __init__(self, *args, **kwargs):
        super(OvnMultihostEngine, self).__init__(*args, **kwargs)
        self.config = self.deployment["config"]
        self.nodes = []


    def _deploy_node(self, config, name):
        deployment = objects.Deployment(config=config,
                                        parent_uuid=self.deployment["uuid"])
        deployment.update_name(name)
        deployer = engine.Engine.get_engine(config["type"], deployment)
        with deployer:
            credentials = deployer.make_deploy()
        return deployer, credentials



    def deploy(self):
        self.deployment.update_status(consts._DeployStatus.DEPLOY_SUBDEPLOY)

        controller_config = self.config["controller"]
        name = controller_config.get("deployment_name",
                                     "%s-controller" % self.deployment["name"])
        self.controller, self.credentials = self._deploy_node(
                    controller_config, name)


        if "nodes" in self.config:
            for i in range(len(self.config["nodes"])):
                node_config = self.config["nodes"][i]

                name = node_config.get("deployment_name",
                            "%s-node-%d" % (self.deployment["name"], i))
                node, credential = self._deploy_node(node_config, name)
                self.nodes.append(node)

        return self.credentials


    def cleanup(self):
        subdeploys = db.deployment_list(parent_uuid=self.deployment["uuid"])
        subdeploys.reverse() # destroy in reversed order
        for subdeploy in subdeploys:
            rally.api.Deployment.destroy(subdeploy["uuid"])



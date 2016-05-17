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


import copy

from rally.common.i18n import _
from rally.common import logging
from rally.common import db
from rally import consts
from rally import exceptions
from rally.task import context
from rally_ovs.plugins.ovs.consts import ResourceType
from rally_ovs.plugins.ovs import utils

LOG = logging.getLogger(__name__)



def get_ovn_multihost_info(deploy_uuid, controller_name):

    deployments = db.deployment_list(parent_uuid=deploy_uuid)

    multihost_info = {"controller" : {}, "farms" : {}, "install_method" : "sandbox"}

    for dep in deployments:
        cred = db.resource_get_all(dep["uuid"], type=ResourceType.CREDENTIAL)[0]
        cred = copy.deepcopy(cred.info)
        name = dep["name"]

        info = { "name" : name, "credential" :  cred}

        if name == controller_name:
            multihost_info["controller"][name] = info
        else:
            multihost_info["farms"][name] = info

        if 'install_method' in dep.config:
            multihost_info["install_method"] = dep.config["install_method"]

    return multihost_info


@context.configure(name="ovn_multihost", order=110)
class OvnMultihost(context.Context):

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "properties": {
        },
        "additionalProperties": True
    }

    DEFAULT_CONFIG = {
    }

    @logging.log_task_wrapper(LOG.info, _("Enter context: `ovn_multihost`"))
    def setup(self):

        multihost_uuid = self.task["deployment_uuid"]
        controller_name = self.config["controller"]

        multihost_info = get_ovn_multihost_info(multihost_uuid, controller_name)
        self.context["ovn_multihost"] = multihost_info

        try:
            controller_dep = db.deployment_get(controller_name)
        except exceptions.DeploymentNotFound:
            raise

        try:
            res = db.resource_get_all(controller_dep["uuid"],
                                        type=ResourceType.CONTROLLER)[0]
        except:
            raise exceptions.GetResourceNotFound(resource="controller")


        self.context["controller"] = res["info"]



    @logging.log_task_wrapper(LOG.info, _("Exit context: `ovn_multihost`"))
    def cleanup(self):
        pass




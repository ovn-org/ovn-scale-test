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
from rally.common.i18n import _
from rally.common import logging
from rally.common import db
from rally import consts
from rally.task import context

from rally_ovs.plugins.ovs.consts import ResourceType

LOG = logging.getLogger(__name__)




@context.configure(name="sandbox", order=110)
class Sandbox(context.Context):
    """Context for xxxxx."""

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "properties": {
            "farm": {
                "type": "string"
            },
            "tag": {
                "type": "string"
            }
        },
        "additionalProperties": True
    }

    DEFAULT_CONFIG = {
    }

    @logging.log_task_wrapper(LOG.info, _("Enter context: `sandbox`"))
    def setup(self):

        LOG.debug("Setup ovn sandbox context")
        deploy_uuid = self.task["deployment_uuid"]
        deployments = db.deployment_list(parent_uuid=deploy_uuid)

        farm = self.config.get("farm", "")
        tag = self.config.get("tag", "")

        sandboxes = []
        for dep in deployments:
            res = db.resource_get_all(dep["uuid"], type=ResourceType.SANDBOXES)
            if len(res) == 0 or len(res[0].info["sandboxes"]) == 0:
                continue

            info = res[0].info
            if farm and farm != info["farm"]:
                continue

            for k,v in six.iteritems(info["sandboxes"]):
                if tag == "all" or v == tag:
                    sandbox = {"name": k, "tag": v, "farm": info["farm"],
                               "host_container": info["host_container"]}
                    sandboxes.append(sandbox)

        self.context["sandboxes"] = sandboxes


    def cleanup(self):
        LOG.debug("Cleanup ovn sandbox context")



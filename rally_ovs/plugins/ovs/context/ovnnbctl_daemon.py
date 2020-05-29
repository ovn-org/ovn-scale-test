# Copyright 2020 Red Hat, Inc.
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
from rally import consts
from rally.task import context
from rally_ovs.plugins.ovs import ovnclients

LOG = logging.getLogger(__name__)

@context.configure(name="ovn-nbctld", order=112)
class OvnNbctlDaemonContext(ovnclients.OvnClientMixin, context.Context):
    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "properties": {
            "daemon_mode": {"type": "boolean"},
            "remote": {"type": "string"},
            "prot": {"type": "string"},
            "privkey": {"type": "string"},
            "cert": {"type": "string"},
            "cacert": {"type": "string"},
        },
        "additionalProperties": True
    }

    DEFAULT_CONFIG = {
        "daemon_mode": True,
    }

    @logging.log_task_wrapper(LOG.info, _("Enter context: `ovn-nbctld`"))
    def setup(self):
        super(OvnNbctlDaemonContext, self).setup()

        if self.config["daemon_mode"]:
            self.context["daemon_socket"] = self._start_daemon(self.config)

    @logging.log_task_wrapper(LOG.info, _("Exit context: `ovn-nbctld`"))
    def cleanup(self):
        if self.config["daemon_mode"]:
            self._stop_daemon()

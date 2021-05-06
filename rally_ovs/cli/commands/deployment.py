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


""" Rally OVS command: deployment """
from __future__ import print_function

import json
import os
import sys

import jsonschema
from six.moves.urllib import parse
import yaml


from rally import api
from rally.cli import cliutils
from rally.cli import envutils
from rally.common import fileutils
from rally.common.i18n import _
from rally.common import utils
from rally.common import db
from rally.common import objects
from rally import exceptions
from rally_ovs import plugins


class DeploymentCommands(object):
    """Set of commands that allow you to manage ovs deployments."""


    @cliutils.args("--name", type=str, required=True,
               help="A name of the ovs deployment.")
    @cliutils.args("--filename", type=str, required=True, metavar="<path>",
               help="A path to the configuration file of the ovs deployment.")
    @cliutils.args("--no-use", action="store_false", dest="do_use",
                   help="Don't set new deployment as default for"
                        " future operations.")
    @plugins.ensure_plugins_are_loaded
    def create(self, name, filename, do_use=False):
        """Create new deployment.

        This command will create a new deployment record in rally ovs
        database.


        """

        filename = os.path.expanduser(filename)
        print("file:" + filename)

        with open(filename, "rb") as deploy_file:
            config = yaml.safe_load(deploy_file.read())

        try:
            deployment = api.Deployment.create(config, name)
        except jsonschema.ValidationError:
            print(_("Config schema validation error: %s.") % sys.exc_info()[1])
            return(1)
        except exceptions.DeploymentNameExists:
            print(_("Error: %s") % sys.exc_info()[1])
            return(1)

        self.list(deployment_list=[deployment])
        if do_use:
            self.use(deployment["uuid"])



    @cliutils.args("--deployment", dest="deployment", type=str,
                   metavar="<uuid>", required=False,
                   help="UUID or name of the deployment.")
    @plugins.ensure_plugins_are_loaded
    @envutils.with_default_deployment()
    def recreate(self, deployment=None):
        """Destroy and create an existing deployment.

        Unlike 'deployment destroy', the deployment database record
        will not be deleted, so the deployment UUID stays the same.

        :param deployment: UUID or name of the deployment
        """
        api.Deployment.recreate(deployment)


    @cliutils.args("--deployment", dest="deployment", type=str,
                   metavar="<uuid>", required=False,
                   help="UUID or name of the deployment.")
    @plugins.ensure_plugins_are_loaded
    @envutils.with_default_deployment()
    def destroy(self, deployment=None):
        """Destroy existing deployment.

        This will delete all ovs sandboxes created during Rally deployment
        creation. Also it will remove the deployment record from the
        Rally database.

        :param deployment: UUID or name of the deployment
        """
        dep = objects.Deployment.get(deployment)
        tasks = db.task_list(deployment=dep["uuid"])
        for task in tasks:
            api.Task.delete(task["uuid"], True)


        api.Deployment.destroy(deployment)



    def list(self, deployment_list=None):
        """List existing deployments."""

        headers = ["uuid", "created_at", "name", "status", "active"]
        current_deployment = envutils.get_global("RALLY_DEPLOYMENT")
        deployment_list = deployment_list or api.Deployment.list()

        table_rows = []
        if deployment_list:
            for t in deployment_list:
                r = [str(t[column]) for column in headers[:-1]]
                r.append("" if t["uuid"] != current_deployment else "*")
                table_rows.append(utils.Struct(**dict(zip(headers, r))))
            cliutils.print_list(table_rows, headers,
                                sortby_index=headers.index("created_at"))
        else:
            print(_("There are no deployments. "
                    "To create a new deployment, use:"
                    "\nrally deployment create"))



    @cliutils.args("--deployment", dest="deployment", type=str,
                   metavar="<uuid>", required=False,
                   help="UUID or name of the deployment.")
    @envutils.with_default_deployment()
    @cliutils.suppress_warnings
    def config(self, deployment=None):
        """Display configuration of the deployment.

        Output is the configuration of the deployment in a
        pretty-printed JSON format.

        :param deployment: UUID or name of the deployment
        """
        deploy = api.Deployment.get(deployment)
        result = deploy["config"]
        print(json.dumps(result, sort_keys=True, indent=4))



    @cliutils.args("--deployment", dest="deployment", type=str,
                   metavar="<uuid>", required=False,
                   help="UUID or name of a deployment.")
    def use(self, deployment):
        """Set active deployment.

        :param deployment: UUID or name of the deployment
        """
        try:
            deployment = api.Deployment.get(deployment)
            print("Using deployment: %s" % deployment["uuid"])

            fileutils.update_globals_file("RALLY_DEPLOYMENT",
                                          deployment["uuid"])

        except exceptions.DeploymentNotFound:
            print("Deployment %s is not found." % deployment)
            return 1



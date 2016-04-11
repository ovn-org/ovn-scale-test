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


from rally.cli import cliutils
from rally.cli import envutils
from rally.cli.commands import task
from rally import plugins

class TaskCommands(task.TaskCommands):
    """ Ovs Task management.

        Set of commands that allow you to manage benchmarking tasks and results.
    """


    @cliutils.args("--deployment", dest="deployment", type=str,
                   metavar="<uuid>", required=False,
                   help="UUID or name of a deployment.")
    @cliutils.args("--task", "--filename", metavar="<path>",
                   help="Path to the input task file.")
    @cliutils.args("--task-args", metavar="<json>", dest="task_args",
                   help="Input task args (JSON dict). These args are used "
                        "to render the Jinja2 template in the input task.")
    @cliutils.args("--task-args-file", metavar="<path>", dest="task_args_file",
                   help="Path to the file with input task args (dict in "
                        "JSON/YAML). These args are used "
                        "to render the Jinja2 template in the input task.")
    @envutils.with_default_deployment(cli_arg_name="deployment")
    @plugins.ensure_plugins_are_loaded
    def validate(self, task, deployment=None, task_args=None,
                 task_args_file=None):
        return super(TaskCommands, self).validate(task, deployment,
                                 task_args, task_args_file)


    @cliutils.args("--deployment", dest="deployment", type=str,
                   metavar="<uuid>", required=False,
                   help="UUID or name of a deployment.")
    @cliutils.args("--task", "--filename", metavar="<path>",
                   help="Path to the input task file")
    @cliutils.args("--task-args", dest="task_args", metavar="<json>",
                   help="Input task args (JSON dict). These args are used "
                        "to render the Jinja2 template in the input task.")
    @cliutils.args("--task-args-file", dest="task_args_file", metavar="<path>",
                   help="Path to the file with input task args (dict in "
                        "JSON/YAML). These args are used "
                        "to render the Jinja2 template in the input task.")
    @cliutils.args("--tag", help="Tag for this task")
    @cliutils.args("--no-use", action="store_false", dest="do_use",
                   help="Don't set new task as default for future operations.")
    @envutils.with_default_deployment(cli_arg_name="deployment")
    @plugins.ensure_plugins_are_loaded
    def start(self, task, deployment=None, task_args=None, task_args_file=None,
              tag=None, do_use=False, abort_on_sla_failure=False):
        return super(TaskCommands, self).start(task, deployment, task_args,
                                  task_args_file, tag, do_use)


    def abort(self, task_id=None, soft=False):
        pass

    def status(self, task_id=None):
        pass




    @cliutils.args("--uuid", type=str, dest="task_id",
                   help=("UUID of task. If --uuid is \"last\" the results of "
                         " the most recently created task will be displayed."))
    @cliutils.args("--iterations-data", dest="iterations_data",
                   action="store_true",
                   help="Print detailed results for each iteration.")
    @envutils.with_default_task_id
    def detailed(self, task_id=None, iterations_data=False):
        return super(TaskCommands, self).detailed(task_id, iterations_data)


    def results(self, task_id=None):
        pass

    def list(self, deployment=None, all_deployments=False, status=None,
             uuids_only=False):
        pass
    def report(self, tasks=None, out=None, open_it=False, out_format="html"):
        pass
    def delete(self, task_id=None, force=False):
        pass


    def xxx(self):
        pass

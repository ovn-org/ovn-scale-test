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



import os

from docutils.parsers import rst
from oslo_utils import importutils
from utils import category, subcategory, paragraph, parse_text


from rally.common.plugin import discover
import rally_ovs


DATA = [
    {
        "group": "task",
        "items": [
            {
                "name": "context",
                "base": "rally.task.context:Context"
            },
            {
                "name": "scenario",
                "base": "rally.task.scenario:Scenario"
            }
        ]
    },
    {
        "group": "deployment",
        "items": [
            {
                "name": "engine",
                "base": "rally.deployment.engine:Engine"
            },
            {
                "name": "server provider",
                "base": "rally.deployment.serverprovider.provider:ProviderFactory"
            }
        ]
    }
]


def load_plugins():
    path = os.path.dirname(rally_ovs.__file__) + "/plugins"

    discover.load_plugins(path)


def _make_pretty_parameters(parameters):
    if not parameters:
        return ""

    result = "**Parameters**:\n\n"
    for p in parameters:
        result += "* %(name)s: %(doc)s\n" % p
    return result


def make_plugin_section(plugin, base_name):
    subcategory_obj = subcategory("%s [%s]" % (plugin.get_name(), base_name))
    info = plugin.get_info()
    if info["title"]:
        subcategory_obj.append(paragraph(info["title"]))

    if info["description"]:
        subcategory_obj.extend(parse_text(info["description"]))

    if info["namespace"]:
        subcategory_obj.append(paragraph(
                "**Namespace**: %s" % info["namespace"]))

    if info["parameters"]:
        subcategory_obj.extend(parse_text(
                _make_pretty_parameters(info["parameters"])))
        if info["returns"]:
            subcategory_obj.extend(parse_text(
                    "**Returns**:\n%s" % info["returns"]))
    filename = info["module"].replace(".", "/")
    ref = "https://github.com/openstack/rally/blob/master/%s.py" % filename
    subcategory_obj.extend(parse_text("**Module**:\n`%s`__\n\n__ %s"
                                      % (info["module"], ref)))
    return subcategory_obj


def make_plugin_base_section(plugin_group):
    elements = []

    for item in plugin_group["items"]:
        name = item["name"].title() if "SLA" != item["name"] else item["name"]
        category_obj = category("%s %ss" % (plugin_group["group"].title(),
                                            name))
        elements.append(category_obj)

        module, cls = item["base"].split(":")
        plugin_base = getattr(importutils.import_module(module), cls)

        for p in plugin_base.get_all():
            category_obj.append(make_plugin_section(p, item["name"]))

    return elements


class PluginReferenceDirective(rst.Directive):

    def run(self):
        content = []
        for i in range(len(DATA)):
            content.extend(make_plugin_base_section(DATA[i]))

        return content


def setup(app):
    load_plugins()
    app.add_directive('generate_plugin_reference', PluginReferenceDirective)

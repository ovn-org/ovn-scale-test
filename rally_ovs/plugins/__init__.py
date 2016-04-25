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

import os

import decorator

from rally.common.plugin import discover
import rally_ovs

PLUGINS_LOADED = False


def load():
    global PLUGINS_LOADED

    if not PLUGINS_LOADED:
        discover.import_modules_from_package("rally.deployment.engines")
        discover.import_modules_from_package("rally.deployment.serverprovider")
        discover.import_modules_from_package("rally.plugins.common")

        path = [os.path.dirname(rally_ovs.__file__)] + __name__.split(".")[1:]
        path = os.path.join(*path)
        discover.load_plugins(path)

        discover.load_plugins("/opt/rally/plugins/")
        discover.load_plugins(os.path.expanduser("~/.rally/plugins/"))

    PLUGINS_LOADED = True


@decorator.decorator
def ensure_plugins_are_loaded(f, *args, **kwargs):
    load()
    return f(*args, **kwargs)

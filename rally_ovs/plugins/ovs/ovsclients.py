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

import abc
import collections
import six
import re
import netaddr

from rally.common.plugin import plugin
from rally.task import scenario
from utils import py_to_val
from io import StringIO

_NAMESPACE = "ovs"


def configure(name):
    return plugin.configure(name, namespace=_NAMESPACE)



class OvsClient(plugin.Plugin):
    def __init__(self, credential, cache_obj):
        self.credential = credential
        self.cache = cache_obj


    @classmethod
    def get(cls, name, namespace=_NAMESPACE):
        return super(OvsClient, cls).get(name, namespace)

    @abc.abstractmethod
    def create_client(self, *args, **kwargs):
        """Create new instance of client."""

    def __call__(self, *args, **kwargs):
        """Return initialized client instance."""
        key = "{0}{1}{2}".format(self.get_name(),
                                 str(args) if args else "",
                                 str(kwargs) if kwargs else "")
        if key not in self.cache:
            self.cache[key] = self.create_client(*args, **kwargs)
        return self.cache[key]



class Clients(object):
    def __init__(self, credential):
        self.credential = credential
        self.cache = {}

    def __getattr__(self, client_name):
        return OvsClient.get(client_name)(self.credential, self.cache)



    def clear(self):
        """Remove all cached client handles."""
        self.cache = {}


class ClientsMixin(object):
    """Mixin for objects that use OvsClient clients"""

    def __init__(self, *args, **kwargs):
        super(ClientsMixin, self).__init__(*args, **kwargs)

        self._controller_clients = None
        self._farm_clients = {}

        # We are a Scenario, context has been already set up. Use it.
        if isinstance(self, scenario.Scenario):
            self.setup()

    def setup(self):
        multihost_info = self.context["ovn_multihost"]

        for k,v in six.iteritems(multihost_info["controller"]):
            cred = v["credential"]
            self._controller_clients = Clients(cred)

        self._farm_clients = {}
        for k,v in six.iteritems(multihost_info["farms"]):
            cred = v["credential"]
            self._farm_clients[k] = Clients(cred)

        self.install_method = multihost_info["install_method"]

    def __del__(self):
        self.cleanup_clients()

    def controller_client(self, client_type="ssh"):
        client = getattr(self._controller_clients, client_type)
        return client()

    def farm_clients(self, name, client_type="ssh"):
        clients = self._farm_clients[name]
        client = getattr(clients, client_type)
        return client()

    def cleanup_clients(self):
        if self._controller_clients:
            self._controller_clients.clear()
        for _, clients in six.iteritems(self._farm_clients):
            clients.clear()


'''
    lswitch 48732e5d-b018-4bad-a1b6-8dbc762f4126 (lswitch_c52f4c_xFG42O)
        lport lport_c52f4c_LXzXCE
        lport lport_c52f4c_dkZSDg
    lswitch 7f55c582-c007-4fba-810d-a14ead480851 (lswitch_c52f4c_Rv0Jcj)
        lport lport_c52f4c_cm8SIf
        lport lport_c52f4c_8h7hn2
    lswitch 9fea76cf-d73e-4dc8-a2a3-1e98b9d8eab0 (lswitch_c52f4c_T0m6Ce)
        lport lport_c52f4c_X3px3u
        lport lport_c52f4c_92dhqb

'''

def get_lswitch_info(info):
    '''
    @param info output of 'ovn-nbctl show'
    '''

    lswitches = []

    lswitch = None
    for line in info.splitlines():
        tokens = line.strip().split(" ")
        if tokens[0] == "switch":
            start_cidr = re.sub("\(lswitch_|\)", "", tokens[2])
            if len(start_cidr):
                cidr = netaddr.IPNetwork(start_cidr)
            else:
                cidr = ""
            name = tokens[2][1:-1]
            lswitch = {"name":name, "uuid":tokens[1], "lports":[], "cidr":cidr}
            lswitches.append(lswitch)
        elif tokens[0] == "port":
            name = tokens[1][1:-1]
            lswitch["lports"].append({"name":name})

    return lswitches

def parse_lswitch_list(lswitch_data):
    lswitches = []
    for line in lswitch_data.splitlines():
        lswitches.append({"name": line.split(" ")[1].strip('()')})
    return lswitches

def set_colval_args(*col_values):
    args = []
    for entry in col_values:
        if len(entry) == 2:
            col, op, val = entry[0], '=', entry[1]
        else:
            col, op, val = entry
        if isinstance(val, collections.Mapping):
            args += ["%s:%s%s%s" % (
                col, k, op, py_to_val(v)) for k, v in val.items()]
        elif (isinstance(val, collections.Sequence)
                and not isinstance(val, six.string_types)):
            if len(val) == 0:
                args.append("%s%s%s" % (col, op, "[]"))
            else:
                args.append(
                    "%s%s%s" % (col, op, ",".join(map(py_to_val, val))))
        else:
            args.append("%s%s%s" % (col, op, py_to_val(val)))
    return args



class DdCtlMixin(object):

    def get(self, table, record, *col_values):
        args = [table, record]
        for entry in col_values:
            args.append("%s" % entry)

        stdout = StringIO()
        self.run("get", args=args, stdout=stdout)
        return stdout.getvalue()

    def list(self, table, records):
        args = [table]
        args += records
        self.run("list", args=args)

    def wait_until(self, table, record, *col_values):
        args = [table, record]
        args += set_colval_args(*col_values)
        self.run("wait-until", args=args)

    def create(self, table, record, *col_values):
        args = [table, record]
        args += set_colval_args(*col_values)
        self.run("create", args=args)

    def add(self, table, record, *col_values):
        args = [table, record]
        args += set_colval_args(*col_values)
        self.run("add", args=args)

    def remove(self, table, record, *col_values):
        args = [table, record]
        args += set_colval_args(*col_values)
        self.run("remove", args=args)

    def set(self, table, record, *col_values):
        args = [table, record]
        args += set_colval_args(*col_values)
        self.run("set", args=args)

    def destroy(self, table, record):
        args = [table, record]
        self.run("destroy", args=args)





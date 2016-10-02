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

from rally.common.plugin import plugin
from utils import py_to_val

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
        if tokens[0] == "lswitch":
            name = tokens[2][1:-1]
            lswitch = {"name":name, "uuid":tokens[1], "lports":[]}
            lswitches.append(lswitch)
        elif tokens[0] == "lport":
            name = tokens[1][1:-1]
            lswitch["lports"].append({"name":name})

    return lswitches


def get_of_in_port(of_port_list_raw, port_name_full):
    # NOTE (huikang): the max length of portname shown in ovs-ofctl show is 15
    port_name = port_name_full[0:15]
    lines = of_port_list_raw.splitlines()
    line = ""
    for line in lines:
        if (line.find(port_name) >= 0):
                break
    position = line.find("(")
    return line[:position]


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
        args += set_colval_args(*col_values)
        self.run("get", args=args)


    def list(self, table, records):
        args = [table]
        args += records
        self.run("list", args=args)

    def wait_until(self, table, record, *col_values):
        args = [table, record]
        args += set_colval_args(*col_values)
        self.run("wait-until", args=args)






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

import random
import netaddr
import six

from consts import ResourceType
from rally.common import sshutils
from rally.common import objects
from rally.common import utils

from rally.common import db

import socket
import selectors
import time

cidr_incr = utils.RAMInt()

'''
    Find credential resource from DB by deployment uuid, and return
    info as a dict.

    :param deployment deployment uuid
'''
def get_credential_from_resource(deployment):

    res = None
    if not isinstance(deployment, objects.Deployment):
        deployment = objects.Deployment.get(deployment)

    res = deployment.get_resources(type=ResourceType.CREDENTIAL)

    return res["info"]



def get_ssh_from_credential(cred):
    sshcli = sshutils.SSH(cred["user"], cred["host"],
                       port = cred["port"],
                       key_filename = cred["key"],
                       password = cred["password"])
    return sshcli


def get_ssh_client_from_deployment(deployment):
    cred = get_credential_from_resource(deployment)

    return get_ssh_from_credential(cred)



def get_random_sandbox(sandboxes):
    info = random.choice(sandboxes)
    sandbox = random.choice(info["sandboxes"])

    return info["farm"], sandbox



def get_random_mac(base_mac):
    mac = [int(base_mac[0], 16), int(base_mac[1], 16),
           int(base_mac[2], 16), random.randint(0x00, 0xff),
           random.randint(0x00, 0xff), random.randint(0x00, 0xff)]
    if base_mac[3] != '00':
        mac[3] = int(base_mac[3], 16)
    return ':'.join(["%02x" % x for x in mac])



def generate_cidr(start_cidr="10.2.0.0/24"):
    """Generate next CIDR for network or subnet, without IP overlapping.

    This is process and thread safe, because `cidr_incr' points to
    value stored directly in RAM. This guarantees that CIDRs will be
    serial and unique even under hard multiprocessing/threading load.

    :param start_cidr: start CIDR str
    :returns: next available CIDR str
    """
    cidr = str(netaddr.IPNetwork(start_cidr).next(next(cidr_incr)))
    return cidr




def py_to_val(pyval):
    """Convert python value to ovs-vsctl value argument"""
    if isinstance(pyval, bool):
        return 'true' if pyval is True else 'false'
    elif pyval == '':
        return '""'
    else:
        return pyval



def get_farm_nodes(deploy_uuid):
    deployments = db.deployment_list(parent_uuid=deploy_uuid)

    farm_nodes = []
    for dep in deployments:
        res = db.resource_get_all(dep["uuid"], type=ResourceType.SANDBOXES)
        if len(res) == 0 or len(res[0].info["sandboxes"]) == 0:
            continue

        farm_nodes.append(res[0].info["farm"])

    return farm_nodes




def get_sandboxes(deploy_uuid, farm="", tag=""):

    sandboxes = []
    deployments = db.deployment_list(parent_uuid=deploy_uuid)
    for dep in deployments:
        res = db.resource_get_all(dep["uuid"], type=ResourceType.SANDBOXES)
        if len(res) == 0 or len(res[0].info["sandboxes"]) == 0:
            continue

        info = res[0].info

        if farm and farm != info["farm"]:
            continue

        for k,v in six.iteritems(info["sandboxes"]):
            if tag and tag != v:
                continue

            sandbox = {"name": k, "tag": v, "farm": info["farm"],
                       "host_container": info["host_container"]}
            sandboxes.append(sandbox)


    return sandboxes


class NCatError(Exception):
    def __init__(self, details):
        self.details = details


class NCatClient(object):
    def __init__(self, server):
        self.server = server
        self.sock = socket.create_connection((server, 8000))
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.sock, selectors.EVENT_READ)

    def run(self, cmd, stdin=None, stdout=None, stderr=None,
            raise_on_error=True, timeout=3600):
        start = time.clock_gettime(time.CLOCK_MONOTONIC)
        end = time.clock_gettime(time.CLOCK_MONOTONIC) + timeout
        to = end - start
        # We have to doctor the command a bit for three reasons:
        # 1. We need to add a newline to ensure that the command
        #    gets sent to the server and doesn't just get put in
        #    the socket's write buffer.
        # 2. We need to pipe stderr to stdout so that stderr gets
        #    returned over the client connection.
        # 3. We need to add some marker text so our client knows
        #    that it has received all output from the command. This
        #    marker text let's us know if the command completed
        #    successfully or not.
        good = "SUCCESS"
        bad = "FAIL"
        result = f"&& echo -n {good} || echo -n {bad}"
        self.sock.send(f"({cmd}) 2>&1 {result}\n".encode('utf-8'))
        out = ""
        stream = None
        error = False
        while True:
            events = self.sel.select(to)
            for key, mask in events:
                buf = key.fileobj.recv(4096).decode('utf-8')
                if buf.endswith(good):
                    out += buf[:-len(good)]
                    stream = stdout
                    break
                elif buf.endswith(bad):
                    out += buf[:-len(bad)]
                    # We assume that if the command errored, then everything
                    # that was output was stderr. This isn't necessarily
                    # accurate but it hopefully won't ruffle too many feathers.
                    stream = stderr
                    error = True
                    break
                else:
                    out += buf
                    to = end - time.clock_gettime(time.CLOCK_MONOTONIC)

        if stream is not None:
            stream.write(out)

        if error and raise_on_error:
            details = (f"Error running command {cmd}\n"
                       f"Last stderr output is {out}\n")
            raise NCatError(details)

    def close(self):
        # Test scenarios call close after every operation because with SSH,
        # this is necessary to ensure that we do not open too many
        # connections. Our ncat client cache is keyed on hostname rather than
        # on the controller node. This means that we open far fewer connections
        # than SSH does. Therefore, there is no reason to close connections
        # as frequently as we do with SSH. We can afford to leave the
        # connection open and reuse the clients instead. This is why we "pass"
        # in this method.
        pass


NCAT_CLIENT_CACHE = {}


def get_client_connection(cred):
    try:
        global NCAT_CLIENT_CACHE
        server = cred["host"]
        return NCAT_CLIENT_CACHE.setdefault(server, NCatClient(server))
    except socket.error:
        return get_ssh_from_credential(cred)

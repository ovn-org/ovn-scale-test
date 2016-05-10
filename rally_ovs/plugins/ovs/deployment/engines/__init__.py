
import os
from rally.deployment.serverprovider import provider


OVS_REPO = "https://github.com/openvswitch/ovs.git"
OVS_BRANCH = "master"
OVS_USER = "rally"


def get_script(name):
    return open(os.path.join(os.path.abspath(
        os.path.dirname(__file__)), "ovs", name), "rb")


def get_script_path(name):
    return os.path.join(os.path.abspath(
        os.path.dirname(__file__)), "ovs", name);

def get_updated_server(server, **kwargs):
    credentials = server.get_credentials()
    credentials.update(kwargs)
    return provider.Server.from_credentials(credentials)

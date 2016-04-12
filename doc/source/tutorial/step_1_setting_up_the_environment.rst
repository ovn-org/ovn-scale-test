..
    Copyright 2016 Ebay Inc.

    Licensed under the Apache License, Version 2.0 (the "License"); you may
    not use this file except in compliance with the License. You may obtain
    a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
    License for the specific language governing permissions and limitations
    under the License.



.. _tutorial_step_1_setting_up_the_environment:

Step 1. Setting up the environment
==================================

.. contents::
   :local:

Setup a password-less SSH key(optional)
---------------------------------------
This step is optional. Rally needs root privilege for installing OVS on
farm node, it's convenient to use a password-less SSH key to login as root
and avoid type your password in config file.

1. Generate a password-less ssh key on rally node

.. code-block:: bash

    $ ssh-kengen  # just hit enter when ask for password

2. Copy the generated id_rsa.pub to all of other nodes, e.g:

.. code-block:: bash

    $ ssh [username]@[hostname]
    $ sudo mkdir /root/.ssh
    $ sudo scp [username]@[rally-node]:/path/to/id_rsa.pub /root/.ssh
    $ sudo cat .ssh/id_rsa.pub >> /root/.ssh/authorized_keys


3. Check if the password-less SSH key is setup properly, try ssh connect to
other nodes from rally node:

.. code-block:: bash

    $ ssh [username]@[hostname]

If success, you will get a bash prompt directly without password prompt


Create a deployment in Rally
----------------------------
You have to provide **OVN Scale Test** with a deployment it is going to run
task. You can put the information about your hosts into a JSON
configuration file, then ``rally-ovs`` is used to deploy a ovn controller node
and one or more farm nodes.

Following config file creates a deployment with:

- one OVN controller node, runs an ovn-northd, a northbound ovsdb-serverand and
  a southbound ovsdb-server.
- two OVN sandbox farm node, runs ovs-sandboxes(each ovs-sandbox simulates one
  HV, consists of an ovn-controller, an ovs-vswitchd, and an ovsdb-server).


.. code-block:: json
    :caption: samples/deployments/ovn-multihost.json

    {
        "type": "OvnMultihostEngine",
        "controller": {
            "type": "OvnSandboxControllerEngine",
            "deployment_name": "ovn-controller-node",
            "ovs_repo": "https://github.com/openvswitch/ovs.git",
            "ovs_branch": "master",
            "ovs_user": "rally",
            "net_dev": "eth1",
            "controller_cidr": "192.168.10.10/16",
            "provider": {
                "type": "OvsSandboxProvider",
                "credentials": [
                    {
                        "host": "192.168.20.10",
                        "user": "root"}
                ]
            }
        },
        "nodes": [
            {
                "type": "OvnSandboxFarmEngine",
                "deployment_name": "ovn-farm-node-0",
                "ovs_repo" : "https://github.com/openvswitch/ovs.git",
                "ovs_branch" : "master",
                "ovs_user" : "rally",
                "provider": {
                    "type": "OvsSandboxProvider",
                    "credentials": [
                        {
                            "host": "192.168.20.20",
                            "user": "root"}
                    ]
                }
            }
        ]

    }


**Notes:**

- Replace 'username' with a suitable username
- "controller_cidr" is a private address, ovn controller node's ovsdb-server
  will listen on this ip. The IP address will be added to "net_dev" as a IP alias.
- With config file, one ovn controller node and two farm nodes will be deployed.


Run rally-ovs to create the deployment:

.. code-block:: console

    $ . ~/rally/bin/activate
    $ rally-ovs deployment create --file ovn-scalability-test/deployments/ovn-multihost.json --name ovn-multihost
    ...
    +--------------------------------------+----------------------------+---------------+------------------+--------+
    | uuid                                 | created_at                 | name          | status           | active |
    +--------------------------------------+----------------------------+---------------+------------------+--------+
    | 320115a1-0613-47a5-91f3-fc0a29a86e64 | 2016-04-12 12:47:54.144207 | ovn-multihost | deploy->finished |        |
    +--------------------------------------+----------------------------+---------------+------------------+--------+
    Using deployment: 320115a1-0613-47a5-91f3-fc0a29a86e64

After this command executed successfully, the ovn controller node has an
running ovn-northd, northbound ovsdb-serverand and southbound ovsdb-server now,
but the two farm nodes have no ovs-sandboxes running on them, you need use
``task`` command to create ovs-sandboxes.


**Notes:** the command used here is ``rally-ovs``, not ``rally``


Run ``rally-ovs deployment`` with option ``--help`` to have a list of all
available options:

.. code-block:: console

    $ rally-ovs deployment --help
    usage: rally-ovs deployment [-h] {config,create,destroy,list,recreate,use} ...
    Set of commands that allow you to manage ovs deployments.
    Commands:
       config     Display configuration of the deployment.
       create     Create new deployment.
       destroy    Destroy existing deployment.
       list       List existing deployments.
       recreate   Destroy and create an existing deployment.
       use        Set active deployment.
    optional arguments:
      -h, --help  show this help message and exit


Create ovs-sandboxes on farm nodes
----------------------------------
Now that we have a working and registered deployment, we can create
ovs-sandboxes to simulate HVs. Let's create some ovs-sandboxes on farm node 0
as a example

.. code-block:: json
    :caption: samples/tasks/scenarios/ovn-sandbox/create_sandbox.json

    {
        "version": 2,
        "title": "Create sandbox",
        "subtasks": [{
            "title": "Create sandbox on farm 0",
            "workloads": [{
                "name": "OvnSandbox.create_sandbox",
                "args": {
                    "sandbox_create_args": {
                        "farm": "ovn-farm-node-0",
                        "amount": 3,
                        "batch" : 10,
                        "start_cidr": "192.168.64.0/16",
                        "net_dev": "eth1",
                        "tag": "ToR1"
                    }
                },
                "runner": {"type": "serial", "times": 1},
                "context": {
                    "ovn_multihost" : { "controller": "ovn-controller-node"}
                }
            }]
        }]
    }


To start a Rally task, run the task start command:

.. code-block:: console

    $ rally-ovs task start samples/tasks/scenarios/ovn-sandbox/create_sandbox.json
    --------------------------------------------------------------------------------
     Preparing input task
    --------------------------------------------------------------------------------

    Input task is:
    <Your task config here>
    ...
    Task config is valid :)
    --------------------------------------------------------------------------------
     Task  41dd9197-6c74-4b74-a081-58b866b40de0: started
    --------------------------------------------------------------------------------
    Benchmarking... This can take a while...
    ...

    --------------------------------------------------------------------------------
    Task 41dd9197-6c74-4b74-a081-58b866b40de0: finished
    --------------------------------------------------------------------------------

    test scenario OvnSandbox.create_sandbox
    args position 0

    +---------------------------------------------------------------------------------------------+
    |                                    Response Times (sec)                                     |
    +------------------------+-------+--------+--------+--------+-------+-------+---------+-------+
    | action                 | min   | median | 90%ile | 95%ile | max   | avg   | success | count |
    +------------------------+-------+--------+--------+--------+-------+-------+---------+-------+
    | sandbox.create_sandbox | 0.935 | 0.935  | 0.935  | 0.935  | 0.935 | 0.935 | 100.0%  | 1     |
    | total                  | 0.956 | 0.956  | 0.956  | 0.956  | 0.956 | 0.956 | 100.0%  | 1     |
    +------------------------+-------+--------+--------+--------+-------+-------+---------+-------+
    Load duration: 1.08041000366
    Full duration: 1.10536003113

    HINTS:
    * To plot HTML graphics with this data, run:
        rally task report 41dd9197-6c74-4b74-a081-58b866b40de0 --out output.html

    * To generate a JUnit report, run:
        rally task report 41dd9197-6c74-4b74-a081-58b866b40de0 --junit --out output.xml

    * To get raw JSON output of task results, run:
        rally task results 41dd9197-6c74-4b74-a081-58b866b40de0

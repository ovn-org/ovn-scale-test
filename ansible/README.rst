Ansible and Docker OVN Emulation Guide
======================================

Overview
--------

Deploy an OVN emulation environment using Docker container and ansible

Host machine requirements
-------------------------

The recommended emulation target requirements:

- 1 deploy node to run ansible and Rally workload
- 1 OVN database node
- 2 OVN chassis host to run emulated OVN chassis container

Installing Dependencies
-----------------------

The deploy node needs ansible. Docker and docker-py are required on the other nodes.

::

    pip install -U docker-py

Building OVN Container Images
-------------------------------

You can build your own OVN docker image by

::

    cd ansible/docker
    make

These command will generate an OVN docker image name ovn-scale-test. If you do
not like the name, you can edit ansible/docker/Makefile to change the image
name.

Alternatively, there is a pre-built image in docker hub. To use it, run

::

    docker pull huikang/ovn-scale-test

The remaining of this guide uses OVN-SCALE-TEST as the image name. You need to
change the name in your deployment.


Setup the emulation environment
-------------------------------

Add hosts to the ansible inventory file

::

    ansible/inventory/ovn-hosts

Customize ansible/group_vars/all.yml based on your testbed.

For example, to define the total number of emulated chasis in the network:

::

    ovn_db_image: "huikang/ovn-scale-test"
    ovn_chassis_image: "huikang/ovn-scale-test"
    ovn_number_chassis: 10

During deployment, these chassis will be evenly distributed on the emulations
hosts, which are defined in the inventory file.

Rnning OVN Emulation
----------------------

Run the ansible playbook

::

    ansible-playbook  -i ansible/inventory/ovn-hosts ansible/site.yml -e action=deploy

The fastest way during evaluation to re-deployment is to remove the OVN
containers and re-deploy.

To clean up the existing emulation deployment,

::

    ansible-playbook  -i ansible/inventory/ovn-hosts ansible/site.yml -e action=clean


Rnning Rally Workloads
----------------------

TODO

ovn-scale-cicd
==============

This project aims to provide some scripts to automate running the
[ovn-scale-test][1] test suite. The goal is for this to be integrated
into a CI/CD system.

Howto
-----

Running this project is as simple as the following:

* Look at the ovn-scale.conf file for variable you can override to
  change the runtime behaviour.
* Modify ansible/docker-ovn-hosts to match the IP addresses of the
  hosts you are using.
* Run `prepare.sh` to prepare the system for running the scripts.
* Run `scale-hosts.sh` to create the docker containers on each host.
* Run `scale-test.sh` to run the testsuite.
* The script `scale-cleanup.sh` will cleanup all the containers.

1: https://github.com/openvswitch/ovn-scale-test

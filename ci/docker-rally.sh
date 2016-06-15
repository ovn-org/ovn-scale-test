#!/bin/bash

OVS_REPO=${1:-https://github.com/openvswitch/ovs.git}
OVS_BRANCH=${2:-master}

# A combined script to run all the things

# Prepare the environment
./prepare.sh

# Run the testsuite
./scale-run.sh $OVS_REPO $OVS_BRANCH

# Clean things up
./scale-cleanup.sh

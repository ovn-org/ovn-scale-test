#!/bin/bash

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set -o xtrace

# Track failures
FAILED=0

OVS_REPO=${1:-https://github.com/openvswitch/ovs.git}
OVS_BRANCH=${2:-master}
CONFIG_FLAGS=${3:---enable-Werror}

echo "OVS_REPO=${OVS_REPO} OVS_BRANCH=${OVS_BRANCH} CONFIG_FLAGS=${CONFIG_FLAGS}"

# A combined script to run all the things

# Prepare the environment
./prepare.sh || FAILED=$(( $FAILED + 1 ))

# resave trace setting
set -o xtrace

# Create the docker containers
./scale-hosts.sh $OVS_REPO $OVS_BRANCH $CONFIG_FLAGS || FAILED=$(( $FAILED + 1 ))

# Run the testsuite
./scale-test.sh || FAILED=$(( $FAILED + 1 ))

# Clean things up
./scale-cleanup.sh || FAILED=$(( $FAILED + 1 ))

# Restore xtrace
$XTRACE

exit $FAILED

#!/bin/bash

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set -o xtrace

# Track failures
FAILED=0

OVS_REPO=${1:-https://github.com/openvswitch/ovs.git}
OVS_BRANCH=${2:-master}
CONFIG_FLAG=${3:---enable-Werror}

echo "OVS_REPO=${OVS_REPO} OVS_BRANCH=${OVS_BRANCH} CONFIG_FLAG=${CONFIG_FLAG}"

# A combined script to run all the things

# Prepare the environment
./prepare.sh || FAILED=$(( $FAILED + 1 ))

# Run the testsuite
./scale-run.sh $OVS_REPO $OVS_BRANCH $CONFIG_FLAG || FAILED=$(( $FAILED + 1 ))

# Clean things up
./scale-cleanup.sh || FAILED=$(( $FAILED + 1 ))

return $FAILED

# Restore xtrace
$XTRACE

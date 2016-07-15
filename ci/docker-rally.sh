#!/bin/bash

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set -o xtrace

# Track failures
FAILED=0

OVS_REPO=${1:-https://github.com/openvswitch/ovs.git}
OVS_BRANCH=${2:-master}

echo "OVS_REPO=${OVS_REPO} OVS_BRANCH=${OVS_BRANCH}"

# A combined script to run all the things

# Prepare the environment
./prepare.sh || FAILED=$(( $FAILED + 1 ))

# Run the testsuite
./scale-run.sh $OVS_REPO $OVS_BRANCH || FAILED=$(( $FAILED + 1 ))

# Clean things up
./scale-cleanup.sh || FAILED=$(( $FAILED + 1 ))

return $FAILED

# Restore xtrace
$XTRACE

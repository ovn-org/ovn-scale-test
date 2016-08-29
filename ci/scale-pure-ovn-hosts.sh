#!/bin/bash

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set -o xtrace

# Read variables
source ovn-scale.conf

# Library files
source scale-lib.sh

OVS_REPO=$1
OVS_BRANCH=$2
CONFIG_FLAGS=$3

# Build the docker containers
pushd $OVN_SCALE_TOP
cd ansible/docker
make ovsrepo=$OVS_REPO ovsbranch=$OVS_BRANCH configflags=$CONFIG_FLAGS
popd
$OVNSUDO docker images

# Deploy the containers
pushd $OVN_SCALE_TOP
$OVNSUDO /usr/local/bin/ansible-playbook -i $OVN_DOCKER_HOSTS ansible/site-ovn-only.yml -e @$OVN_DOCKER_VARS  -e enable_rally_ovs="no" \
     --extra-vars "ovs_repo=$OVS_REPO" --extra-vars "ovs_branch=$OVS_BRANCH" --extra-vars "configflags=$CONFIG_FLAGS" -e action=deploy
if [ "$?" != "0" ] ; then
    echo "Deploying failed, exiting"
    exit 1
fi
popd

# Verify the containers are running
check_container_failure

# TODO(mestery): Verifying everything is connected
$OVNSUDO docker exec ovn-south-database ovn-sbctl show

# Restore xtrace
$XTRACE

#!/bin/bash

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set -o xtrace

# Read variables
source ovn-scale.conf

OVS_REPO=$1
OVS_BRANCH=$2
CONFIG_FLAGS=$3

function check_container_failure {
    sleep 5

    docker ps -a
    failed_containers=$(docker ps -a --format "{{.Names}}" --filter status=exited)

    if [ "$failed_containers" ]; then
        for failed in ${failed_containers}; do
            docker logs --tail all ${failed}
        done
        exit 1
    fi
}

function check_ovn_rally {
    output_file=$1
    count=`cat $output_file | grep total | grep 100 | wc -l`
    if [ $count -ne 0 ]
    then
        echo "Rally run succeeded"
    else
        echo "Rally run failed"
        exit 1
    fi
}

# Build the docker containers
pushd $OVN_SCALE_TOP
cd ansible/docker
make ovsrepo=$OVS_REPO ovsbranch=$OVS_BRANCH configflags=$CONFIG_FLAGS
popd
$OVNSUDO docker images

# Deploy the containers
pushd $OVN_SCALE_TOP
$OVNSUDO /usr/local/bin/ansible-playbook -i $OVN_DOCKER_HOSTS ansible/site.yml -e @$OVN_DOCKER_VARS \
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

# Create the rally deployment
$OVNSUDO docker exec ovn-rally rally-ovs deployment create --file /root/rally-ovn/ovn-multihost-deployment.json --name ovn-multihost

# Restore xtrace
$XTRACE

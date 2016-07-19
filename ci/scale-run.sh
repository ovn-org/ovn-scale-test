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

# Build the docker containers
pushd $OVN_SCALE_TOP
cd ansible/docker
make ovsrepo=$OVS_REPO ovsbranch=$OVS_BRANCH configflags=$CONFIG_FLAGS
popd
$OVNSUDO docker images

# Deploy the containers
# TODO(mestery): Loop through all hosts in the "[emulation-hosts]" section.
#                For now, this assumes a single host, so not necessary until
#                that assumption changes.
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

# Register the emulated sandboxes in the rally database
$OVNSUDO docker exec ovn-rally rally-ovs task start /root/rally-ovn/workload/create-sandbox-$OVN_RALLY_HOSTNAME.json
TASKID=$($OVNSUDO docker exec ovn-rally rally task list --uuids-only)
$OVNSUDO docker exec ovn-rally rally task report $TASKID --out /root/create-sandbox-output.html
$OVNSUDO docker cp ovn-rally:/root/create-sandbox-output.html .
$OVNSUDO docker exec ovn-rally rally task delete --uuid $TASKID

# Run tests
$OVNSUDO docker exec ovn-rally rally-ovs task start /root/rally-ovn/workload/create_networks.json
TASKID=$($OVNSUDO docker exec ovn-rally rally task list --uuids-only)
# NOTE(mestery): HTML and JSON data are collected differently, look to consolidate
$OVNSUDO docker exec ovn-rally rally task report $TASKID --out /root/create-networks-output.html
$OVNSUDO docker exec ovn-rally rally task results $TASKID > ./create-networks-data.json
$OVNSUDO docker cp ovn-rally:/root/create-networks-output.html .
$OVNSUDO docker exec ovn-rally rally task delete --uuid $TASKID

$OVNSUDO docker exec ovn-rally rally-ovs task start /root/rally-ovn/workload/create_and_list_lports.json
TASKID=$($OVNSUDO docker exec ovn-rally rally task list --uuids-only)
# NOTE(mestery): HTML and JSON data are collected differently, look to consolidate
$OVNSUDO docker exec ovn-rally rally task report $TASKID --out /root/create-and-list-lports-output.html
$OVNSUDO docker exec ovn-rally rally task results $TASKID > ./create-and-list-lports-data.json
$OVNSUDO docker cp ovn-rally:/root/create-and-list-lports-output.html .
$OVNSUDO docker exec ovn-rally rally task delete --uuid $TASKID

$OVNSUDO docker exec ovn-rally rally-ovs task start /root/rally-ovn/workload/create_and_list_acls.json
TASKID=$($OVNSUDO docker exec ovn-rally rally task list --uuids-only)
# NOTE(mestery): HTML and JSON data are collected differently, look to consolidate
$OVNSUDO docker exec ovn-rally rally task report $TASKID --out /root/create-and-list-acls-output.html
$OVNSUDO docker exec ovn-rally rally task results $TASKID > ./create-and-list-acls-data.json
$OVNSUDO docker cp ovn-rally:/root/create-and-list-acls-output.html .
$OVNSUDO docker exec ovn-rally rally task delete --uuid $TASKID

$OVNSUDO docker exec ovn-rally rally-ovs task start /root/rally-ovn/workload/create_and_bind_ports.json
TASKID=$($OVNSUDO docker exec ovn-rally rally task list --uuids-only)
# NOTE(mestery): HTML and JSON data are collected differently, look to consolidate
$OVNSUDO docker exec ovn-rally rally task report $TASKID --out /root/create-and-bind-ports-output.html
$OVNSUDO docker exec ovn-rally rally task results $TASKID > ./create-and-bind-ports-data.json
$OVNSUDO docker cp ovn-rally:/root/create-and-bind-ports-output.html .
$OVNSUDO docker exec ovn-rally rally task delete --uuid $TASKID

$OVNSUDO docker ps

# Restore xtrace
$XTRACE

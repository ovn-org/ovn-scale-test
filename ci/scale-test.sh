#!/bin/bash

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set -o xtrace

# Read variables
source ovn-scale.conf

# Library files
source scale-lib.sh

# Register the emulated sandboxes in the rally database
SANDBOXHOSTS=$($OVNSUDO docker exec ovn-rally ls root/rally-ovn/workload/ | grep create-sandbox-)
for sand in $SANDBOXHOSTS ; do
    $OVNSUDO docker exec ovn-rally rally-ovs task start /root/rally-ovn/workload/$sand 2>&1 | tee /tmp/rally-ovs-output.raw
    check_ovn_rally /tmp/rally-ovs-output.raw
    TASKID=$($OVNSUDO docker exec ovn-rally rally task list --uuids-only)
    $OVNSUDO docker exec ovn-rally rally task report $TASKID --out /root/create-sandbox-output.html
    $OVNSUDO docker cp ovn-rally:/root/create-sandbox-output.html .
    $OVNSUDO docker exec ovn-rally rally task delete --uuid $TASKID
done

# Run tests
$OVNSUDO docker exec ovn-rally rally-ovs task start /root/rally-ovn/workload/create_networks.json 2>&1 | tee /tmp/rally-ovs-output.raw
check_ovn_rally /tmp/rally-ovs-output.raw
TASKID=$($OVNSUDO docker exec ovn-rally rally task list --uuids-only)
# NOTE(mestery): HTML and JSON data are collected differently, look to consolidate
$OVNSUDO docker exec ovn-rally rally task report $TASKID --out /root/create-networks-output.html
$OVNSUDO docker exec ovn-rally rally task results $TASKID > ./create-networks-data.json
$OVNSUDO docker cp ovn-rally:/root/create-networks-output.html .
$OVNSUDO docker exec ovn-rally rally task delete --uuid $TASKID
$OVNSUDO rm -rf /tmp/rally-ovs-output.raw

$OVNSUDO docker exec ovn-rally rally-ovs task start /root/rally-ovn/workload/create_and_list_lports.json 2>&1 | tee /tmp/rally-ovs-output.raw
check_ovn_rally /tmp/rally-ovs-output.raw
TASKID=$($OVNSUDO docker exec ovn-rally rally task list --uuids-only)
# NOTE(mestery): HTML and JSON data are collected differently, look to consolidate
$OVNSUDO docker exec ovn-rally rally task report $TASKID --out /root/create-and-list-lports-output.html
$OVNSUDO docker exec ovn-rally rally task results $TASKID > ./create-and-list-lports-data.json
$OVNSUDO docker cp ovn-rally:/root/create-and-list-lports-output.html .
$OVNSUDO docker exec ovn-rally rally task delete --uuid $TASKID
$OVNSUDO rm -rf /tmp/rally-ovs-output.raw

$OVNSUDO docker exec ovn-rally rally-ovs task start /root/rally-ovn/workload/create_and_list_acls.json 2>&1 | tee /tmp/rally-ovs-output.raw
check_ovn_rally /tmp/rally-ovs-output.raw
TASKID=$($OVNSUDO docker exec ovn-rally rally task list --uuids-only)
# NOTE(mestery): HTML and JSON data are collected differently, look to consolidate
$OVNSUDO docker exec ovn-rally rally task report $TASKID --out /root/create-and-list-acls-output.html
$OVNSUDO docker exec ovn-rally rally task results $TASKID > ./create-and-list-acls-data.json
$OVNSUDO docker cp ovn-rally:/root/create-and-list-acls-output.html .
$OVNSUDO docker exec ovn-rally rally task delete --uuid $TASKID
$OVNSUDO rm -rf /tmp/rally-ovs-output.raw

$OVNSUDO docker exec ovn-rally rally-ovs task start /root/rally-ovn/workload/create_and_bind_ports.json 2>&1 | tee /tmp/rally-ovs-output.raw
check_ovn_rally /tmp/rally-ovs-output.raw
TASKID=$($OVNSUDO docker exec ovn-rally rally task list --uuids-only)
# NOTE(mestery): HTML and JSON data are collected differently, look to consolidate
$OVNSUDO docker exec ovn-rally rally task report $TASKID --out /root/create-and-bind-ports-output.html
$OVNSUDO docker exec ovn-rally rally task results $TASKID > ./create-and-bind-ports-data.json
$OVNSUDO docker cp ovn-rally:/root/create-and-bind-ports-output.html .
$OVNSUDO docker exec ovn-rally rally task delete --uuid $TASKID
$OVNSUDO rm -rf /tmp/rally-ovs-output.raw

$OVNSUDO docker exec ovn-rally rally-ovs task start /root/rally-ovn/workload/create_routers.json 2>&1 | tee /tmp/rally-ovs-output.raw
check_ovn_rally /tmp/rally-ovs-output.raw
TASKID=$($OVNSUDO docker exec ovn-rally rally task list --uuids-only)
# NOTE(mestery): HTML and JSON data are collected differently, look to consolidate
$OVNSUDO docker exec ovn-rally rally task report $TASKID --out /root/create-routers-output.html
$OVNSUDO docker exec ovn-rally rally task results $TASKID > ./create-routers-data.json
$OVNSUDO docker cp ovn-rally:/root/create-routers-output.html .
$OVNSUDO docker exec ovn-rally rally task delete --uuid $TASKID
$OVNSUDO rm -rf /tmp/rally-ovs-output.raw

$OVNSUDO docker exec ovn-rally rally-ovs task start /root/rally-ovn/workload/create_routers_bind_ports.json 2>&1 | tee /tmp/rally-ovs-output.raw
check_ovn_rally /tmp/rally-ovs-output.raw
TASKID=$($OVNSUDO docker exec ovn-rally rally task list --uuids-only)
# NOTE(mestery): HTML and JSON data are collected differently, look to consolidate
$OVNSUDO docker exec ovn-rally rally task report $TASKID --out /root/create_routers_bind_ports-output.html
$OVNSUDO docker exec ovn-rally rally task results $TASKID > ./create_routers_bind_ports-data.json
$OVNSUDO docker cp ovn-rally:/root/create_routers_bind_ports-output.html .
$OVNSUDO docker exec ovn-rally rally task delete --uuid $TASKID
$OVNSUDO rm -rf /tmp/rally-ovs-output.raw

$OVNSUDO docker ps

# Restore xtrace
$XTRACE

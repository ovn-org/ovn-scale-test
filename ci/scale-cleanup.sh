#!/bin/bash

# Read variables
source ovn-scale.conf

# Clean everything up
pushd $OVN_SCALE_TOP
sudo /usr/local/bin/ansible-playbook -i $OVN_DOCKER_HOSTS ansible/site.yml -e @$OVN_DOCKER_VARS -e action=clean
popd
$OVNSUDO docker rmi ovn-scale-test-ovn
$OVNSUDO docker rmi ovn-scale-test-base
# Find the <none> image and delete it
$OVNSUDO docker rmi $(docker images | grep none | awk -F' +' '{print $3}')

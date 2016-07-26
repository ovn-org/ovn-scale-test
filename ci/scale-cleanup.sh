#!/bin/bash

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set -o xtrace

# Read variables
source ovn-scale.conf

# Blow away the cache directories. This can cause painful bleeding from the
# eyes when trying to debug why a changed rally config isn't taking place
# in your ovn-rally container, only to realise it's due to this directory
# effectively being a cache which is retained.
CACHEDIR=$(grep node_config_directory $CUR_DIR/ansible/all.yml | cut -d " " -f 2 | sed -e 's/\"//g')
sudo rm -rf $CACHEDIR

# Clean everything up
pushd $OVN_SCALE_TOP
sudo /usr/local/bin/ansible-playbook -i $OVN_DOCKER_HOSTS ansible/site.yml -e @$OVN_DOCKER_VARS -e action=clean
popd
$OVNSUDO docker rmi ovn-scale-test-ovn
$OVNSUDO docker rmi ovn-scale-test-base
# Find the <none> image and delete it
NONEIMAGE=$($OVNSUDO docker images | grep none | awk -F' +' '{print $3}')
if [ "$NONEIMAGE" != "" ] ; then
    $OVNSUDO docker rmi $NONEIMAGE
fi

# Restore xtrace
$XTRACE

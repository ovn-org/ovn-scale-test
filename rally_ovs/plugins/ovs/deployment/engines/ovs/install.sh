#!/bin/bash

OVS_REPO=$1
OVS_BRANCH=$2
OVS_USER=$3
REPO_ACTION=$4

export PATH=$PATH:/usr/sbin

echo "OVS_REPO: $OVS_REPO"
echo "OVS_BRANCH: $OVS_BRANCH"
echo "OVS_USER: $OVS_USER"
echo "REPO_ACTION: $REPO_ACTION"

function is_ovs_installed {
    local installed=0
    if command -v ovs-vswitchd; then
        echo "ovs already installed"
        return 0
    fi

    return 1
}


function install_ovs {
    cd /home/$OVS_USER
    echo "PWD: $PWD"
    if [ -d ovs ] ; then
        cd ovs

        if [ X$REPO_ACTION = X"rebuild" ]; then
            echo "rebuild ovs with no repo change"
        else
            git fetch --all
            repo_change=`git rev-list HEAD...origin/master --count`
            if [ $repo_change = "0" ]; then
                echo "ovs is up-to-date"
                return
            else
                echo "git pull"
                git rebase
            fi
        fi
    else
        echo "git clone -b $OVS_BRANCH $OVS_REPO"
        git clone -b $OVS_BRANCH $OVS_REPO
        cd ovs
    fi

    sudo apt-get install -y --force-yes gcc make automake autoconf \
                      libtool libcap-ng0 libssl1.0.0 python-pip \
                      libjemalloc1 libjemalloc-dev
    sudo pip install six
    ./boot.sh
    mkdir build
    cd build
    CFLAGS='-g -O2' LIBS='-ljemalloc' ../configure --with-linux=/lib/modules/`uname -r`/build
    make -j 6
    sudo make install
    sudo make INSTALL_MOD_DIR=kernel/net/openvswitch modules_install

    sudo modprobe -r vport_geneve
    sudo modprobe -r openvswitch
    sudo modprobe openvswitch
    sudo modprobe vport-geneve

    dmesg | tail
    modinfo /lib/modules/`uname -r`/kernel/net/openvswitch/openvswitch.ko

    sudo chown $OVS_USER /usr/local/var/run/openvswitch
    sudo chown $OVS_USER /usr/local/var/log/openvswitch
}


if  ! is_ovs_installed || [ X$REPO_ACTION != X ] ; then

    if [ X$REPO_ACTION = X"reclone" ] ; then
        echo "Reclone ovs"
        sudo rm -rf ovs
    elif [ X$REPO_ACTION = X"pull" ] ; then
        echo "Pull ovs"
    elif [ X$REPO_ACTION = X"rebuild" ]; then
        echo "Rebuild ovs"
    else
        echo "Install ovs"
    fi

    install_ovs
fi

touch /tmp/ovs_install
echo "Install ovs done"

#!/bin/bash

# Adjust PATH for non-interactive SSH sessions.
export PATH=$PATH:/usr/local/sbin:/usr/sbin

OVS_REPO=$1
OVS_BRANCH=$2
OVS_REPO_ACTION=$3
OVN_REPO=$4
OVN_BRANCH=$5
OVN_REPO_ACTION=$6
OVS_USER=$7

echo "OVS_REPO: $OVS_REPO"
echo "OVS_BRANCH: $OVS_BRANCH"
echo "OvS_REPO_ACTION: $OVS_REPO_ACTION"
echo "OVN_REPO: $OVN_REPO"
echo "OVN_BRANCH: $OVN_BRANCH"
echo "OVN_REPO_ACTION: $OVN_REPO_ACTION"
echo "OVS_USER: $OVS_USER"

function is_ovs_installed {
    local installed=0
    if command -v ovs-vswitchd; then
        echo "ovs already installed"
        return 0
    fi

    return 1
}

function is_ovn_installed {
    local installed=0
    if command -v ovn-controller; then
        echo "ovn already installed"
        return 0
    fi

    return 1
}

function build_ovs {
    CFLAGS='-g -O2' ../configure --with-linux=/lib/modules/`uname -r`/build
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

function build_ovn {
    CFLAGS='-g -O2' LIBS='-ljemalloc' ../configure --with-ovs-source=../../ovs --with-ovs-build=../../ovs/build
    make -j 6
    sudo make install
    sudo chown $OVS_USER /usr/local/var/run/ovn
    sudo chown $OVS_USER /usr/local/var/log/ovn
}

# install COMPONENT REPO REPO_BRANCH REPO_ACTION
# COMPONENT - "ovs" or "ovn"
# REPO
# REPO_BRANCH
# REPO_ACTION - "reclone", "pull", "rebuild" or "none"
function install {
    component=$1
    repo=$2
    repo_branch=$3
    repo_action=$4
    echo repo_action: $repo_action
    if ! is_${component}_installed || [ X$repo_action != Xnone ] ; then
        if [ X$repo_action = X"reclone" ] ; then
            echo "Reclone $component"
            sudo rm -rf $component
        elif [ X$repo_action = X"pull" ] ; then
            echo "Pull $component"
        elif [ X$repo_action = X"rebuild" ]; then
            echo "Rebuild $component"
        else
            echo "Install $component"
        fi

        cd /home/$OVS_USER
        echo "PWD: $PWD"
        if [ -d $component ] ; then
            cd $component

            if [ X$repo_action = X"rebuild" ]; then
                echo "rebuild $component with no repo change"
            else
                git fetch --all
                repo_change=`git rev-list HEAD...origin/master --count`
                if [ $repo_change = "0" ]; then
                    echo "$component is up-to-date"
                    return
                else
                    echo "git pull"
                    git rebase
                fi
            fi
        else
            echo "git clone -b $repo_branch $repo"
            git clone -b $repo_branch $repo
            cd $component
        fi
        sudo apt-get install -y --force-yes gcc make automake autoconf \
                          libtool libcap-ng0 libssl1.0.0 python-pip \
                          libjemalloc1 libjemalloc-dev
        sudo pip install six
        ./boot.sh
        mkdir build
        cd build

        build_$component
        cd ../..
    fi
}

install ovs $OVS_REPO $OVS_BRANCH $OVS_REPO_ACTION
install ovn $OVN_REPO $OVN_BRANCH $OVN_REPO_ACTION

touch /tmp/ovs_install
echo "Install ovs done"

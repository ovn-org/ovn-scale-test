#!/bin/bash

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set -o xtrace

# Read variables
source ovn-scale.conf

# Install prerequisites
$OVNSUDO apt-get update -y
$OVNSUDO apt-get install -y apt-transport-https ca-certificates python-dev libffi-dev libssl-dev gcc make binutils
$OVNSUDO apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 58118E89F3A912897C070ADBF76221572C52609D

if [ "$INSTALLDOCKER" == "True" ] ; then
    if [ ! -f /etc/apt/sources.list.d/docker.list ] ; then
        case $UBUNTUVER in
            14.04)
                $OVNSUDO su -c 'echo "deb https://apt.dockerproject.org/repo ubuntu-trusty main" > /etc/apt/sources.list.d/docker.list'
                ;;
            16.04)
                $OVNSUDO su -c 'echo "deb https://apt.dockerproject.org/repo ubuntu-xenial main" > /etc/apt/sources.list.d/docker.list'
                ;;
            *)
                echo "Warning: Ubuntu version $UBUNTUVER not supported"
                return 1
        esac
        $OVNSUDO apt-get update -y
        $OVNSUDO apt-get purge -y lxc-docker
        $OVNSUDO apt-get install -y apparmor
    fi
fi

# Setup ssh
if [ ! -f ~/.ssh/id_rsa.pub ] ; then
    ssh-keygen -t rsa -f ~/.ssh/id_rsa -N ''
fi

# Add public key to authorized_keys
OVNKEY="$(cat ~/.ssh/id_rsa.pub | cut -d " " -f 2)"
OVNKEYTHERE=$(grep $OVNKEY ~/.ssh/authorized_keys)
if [ "$OVNKEYTHERE" == "" ] ; then
    cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
fi

# Setup ssh
$OVNSUDO su root <<'EOF'
if [ ! -f /root/.ssh/id_rsa.pub ] ; then
    ssh-keygen -t rsa -f /root/.ssh/id_rsa -N ''
fi
EOF

# Add public key to authorized_keys
$OVNSUDO su -m root <<'EOF'
OVNKEY="$(cat /root/.ssh/id_rsa.pub | cut -d " " -f 2)"
OVNKEYTHERE=$(grep $OVNKEY $HOME/.ssh/authorized_keys)
if [ "$OVNKEYTHERE" == "" ] ; then
    cat /root/.ssh/id_rsa.pub >> $HOME/.ssh/authorized_keys
fi
EOF

$OVNSUDO su -m root <<'EOF'
OVNKEY="$(cat /root/.ssh/id_rsa.pub | cut -d " " -f 2)"
OVNKEYTHERE=$(grep $OVNKEY /root/.ssh/authorized_keys)
if [ "$OVNKEYTHERE" == "" ] ; then
    cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys
fi
EOF

# Install python dependencies
$OVNSUDO apt-get install -y python-pip
$OVNSUDO pip install --upgrade pip
$OVNSUDO pip install -U docker-py netaddr
$OVNSUDO apt-get remove -y ansible
$OVNSUDO pip install ansible==2.0.2.0
$OVNSUDO pip install --upgrade setuptools

# Create ${OVN_SCALE_TOP}/ansible/site-ovn-only.yml if needed
if [ ! -f ${OVN_SCALE_TOP}/ansible/site-ovn-only.yml ] ; then
    # Locate first match for "rally" in site.yml, and print all lines that precede it.
    # Also, trim off matched line and the line above it (in OSX, use ghead)
    grep --before-context 666 --max-count 1 rally ${OVN_SCALE_TOP}/ansible/site.yml | \
        head --lines -2 > ${OVN_SCALE_TOP}/ansible/site-ovn-only.yml
fi

# Allow root ssh logins from the local IP and docker subnet
$OVNSUDO su -m root <<'EOF'
if [ ! -f /root/.ssh/config ] ; then
    echo "UserKnownHostsFile=/dev/null" >> /root/.ssh/config
    echo "StrictHostKeyChecking=no" >> /root/.ssh/config
    echo "LogLevel=ERROR" >> /root/.ssh/config
else
    UKHS=$(grep UserKnownHostsFile /root/.ssh/config)
    if [ "$UKHS" == "" ] ; then
        echo "UserKnownHostsFile=/dev/null" >> /root/.ssh/config
    fi
    SHKC=$(grep StrictHostKeyChecking /root/.ssh/config)
    if [ "$SHKC" == "" ] ; then
        echo "StrictHostKeyChecking=no" >> /root/.ssh/config
    fi
    LL=$(grep LogLevel /root/.ssh/config)
    if [ "$LL" == "" ] ; then
        echo "LogLevel=ERROR" >> /root/.ssh/config
    fi
fi
# Determine local ip of this system.
# First, try eth0. Then, try bond0. Lastly, use the address
# of the interface that is used by the default route.
LOCALIP=$(ip addr show dev eth0 | grep 'inet ' | cut -d " " -f 6 | cut -d "/" -f 1)
if [ "$LOCALIP" == "" ] ; then
    # Try bond0
    LOCALIP=$(ip addr show dev bond0 | grep 'inet ' | cut -d " " -f 6 | cut -d "/" -f 1)
fi
if [ "$LOCALIP" == "" ] ; then
    # Try to use interface used in default route
    PHYS_DEV=$(ip route list match 0.0.0.0/0 | grep -oP "(?<=dev )[^\s]*(?=\s)")
    LOCALIP=$(ip -4 addr show $PHYS_DEV | grep -oP "(?<=inet ).*(?=/)")
fi
# Prepare the docker-ovn-hosts file
cat ansible/docker-ovn-hosts-example | sed -e "s/REPLACE_IP/$LOCALIP/g" > ansible/docker-ovn-hosts
# add new line to the end of /etc/ssh/sshd_config, if needed.
# Failure to do so will cause config to smudge that line
[[ $(tail -c1 /etc/ssh/sshd_config | wc -l) == 1 ]] || echo >> /etc/ssh/sshd_config
LRT=$(grep "Match host $LOCALIP" /etc/ssh/sshd_config)
if [ "$LRT" == "" ] ; then
    echo "Match host $LOCALIP" >> /etc/ssh/sshd_config
    echo "    PermitRootLogin without-password" >> /etc/ssh/sshd_config
fi
LDT=$(grep 'Match host 172.17.*.*' /etc/ssh/sshd_config)
if [ "$LDT" == "" ] ; then
    echo "Match host 172.17.*.*" >> /etc/ssh/sshd_config
    echo "    PermitRootLogin without-password" >> /etc/ssh/sshd_config
fi
EOF
$OVNSUDO /etc/init.d/ssh restart

if [ "$INSTALLDOCKER" == "True" ] ; then
    # Install the docker engine
    $OVNSUDO apt-get install -y docker-engine
    case $UBUNTUVER in
    14.04)
        $OVNSUDO service docker start
        ;;
    16.04)
        $OVNSUDO systemctl restart docker
        ;;
    *)
        echo "Warning: Ubuntu version $UBUNTUVER not supported"
        return 1
        ;;
    esac

    # Create a docker group and add $OVNUSER user to this group
    EXISTING_DOCKER=$(cat /etc/group | grep docker)
    if [ "$EXISTING_DOCKER" == "" ]; then
        $OVNSUDO groupadd docker
    fi
    EXISTING_DOCKER_USER=$(cat /etc/group | grep docker | grep $OVNUSER)
    if [ "$EXISTING_DOCKER_USER" == "" ]; then
        $OVNSUDO usermod -aG docker $OVNUSER
        if [ "$OVNSUDO" == "" ] ; then
            echo "WARNING: The docker group was created and the $OVNUSER user added to this group."
            echo "         Please reboot the box, log back in, and re-run $0."
            return 1
        fi
    fi
fi

# Increase maxkeys, see Docker PR here:
# https://github.com/cloudfoundry/bosh/issues/1340
$OVNSUDO sysctl -w kernel/keys/root_maxkeys=10000000
$OVNSUDO sysctl -w kernel/keys/maxkeys=10000000

# Restart docker
case $UBUNTUVER in
14.04)
    $OVNSUDO /etc/init.d/docker restart
    ;;

16.04)
    $OVNSUDO systemctl restart docker
    ;;

*)
    echo "Warning: Ubuntu version $UBUNTUVER not supported"
    return 1
esac

# Restore xtrace
$XTRACE

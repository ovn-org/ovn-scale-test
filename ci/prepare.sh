#!/bin/bash

# Read variables
source ovn-scale.conf

# Install prerequisites
sudo apt-get install -y apt-transport-https ca-certificates
sudo apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 58118E89F3A912897C070ADBF76221572C52609D

if [ ! -f /etc/apt/sources.list.d/docker.list ] ; then
    sudo su -c 'echo "deb https://apt.dockerproject.org/repo ubuntu-trusty main" > /etc/apt/sources.list.d/docker.list' 
    sudo apt-get update -y
    sudo apt-get purge -y lxc-docker 
    sudo apt-get install -y apparmor
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
sudo su root <<'EOF'
if [ ! -f /root/.ssh/id_rsa.pub ] ; then
    ssh-keygen -t rsa -f /root/.ssh/id_rsa -N ''
fi
EOF

# Add public key to authorized_keys
sudo su -m root <<'EOF'
OVNKEY="$(cat /root/.ssh/id_rsa.pub | cut -d " " -f 2)"
OVNKEYTHERE=$(grep $OVNKEY $HOME/.ssh/authorized_keys)
if [ "$OVNKEYTHERE" == "" ] ; then
    cat /root/.ssh/id_rsa.pub >> $HOME/.ssh/authorized_keys
fi
EOF

# Install the docker engine
sudo apt-get install -y docker-engine
sudo service docker start

# Create a docker group and add ubuntu user to this group
EXISTING_DOCKER=$(cat /etc/group | grep docker)
if [ "$EXISTING_DOCKER" == "" ]; then
    sudo groupadd docker
    sudo usermod -aG docker ubuntu
    echo "WARNING: The docker group was created and the ubuntu user added to this group."
    echo "         Please reboot the box, log back in, and re-run $0."
    exit 1
fi

# Install python dependencies
sudo apt-get install -y python-pip
sudo pip install --upgrade pip
sudo pip install -U docker-py netaddr
sudo apt-get remove -y ansible
sudo pip install ansible==2.0.2.0

# Prepate the docker-ovn-hosts file
LOCALIP=$(ifconfig eth0|grep 'inet ' | sed -e 's/ \+/ /g' | cut -d " " -f 3 | cut -d ":" -f 2)

cat ansible/docker-ovn-hosts-example | sed -e "s/REPLACE_IP/$LOCALIP/g" > ansible/docker-ovn-hosts

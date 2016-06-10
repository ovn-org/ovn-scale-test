#!/bin/bash
set -eu

run() {
    (cd "$sandbox" && "$@") || exit 1
}


schema=/usr/local/share/openvswitch/vswitch.ovsschema
ovnsb_schema=/usr/local/share/openvswitch/ovn-sb.ovsschema
ovnnb_schema=/usr/local/share/openvswitch/ovn-nb.ovsschema

controller_ip=$1
device=$2

#
# IP related code start
#
declare -a IP_CIDR_ARRAY
declare -A IP_NETMASK_TABLE

function get_ip_cidrs {
    dev=$1

    i=0
    IFS=$'\n'
    #echo "$dev ip cidrs:"
    #echo "---------------------------"
    for inet in `ip addr show $dev | grep -e 'inet\b'` ; do
        local ip_cidr=`echo $inet | \
            sed -n  -e  's%.*inet \(\([0-9]\{1,3\}\.\)\{3\}[0-9]\{1,3\}/[0-9]\+\) .*%\1%p'`

        IFS=' '
        read ip_addr netmask <<<$(echo $ip_cidr | sed -e 's/\// /')
        IP_CIDR_ARRAY[i]=$ip_cidr
        IP_NETMASK_TABLE[$ip_addr]=$netmask

        #echo "    cidr $ip_cidr"
        ((i+=1))
    done

    #echo IP_CIDR_ARRAY: ${IP_CIDR_ARRAY[@]}
}


function in_array # ( keyOrValue, arrayKeysOrValues )
{
    local elem=$1

    IFS=' '
    local i
    for i in "${@:2}"; do
        #echo "$i == $elem"
        [[ "$i" == "$elem" ]] && return 0;
    done

    return 1
}


function get_ip_from_cidr {
    local cidr=$1
    echo $cidr | cut -d'/' -f1
}

function get_netmask_from_cidr {
    local cidr=$1
    echo $cidr | cut -d'/' -f2
}


function ip_addr_add {
    local ip=$1
    local dev=$2

    if in_array $ip ${IP_CIDR_ARRAY[@]} ; then
        echo "$ip is already on $dev"
        return
    fi

    echo "Add $ip to $dev"
    sudo ip addr add $ip dev $dev
}


function ip_cidr_fixup {
    local ip=$1
    if [[ ! "$ip" =~ "/" ]] ; then
        echo $ip"/32"
        return
    fi

    echo $ip
}

#
# IP related code end
#

# Create sandbox.
# sandbox_name="controller-sandbox"
sandbox_name="/usr/local/var/run/openvswitch/"

sandbox=$sandbox_name

# Get ip addresses on net device
get_ip_cidrs $device


# A UUID to uniquely identify this system.  If one is not specified, a random
# one will be generated.  A randomly generated UUID will be saved in a file
# 'ovn-uuid'.
OVN_UUID=${OVN_UUID:-}

function configure_ovn {
    echo "Configuring OVN"

    if [ -z "$OVN_UUID" ] ; then
        if [ -f /usr/local/var/run/openvswitch/ovn-uuid ] ; then
            OVN_UUID=$(cat /usr/local/var/run/openvswitch/ovn-uuid)
        else
            OVN_UUID=$(uuidgen)
            echo $OVN_UUID > /usr/local/var/run/openvswitch/ovn-uuid
        fi
    fi
}


function init_ovsdb_server {

    server_name=$1
    db=$2
    db_sock=`basename $2`

    #Wait for ovsdb-server to finish launching.
    echo -n "Waiting for $server_name to start..."
    while test ! -e "$sandbox"/$db_sock; do
        sleep 1;
    done
    echo "  Done"

    run ovs-vsctl --db=$db --no-wait -- init
}


function start_ovs {
    # Create database and start ovsdb-server.
    echo "Starting OVS"

    CON_IP=`get_ip_from_cidr $controller_ip`
    echo "controller ip: $CON_IP"

    EXTRA_DBS=""
    OVSDB_REMOTE=""

    OVSDB_REMOTE="ptcp\:6640\:$CON_IP"

    #Add a small delay to allow ovsdb-server to launch.
    sleep 0.1

    init_ovsdb_server "ovsdb-server-nb" unix:/usr/local/var/run/openvswitch/ovnnb_db.sock
    init_ovsdb_server "ovsdb-server-sb" unix:/usr/local/var/run/openvswitch/ovnsb_db.sock

    ovs-vsctl --db=unix:/usr/local/var/run/openvswitch/ovnsb_db.sock --no-wait \
        -- set open_vswitch .  manager_options=@uuid \
        -- --id=@uuid create Manager target="$OVSDB_REMOTE" inactivity_probe=0
}

function start_ovn {
    echo "Starting OVN northd"

    run ovn-northd  --no-chdir --pidfile \
              -vconsole:off -vsyslog:off -vfile:info --log-file \
              --ovnnb-db=unix:/usr/local/var/run/openvswitch/ovnnb_db.sock \
              --ovnsb-db=unix:/usr/local/var/run/openvswitch/ovnsb_db.sock
}

configure_ovn

start_ovs

start_ovn

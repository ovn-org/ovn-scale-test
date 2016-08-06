#! /bin/bash
set -eu

run() {
    (cd "$sandbox" && "$@") || exit 1
}

schema=/usr/local/share/openvswitch/vswitch.ovsschema

controller_ip=$1
host_ip=$2
device=$3

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


function ip_addr_del {
    local ip=$1
    local dev=$2

    if ! in_array $ip ${IP_CIDR_ARRAY[@]} ; then
        echo "$ip is not on $dev"
        return
    fi

    if [ X"${IP_CIDR_ARRAY[0]}" = X"$ip" ] ; then
        echo "skip main ip $ip on $dev"
        return
    fi

    echo "Delete $ip from $dev"
    sudo ip addr del $ip dev $dev

    IP_CIDR_ARRAY=( ${IP_CIDR_ARRAY[@]/"$ip"/} )
    #echo IP_CIDR_ARRAY: ${IP_CIDR_ARRAY[@]}
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
sandbox_name="/usr/local/var/run/openvswitch/"
sandbox=$sandbox_name

# Get ip addresses on net device
get_ip_cidrs $device
host_ip=`ip_cidr_fixup $host_ip`

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
    while test ! -e /usr/local/var/run/openvswitch/$db_sock; do
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

    SANDBOX_BIND_IP=""
    EXTRA_DBS=""
    OVSDB_REMOTE=""

    touch "$sandbox"/.conf.db.~lock~
    rm -f conf.db
    run ovsdb-tool create conf.db "$schema"

    run ovsdb-server --detach --no-chdir --pidfile \
        -vconsole:off -vsyslog:off -vfile:info --log-file \
        --remote=punix:"$sandbox"/db.sock \
        conf.db

    #Add a small delay to allow ovsdb-server to launch.
    sleep 0.1

    init_ovsdb_server "ovsdb-server" unix:"$sandbox"/db.sock
    run ovs-vsctl --no-wait set open_vswitch . system-type="sandbox"

    OVN_REMOTE="tcp:$CON_IP:6640"

    ip_addr_add $host_ip $device
    SANDBOX_BIND_IP=$host_ip

    run ovs-vsctl --no-wait set open_vswitch . external-ids:system-id="$OVN_UUID"
    ovs-vsctl --no-wait set open_vswitch . external-ids:ovn-remote="$OVN_REMOTE"
    ovs-vsctl --no-wait set open_vswitch . external-ids:ovn-remote-probe-interval=0
    ovs-vsctl --no-wait set open_vswitch . external-ids:ovn-bridge="br-int"
    ovs-vsctl --no-wait set open_vswitch . external-ids:ovn-encap-type="geneve"
    ovs-vsctl --no-wait set open_vswitch . external-ids:ovn-encap-ip="$host_ip"

    ovs-vsctl --no-wait -- --may-exist add-br br-int
    ovs-vsctl --no-wait br-set-external-id br-int bridge-id br-int
    ovs-vsctl --no-wait set bridge br-int fail-mode=secure other-config:disable-in-band=true

    ovs-vsctl --no-wait --may-exist add-br br0
    ovs-vsctl --no-wait set open_vswitch . external-ids:ovn-bridge-mappings=providernet:br0

    run ovs-vswitchd --detach --no-chdir --pidfile \
        -vconsole:off -vsyslog:off -vfile:info --log-file \
        --enable-dummy=override # -vvconn:info -vnetdev_dummy:info
}

function start_ovn {
    echo "Starting OVN"

    run ovn-controller --no-chdir --pidfile \
                    -vconsole:off -vsyslog:off -vfile:info --log-file
}

configure_ovn

start_ovs

start_ovn

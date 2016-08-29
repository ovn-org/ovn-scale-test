#! /bin/bash
#
# Copyright (c) 2013, 2015 Nicira, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#set -e # exit on first error
#set -x

run() {
    (cd "$sandbox" && "$@") || exit 1
}


run_service() {
    local name=$1
    shift
    echo $@ > $sandbox_name/$name.sh
    run $@
}


builddir=
srcdir=
schema=
installed=true
built=false

ovn=false
controller=false
ovnsb_schema=
ovnnb_schema=
controller_ip="127.0.0.1"
host_ip="127.0.0.1/8"
device="eth0"

session=false

start=
stop=
cleanup=
cleanup_all=false
graceful=false

for option; do
    # This option-parsing mechanism borrowed from a Autoconf-generated
    # configure script under the following license:

    # Copyright (C) 1992, 1993, 1994, 1995, 1996, 1998, 1999, 2000, 2001,
    # 2002, 2003, 2004, 2005, 2006, 2009, 2013 Free Software Foundation, Inc.
    # This configure script is free software; the Free Software Foundation
    # gives unlimited permission to copy, distribute and modify it.

    # If the previous option needs an argument, assign it.
    if test -n "$prev"; then
        eval $prev=\$option
        prev=
        continue
    fi
    case $option in
        *=*) optarg=`expr "X$option" : '[^=]*=\(.*\)'` ;;
        *) optarg=yes ;;
    esac

    case $dashdash$option in
        --)
            dashdash=yes ;;
        -h|--help)
            cat <<EOF
ovs-sandbox, for starting a sandboxed dummy Open vSwitch environment
usage: $0 [OPTION...]

If you run ovs-sandbox from an OVS build directory, it uses the OVS that
you built.  Otherwise, if you have an installed Open vSwitch, it uses
the installed version.

These options force ovs-sandbox to use a particular OVS build:
  -b, --builddir=DIR   specify Open vSwitch build directory
  -s, --srcdir=DIR     specify Open vSwitch source directory
These options force ovs-sandbox to use an installed Open vSwitch:
  -i, --installed      use installed Open vSwitch
  -S, --schema=FILE    use FILE as vswitch.ovsschema
  -o, --ovn            enable OVN
  -c, --controller     enable OVN controller

Other options:
  -h, --help           Print this usage message.
  -c, --controller-ip  The IP of the controller node
  -H, --host-ip        The host ip of the sandbox
  -D, --device         The network device which has the host ip, default is eth0
  -S, --session        Open a bash for running OVN/OVS tools in the
                       dummy Open vSwitch environment
  --start=SANDBOX      Start the sandbox [TODO]
  --stop=SANDBOX       Stop the sandbox [TODO]
  --cleanup=SANDBOX    Cleanup the sandbox
  --cleanup-all        Cleanup all sandboxes
  --graceful           Graceful cleanup/stop sandbox
EOF
            exit 0
            ;;

        --b*=*)
            builddir=$optarg
            built=:
            ;;
        -b|--b*)
            prev=builddir
            built=:
            ;;
        --sr*=*)
            srcdir=$optarg
            built=false
            ;;
        -s|--sr*)
            prev=srcdir
            built=false
            ;;
        -i|--installed)
            installed=:
            ;;
        --sc*=*)
            schema=$optarg
            installed=:
            ;;
        -S|--sc*)
            prev=schema
            installed=:
            ;;
        -o|--ovn)
            ovn=true
            ;;
        -c|--controller)
            controller=true;
            ;;
        -S|--session)
            session=true;
            ;;
        --start)
            prev=start
            ;;
        --stop)
            prev=stop
            ;;
        --cleanup)
            prev=cleanup
            ;;
        --cleanup-all)
            cleanup_all=true
            ;;
        --graceful)
            graceful=true;
            ;;
        -c|--controller-ip)
            prev=controller_ip
            ;;
        -H|--host-ip)
            prev=host_ip
            ;;
        -D|--device)
            prev=device
            ;;
        -*)
            echo "unrecognized option $option (use --help for help)" >&2
            exit 1
            ;;
        *)
            echo "$option: non-option arguments not supported (use --help for help)" >&2
            exit 1
            ;;
    esac
    shift
done


if $installed && $built; then
    echo "sorry, conflicting options (use --help for help)" >&2
    exit 1
elif $installed || $built; then
    :
elif test -e vswitchd/ovs-vswitchd; then
    built=:
    builddir=.
elif (ovs-vswitchd --version) >/dev/null 2>&1; then
    installed=:
else
    echo "can't find an OVS build or install (use --help for help)" >&2
    exit 1
fi


if $built; then
    if test ! -e "$builddir"/vswitchd/ovs-vswitchd; then
        echo "$builddir does not appear to be an OVS build directory" >&2
        exit 1
    fi
    builddir=`cd $builddir && pwd`

    # Find srcdir.
    case $srcdir in
        '')
            srcdir=$builddir
            if test ! -e "$srcdir"/WHY-OVS.md; then
                srcdir=`cd $builddir/.. && pwd`
            fi
            ;;
        /*) ;;
        *) srcdir=`pwd`/$srcdir ;;
    esac
    schema=$srcdir/vswitchd/vswitch.ovsschema
    if test ! -e "$schema"; then
        echo >&2 'source directory not found, please use --srcdir'
        exit 1
    fi
    if $ovn; then
        ovnsb_schema=$srcdir/ovn/ovn-sb.ovsschema
        if test ! -e "$ovnsb_schema"; then
            echo >&2 'source directory not found, please use --srcdir'
            exit 1
        fi
        ovnnb_schema=$srcdir/ovn/ovn-nb.ovsschema
        if test ! -e "$ovnnb_schema"; then
            echo >&2 'source directory not found, please use --srcdir'
            exit 1
        fi
        vtep_schema=$srcdir/vtep/vtep.ovsschema
        if test ! -e "$vtep_schema"; then
            echo >&2 'source directory not found, please use --srcdir'
            exit 1
        fi
    fi

    # Put built tools early in $PATH.
    if test ! -e $builddir/vswitchd/ovs-vswitchd; then
        echo >&2 'build not found, please change set $builddir or change directory'
        exit 1
    fi
    PATH=$builddir/ovsdb:$builddir/vswitchd:$builddir/utilities:$builddir/vtep:$PATH
    if $ovn; then
        PATH=$builddir/ovn:$builddir/ovn/controller:$builddir/ovn/controller-vtep:$builddir/ovn/northd:$builddir/ovn/utilities:$PATH
    fi
    export PATH
else
    case $schema in
        '')
            for schema in \
                /usr/local/share/openvswitch/vswitch.ovsschema \
                /usr/share/openvswitch/vswitch.ovsschema \
                none; do
                if test -r $schema; then
                    break
                fi
            done
            ;;
        /*) ;;
        *) schema=`pwd`/$schema ;;
    esac
    if test ! -r "$schema"; then
        echo "can't find vswitch.ovsschema, please specify --schema" >&2
        exit 1
    fi
    ovnsb_schema=`dirname $schema`/ovn-sb.ovsschema
    ovnnb_schema=`dirname $schema`/ovn-nb.ovsschema
fi


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

# Create sandbox.
if $controller; then
    sandbox_name="controller-sandbox"
else
    sandbox_name="sandbox-`get_ip_from_cidr $host_ip`"
fi

sandbox=`pwd`/$sandbox_name

function is_sandbox {
    local box_name=$1

    if [ ! -d $box_name ] || [ ! -f $box_name/sandbox.rc ] ; then
        return 1
    fi

    return 0
}


function app_start {
    local proc=$1

    if [ ! -f $OVS_RUNDIR/$proc.sh ]; then
        return
    fi

    if [ -f $OVS_RUNDIR/$proc.pid ]; then
        echo "$proc is already running"
        return
    fi

    if $(cd "$OVS_RUNDIR" && . $proc.sh) ; then
        echo "$proc start"
    else
        echo "start $proc failed"
    fi
}


function app_exit {
    local proc=$1
    local pid=

    if [ -f $OVS_RUNDIR/$proc.pid ] ; then
        echo "$proc exit"
        pid=`cat $OVS_RUNDIR/$proc.pid`
        if $graceful ; then
            # TODO: ovsdb-server-sb has bug to process lastest ovn-controller's
            #       exit message, so add a timeout here to avoid blocking forever
            local exit_success=true
            ovs-appctl --timeout 5 -t $OVS_RUNDIR/$proc.$pid.ctl exit || exit_success=false
            if $exit_success; then
                local wait_until=`date +%s%3N`
                (( wait_until += 15000 ))

                while test -e "$OVS_RUNDIR"/$proc.pid; do
                    sleep 0.5;
                    if [ `date +%s%3N` -gt $wait_until ] ; then
                        echo "Wait $proc exit timeout"
                        kill $pid
                        break
                    fi
                done
            else
                echo "Exit $proc by ovs-appctl exit timeout"
                kill $pid
            fi

        else
            kill $pid
        fi

        rm -f $OVS_RUNDIR/$proc.$pid.ctl # the file was renamed, remove it forcely
    fi
}

function do_start {

    local box_name=$1
    if ! is_sandbox $box_name ; then
        echo "Not found sandbox $box_name"
        return 1
    fi

    . $box_name/sandbox.rc 2>/dev/null
    app_start ovn-northd
    app_start ovsdb-server-nb
    app_start ovsdb-server-sb
    app_start ovn-controller
    app_start ovsdb-server
    app_start ovs-vswitchd
}


function do_stop {

    local box_name=$1
    if ! is_sandbox $box_name ; then
        echo "Not found sandbox $box_name"
        return 1
    fi

    . $box_name/sandbox.rc 2>/dev/null

    app_exit ovn-northd
    app_exit ovsdb-server-nb
    app_exit ovsdb-server-sb
    app_exit ovn-controller
    app_exit ovsdb-server
    app_exit ovs-vswitchd
}

function do_cleanup {

    local box_name=$1

    if ! is_sandbox $box_name ; then
        echo "Not found sandbox $box_name"
        return 1
    fi

    echo "CLEANUP: $box_name"

    do_stop $box_name

    # Ensure cleanup.
    pids=`cat "$box_name"/*.pid 2>/dev/null`
    [ -n "$pids" ] && kill -15 `echo $pids`


    if [ X"$SANDBOX_BIND_IP" != X"" ] ; then
        get_ip_cidrs $SANDBOX_BIND_DEV
        ip_addr_del $SANDBOX_BIND_IP $SANDBOX_BIND_DEV
    fi

    rm -rf $box_name
}


function cleanup_all {

    local all
    for i in `ls -d *sandbox*`; do
        if [ ! -d $i ] || [ ! -f $i/sandbox.rc ]; then
            continue
        fi
        all="$all $i"
    done

    echo $all

    for i in $all; do
        do_cleanup $i
    done
}

if [ X$start != X ]; then
    do_start $start
    exit $?
fi

if [ X$stop != X ]; then
    do_stop $stop
    exit $?
fi

if $cleanup_all ; then
    cleanup_all
    exit 0
fi

if [ X$cleanup != X ] ; then
    do_cleanup $cleanup
    exit $?
fi


do_cleanup $sandbox_name

# Get ip addresses on net device
get_ip_cidrs $device
host_ip=`ip_cidr_fixup $host_ip`

mkdir $sandbox_name


# Set up environment for OVS programs to sandbox themselves.
cat > $sandbox_name/sandbox.rc <<EOF
OVS_RUNDIR=$sandbox; export OVS_RUNDIR
OVS_LOGDIR=$sandbox; export OVS_LOGDIR
OVS_DBDIR=$sandbox; export OVS_DBDIR
OVS_SYSCONFDIR=$sandbox; export OVS_SYSCONFDIR
EOF

. $sandbox_name/sandbox.rc

# A UUID to uniquely identify this system.  If one is not specified, a random
# one will be generated.  A randomly generated UUID will be saved in a file
# 'ovn-uuid'.
OVN_UUID=${OVN_UUID:-}

function configure_ovn {
    echo "Configuring OVN"

    if [ -z "$OVN_UUID" ] ; then
        if [ -f $OVS_RUNDIR/ovn-uuid ] ; then
            OVN_UUID=$(cat $OVS_RUNDIR/ovn-uuid)
        else
            OVN_UUID=$(uuidgen)
            echo $OVN_UUID > $OVS_RUNDIR/ovn-uuid
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

    SANDBOX_BIND_IP=""
    EXTRA_DBS=""
    OVSDB_REMOTE=""
    if $controller ; then
        if $ovn ; then

            touch "$sandbox"/.conf-nb.db.~lock~
            touch "$sandbox"/.conf-sb.db.~lock~
            rm -f conf-nb.db conf-sb.db
            run ovsdb-tool create conf-nb.db "$schema"
            run ovsdb-tool create conf-sb.db "$schema"

            touch "$sandbox"/.ovnsb.db.~lock~
            touch "$sandbox"/.ovnnb.db.~lock~
            rm -f ovnsb.db ovnnb.db
            run ovsdb-tool create ovnsb.db "$ovnsb_schema"
            run ovsdb-tool create ovnnb.db "$ovnnb_schema"

            ip_addr_add $controller_ip $device
            SANDBOX_BIND_IP=$controller_ip

            OVSDB_REMOTE="ptcp\:6640\:$CON_IP"

            cat >> $sandbox_name/sandbox.rc <<EOF
OVN_NB_DB=unix:$sandbox/db-nb.sock; export OVN_NB_DB
OVN_SB_DB=unix:$sandbox/db-sb.sock; export OVN_SB_DB
EOF
            . $sandbox_name/sandbox.rc

            # Northbound db server
            prog_name='ovsdb-server-nb'
            run_service $prog_name ovsdb-server --detach --no-chdir \
                --pidfile=$prog_name.pid \
                --unixctl=$prog_name.ctl \
                -vconsole:off -vsyslog:off -vfile:info \
                --log-file=$prog_name.log \
                --remote=p$OVN_NB_DB \
                conf-nb.db ovnnb.db
            pid=`cat $sandbox_name/$prog_name.pid`
            mv $sandbox_name/$prog_name.ctl $sandbox_name/$prog_name.$pid.ctl

            # Southbound db server
            prog_name='ovsdb-server-sb'
            run_service $prog_name ovsdb-server --detach --no-chdir \
                --pidfile=$prog_name.pid \
                --unixctl=$prog_name.ctl \
                -vconsole:off -vsyslog:off -vfile:info \
                --log-file=$prog_name.log \
                --remote="p$OVN_SB_DB" \
                --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
                conf-sb.db ovnsb.db
            pid=`cat $sandbox_name/$prog_name.pid`
            mv $sandbox_name/$prog_name.ctl $sandbox_name/$prog_name.$pid.ctl

        fi
    else
        touch "$sandbox"/.conf.db.~lock~
        rm -f conf.db
        run ovsdb-tool create conf.db "$schema"

        run_service ovsdb-server ovsdb-server --detach --no-chdir --pidfile \
            -vconsole:off -vsyslog:off -vfile:info --log-file \
            --remote=punix:"$sandbox"/db.sock \
            conf.db
    fi



    #Add a small delay to allow ovsdb-server to launch.
    sleep 0.1

    # Initialize database.
    if $controller ; then
        init_ovsdb_server "ovsdb-server-nb" $OVN_NB_DB
        init_ovsdb_server "ovsdb-server-sb" $OVN_SB_DB

        ovs-vsctl --db=$OVN_SB_DB --no-wait \
            -- set open_vswitch .  manager_options=@uuid \
            -- --id=@uuid create Manager target="$OVSDB_REMOTE" inactivity_probe=0

    else
        init_ovsdb_server "ovsdb-server" unix:"$sandbox"/db.sock
        run ovs-vsctl --no-wait set open_vswitch . system-type="sandbox"

        if $ovn ; then
            OVN_REMOTE="tcp:$CON_IP:6640"

            ip_addr_add $host_ip $device
            SANDBOX_BIND_IP=$host_ip

            run ovs-vsctl --no-wait \
                -- set open_vswitch . external-ids:system-id="$OVN_UUID" \
                                      external-ids:ovn-remote="$OVN_REMOTE" \
                                      external-ids:ovn-remote-probe-interval=0 \
                                      external-ids:ovn-bridge="br-int" \
                                      external-ids:ovn-encap-type="geneve" \
                                      external-ids:ovn-encap-ip="$host_ip"

            run ovs-vsctl --no-wait \
                -- --may-exist add-br br-int \
                -- br-set-external-id br-int bridge-id br-int \
                -- set bridge br-int fail-mode=secure other-config:disable-in-band=true \

            run ovs-vsctl --no-wait \
                -- --may-exist add-br br0 \
                -- set open_vswitch . external-ids:ovn-bridge-mappings=providernet:br0

            run_service ovs-vswitchd ovs-vswitchd --detach --no-chdir --pidfile \
                            -vconsole:off -vsyslog:off -vfile:info --log-file \
                            --enable-dummy=override # -vvconn:info -vnetdev_dummy:info

        else
            :
        fi
    fi

    cat >> $sandbox_name/sandbox.rc <<EOF
SANDBOX_BIND_IP=$SANDBOX_BIND_IP; export SANDBOX_BIND_IP
SANDBOX_BIND_DEV=$device; export SANDBOX_BIND_DEV
EOF


}


function start_ovn {
    echo "Starting OVN"

    if $controller ; then
        run_service ovn-northd ovn-northd --detach --no-chdir --pidfile \
              -vconsole:off -vsyslog:off -vfile:info --log-file \
              --ovnnb-db=$OVN_NB_DB \
              --ovnsb-db=$OVN_SB_DB
    else
        if $ovn ; then
            run_service ovn-controller ovn-controller --detach --no-chdir \
                    --pidfile \
                    -vconsole:off -vsyslog:off -vfile:info --log-file
        fi
    fi
}


if $ovn ; then
    configure_ovn

    start_ovs

    start_ovn
else
    start_ovs
fi

if ! $session ; then
    exit 0
fi


cat <<EOF

----------------------------------------------------------------------
You are running in a dummy Open vSwitch environment.  You can use
ovs-vsctl, ovs-ofctl, ovs-appctl, and other tools to work with the
dummy switch.

Log files, pidfiles, and the configuration database are in the
"sandbox" subdirectory.

Exit the shell to kill the running daemons.
EOF

status=0; $SHELL || status=$?

cat <<EOF
----------------------------------------------------------------------



EOF

exit $status

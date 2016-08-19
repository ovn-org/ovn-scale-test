#!/bin/bash

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set -o xtrace

function check_container_failure {
    sleep 5

    docker ps -a
    failed_containers=$(docker ps -a --format "{{.Names}}" --filter status=exited)

    if [ "$failed_containers" ]; then
        for failed in ${failed_containers}; do
            docker logs --tail all ${failed}
        done
        exit 1
    fi
}

function check_ovn_rally {
    output_file=$1
    count=`cat $output_file | grep total | grep 100 | wc -l`
    if [ $count -ne 0 ]
    then
        echo "Rally run succeeded"
    else
        echo "Rally run failed"
        exit 1
    fi
}

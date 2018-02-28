#!/bin/bash

# Copyright 2008-2018 Univa Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

POLLING_INTERVAL="300"

# terminate after 57 minutes
TTL=57

readonly TEMP=$(getopt -o v,n: --long verbose,debug,help,software-profile:,count: -n $(basename $0) -- "$@")
[[ $? -eq 0 ]] || {
    echo "Terminating..." >&2
    exit 1
}

eval set -- "${TEMP}"

count=1

function usage() {
    echo "usage: $(basename $0) --software-profile <name>" >&2
    exit 1
}

while true; do
    case "$1" in
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        --software-profile)
            software_profile=${2}
            shift 2
            ;;
        --hardware-profile)
            hardware_profile=${2}
            shift 2
            ;;
        --count|-n)
            count=$2
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "Internal error!" >&2
            exit 1
            ;;
    esac
done

[[ -n ${software_profile} ]] || {
    usage
    exit 1
}

# Use Python helper script to determine which hosts in the UGE cluster are
# currently unused (used slot count is 0)

source /opt/tortuga/etc/tortuga.sh
source /opt/uge-8.5.0/default/common/settings.sh

readonly spe_kitdir=$(get-kit-list | grep simple_policy_engine)

execdhost=$(/opt/tortuga/kits/kit-${spe_kitdir}/examples/simple_burst/get-idle-node --polling-interval $POLLING_INTERVAL --ttl ${TTL} --software-profile ${software_profile} | head -n 1)

RET=$?

if [[ ${RET} -ne 0 ]] || [[ -z ${execdhost} ]]; then exit 1; fi

# Disable host from accepting add'l jobs. This will prevent jobs from being
# scheduled in the time between the node being selected for idling and the
# actual idle process.

qmod -d \*@${execdhost}

# Instruct Tortuga to delete node
delete-node --node ${execdhost}

exit 0

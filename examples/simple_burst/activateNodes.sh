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

readonly TEMP=$(getopt -o v,n: --long verbose,debug,help,software-profile:,hardware-profile:,count: -n $(basename $0) -- "$@")
[[ $? -eq 0 ]] || {
    echo "Terminating..." >&2
    exit 1
}

eval set -- "${TEMP}"

count=1

function usage() {
    echo "usage: $(basename $0) --software-profile <name> --hardware-profile <name>" >&2
    exit 1
}

while true; do
    case "$1" in
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        --software-profile)
            software_profile=$2
            shift 2
            ;;
        --hardware-profile)
            hardware_profile=$2
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

[[ -n ${software_profile} ]] && [[ -n ${hardware_profile} ]] || {
    usage
    exit 1
}

. /opt/tortuga/etc/tortuga.sh

# Convert float value to integer
count=$(printf "%d" ${count})

# Do not allow add operation to proceed if any nodes in the burst profile
# are not in the 'Installed' state. This prevents the burst operation from
# running away in the event of failed provisioning.
[[ $(get-node-status --list --software-profile ${software_profile} --not-installed) -eq 0 ]] || {
    echo "Add nodes operation currently in progress..." >&2
    exit 1
}

add-nodes --count ${count} \
    --software-profile ${software_profile} \
    --hardware-profile ${hardware_profile}

exit 0

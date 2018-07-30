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

readonly curdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

verbose=0
enable=
do_not_prompt=0
slots_per_host=0

ARGS=$(getopt -o v,y -l verbose,enable,no-enable,yes,slots-per-host: -- "$@")
[[ $? -eq 0 ]] || {
    echo "Terminating..." >&2
    exit 1
}

eval set -- "${ARGS}"

while true; do
    case $1 in
        -v|--verbose)
            verbose=1
            shift
            ;;
        -y|--yes)
            do_not_prompt=1
            shift
            ;;
        --enable)
            enable=1
            shift
            ;;
        --no-enable)
            enable=0
            shift
            ;;
        --slots-per-host)
            [[ $2 -ge 1 ]] || {
                echo "Error: invalid argument to --slots-per-host specified" >&2
                exit 1
            }
            slots_per_host=$2
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

[[ -n $TORTUGA_ROOT ]] || {
    echo "Error: Tortuga environment must be sourced before running this script" >&2
    exit 1
}

[[ -n $SGE_ROOT ]] && $(type -P qconf &>/dev/null) || {
    echo "Error: Univa Grid Engine must be installed before running this script" >&2
    exit 1
}

readonly uge_clusters=($(uge-cluster list))

[[ -n $uge_clusters ]] || {
    echo "Error: no UGE clusters available" >&2
    exit 1
}

. ${curdir}/settings.sh

is_resadapter_enabled() {
    local hwprofile=$1
    local readapter=$2

    get-hardware-profile --name ${hwprofile} | grep "<resourceadapter" | \
        cut -f3 -d= | sed 's/[\">]//g' | grep -qx ${resadapter}
}

resadapters=($(get-resource-adapter-list | grep -v ^default$))

[[ ${#resadapters[@]} -eq 1 ]] || {
    echo "Error: you must have at least one resource adapter installed." >&2
    exit 1
}

readonly resadapter=${resadapters[0]}

[[ $do_not_prompt -eq 0 ]] && {
    echo -n "Do you wish to enable cloud bursting for ${resadapter} [N/y]? "
    read response
    [[ -z $response ]] || [[ $(echo ${response} | grep "^[Nn]") ]] && {
        echo "Aborted by user." >&2
        exit 1
    }
}

[[ -f ${curdir}/generate.py ]] || {
    echo "Error: missing template generator script (generate.py)" >&2
    exit 1
}

echo -n "Checking if Simple Policy Engine is enabled... "

! $(get-component-list -p | grep -q "simple_policy_engine-.* engine-.*") && {
    echo "no"

    # Enable 'engine' component from simple policy engine
    component_name=$(get-component-list | grep "simple_policy_engine-.* engine-.*")

    [[ -n ${component_name} ]] || {
        echo "Error: unable to find 'engine' component in simple policy engine kit" >&2
        exit 1
    }

    echo -n "Enabling Simple Policy Engine component... "

    enable-component -p ${component_name}
    [[ $? -eq 0 ]] && {
        echo "done."
    } || {
        echo "warning"
        echo "Warning: non-zero exit code from 'enable-component'" >&2
    }

    # Puppet sync
    echo -n "Running Puppet sync... "
    /opt/puppetlabs/bin/puppet agent --onetime --no-daemonize
}

echo "done."

get-software-profile --name ${burst_swprofile} &>/dev/null
[[ $? -eq 0 ]] || {
    echo -n "Creating software profile '${burst_swprofile}'... "

    create-software-profile --name ${burst_swprofile} --no-os-media-required

    echo "done."

    echo -n "  - Enabling execd component... "
    enable-component --software-profile ${burst_swprofile} execd &>/dev/null
    uge-cluster update ${cluster_name} --add-execd-swprofile ${burst_swprofile}
    echo "done."
}

# Create software profile configuration to ensure all nodes in
# ${burst_swprofile} are added to ${uge_burst_hostgroup}
readonly filename=${SGE_ROOT}/${SGE_CELL}/common/config.${burst_swprofile}
echo -n "Creating software profile/hostgroup mapping... "
echo ${uge_burst_hostgroup} >${filename}
echo "done."

get-hardware-profile --name ${burst_hwprofile} &>/dev/null
[[ $? -eq 0 ]] || {
    echo -n "Checking for provisioning network... "
    get-network-list &>/dev/null
    [[ $? -eq 0 ]] && {
        echo "found."
        readonly args="--defaults"
    } || echo "done."

    echo "Creating hardware profile '${burst_hwprofile}'... "

    # Check if we can use 'execd' hardware profile as a source for the copy
    get-hardware-profile --name execd &>/dev/null
    [[ $? -eq 0 ]] && {
        # Check if requested resource adapter is enabled on hardware profile
        is_resadapter_enabled execd ${resadapter}
        [[ $? -eq 0 ]] && {
            echo "  - Copying existing hardware profile 'execd'... "
            copy-hardware-profile --src execd --dst ${burst_hwprofile}
            [[ $? -eq 0 ]] || {
                echo "failed."

                echo
                echo "Error copying hardware profile 'execd' to '${burst_hwprofile}'" >&2

                exit 1
            }
        } || {
            echo -n "  - Creating hardware profile from template"

            create-hardware-profile --name ${burst_hwprofile} ${args}

            echo "done."

            echo -n "  - Updating hardware profile configuration"
            update-hardware-profile --name ${burst_hwprofile} \
                --location remote --resource-adapter ${resadapter}
            echo "done."

            echo "  - WARNING: hardware profile ${burst_hwprofile} may need further configuration"
        }
    } || {
        echo "  - Creating new hardware profile \"${burst_hwprofile}\""

        create-hardware-profile --name ${burst_hwprofile}
        [[ $? -eq 0 ]] || {
            echo "Error creating hardware profile [${burst_hwprofile}]" >&2
            exit 1
        }

        update-hardware-profile --name ${burst_hwprofile} \
            --location remote --resource-adapter ${resadapter} --cost 100
    }

    echo "done."
}

# Map profiles
get-usable-hardware-profiles --software-profile ${burst_swprofile} | \
    tail -n +2 | grep -qx ${burst_hwprofile}
[[ $? -eq 0 ]] || {
    set-profile-mapping --software-profile ${burst_swprofile} \
        --hardware-profile ${burst_hwprofile}
}

# Create burst queue
echo -n "Checking for Grid Engine queue \"${uge_burst_queue}\"... "

qconf -sql | grep -qx ${uge_burst_queue}
[[ $? -eq 0 ]] && {
    echo "found."
} || {
    echo "not found."

    echo -n "  - Creating queue \"${uge_burst_queue}\"... "

    EDITOR=true qconf -aq ${uge_burst_queue} &>/dev/null
    [[ $? -eq 0 ]] || {
        echo "failed."
        exit 1
    }

    echo "done."
}


[[ ${slots_per_host} -eq 0 ]] && {
    echo -n "How many slots per (burst) host [1] (0 to exit)? "
    read response

    if [[ -z ${response} ]]; then
        slots_per_host=1
    else
        if $(test ${response} -gt 0 2>/dev/null); then
            slots_per_host=${response}
        fi
    fi

    [[ ${slots_per_host} -gt 0 ]] || {
        echo "Aborted by user!" >&2
        exit 1
    }
}

# Create hostgroup
echo -n "Checking for Grid Engine hostgroup \"${uge_burst_hostgroup}\"... "

qconf -shgrpl | grep -qx ${uge_burst_hostgroup}
[[ $? -eq 0 ]] && {
    echo "found."
} || {
    echo "not found."

    echo -n "  - Creating Grid Engine hostgroup \"${uge_burst_hostgroup}\"... "
    EDITOR=true qconf -ahgrp ${uge_burst_hostgroup} &>/dev/null
    [[ $? -eq 0 ]] || {
        echo "failed."
        exit 1
    }
    echo "done."
}

echo -n "Updating Grid Engine configuration..."

# Add burst hostgroup to burst queue
qconf -mattr queue hostlist ${uge_burst_hostgroup} ${uge_burst_queue} &>/dev/null
[[ $? -eq 0 ]] || {
    :
}

qconf -mattr queue slots "${slots_per_host},[$(hostname -s)=0]" ${uge_burst_queue} &>/dev/null
[[ $? -eq 0 ]] || {
    :
}

# Add qmaster host to burst hostgroup
qconf -aattr hostgroup hostlist $(hostname -s) ${uge_burst_hostgroup} &>/dev/null
[[ $? -eq 0 ]] || {
    :
}

echo "done."

# Run configuration file generator
force="--force"

python generate.py \
    --software-profile ${burst_swprofile} \
    --hardware-profile ${burst_hwprofile} \
    --slots-per-host ${slots_per_host} \
    --burst-queue ${uge_burst_queue} \
    ${force}

chmod +x ${rules_dir}/{activateNodes.sh,idleNodes.sh}

echo -n "Installing helper scripts... "
for i in get-resource-info get-idle-node.ec2 get-idle-node; do
    cp $i ${rules_dir}
done
echo "done."

echo -n "Installing 'get-idle-node' helper... "
idle_script="get-idle-node"

( cd ${rules_dir}; ln -sf ${idle_script} get-idle-node)

echo "done."

if [[ -z ${enable} ]] || [[ ${enable} == 1 ]]; then
    echo "Installing cloud bursting rules..."

    for rule_file in basic_burst.xml basic_unburst.xml post_basic_resource.xml; do
        add-rule --desc-file ${rules_dir}/${rule_file} &>/dev/null
    done

    echo -n "Synchronizing cluster... "
    /opt/puppetlabs/bin/puppet agent --onetime --no-daemonize
    echo "done."
else
   echo "Skipping enabling cloud bursting."
fi

echo "Installation complete. Cloud bursting is now enabled."

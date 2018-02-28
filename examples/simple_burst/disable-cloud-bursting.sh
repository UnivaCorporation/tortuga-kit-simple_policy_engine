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

[[ -n ${TORTUGA_ROOT} ]] || {
    echo "Error: Tortuga environment must be sourced." >&2
    exit 1
}

readonly curdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

. ${curdir}/settings.sh

echo -n "This script will remove existing \"cloud bursting\" configuration. Do you wish to proceed [N/y]? "

read response

[[ -z ${response} ]] || $(echo ${response} | grep -qv "^[Yy]") && {
    echo "Aborted by user." >&2
    exit 1
}

echo -n "Removing rules... "
for rule_name in ${rules[@]}; do delete-rule --app-name ${rule_app_name} --rule-name ${rule_name} &>/dev/null; done
echo "done."

echo -n "Removing Grid Engine queue and hostgroup... "
qconf -dattr queue hostlist ${uge_burst_hostgroup} ${uge_burst_queue} &>/dev/null
qconf -dhgrp ${uge_burst_hostgroup} &>/dev/null
echo "done."

echo -n "Remove qmaster host from burst queue..."
qconf -de $(hostname -s) &>/dev/null
echo "done."

echo -n "Removing software profile/hostgroup mapping... "
rm -f $SGE_CELL/$SGE_ROOT/config.${burst_swprofile}
echo "done."

echo -n "Removing software profile from UGE cluster... "
uge-cluster update ${cluster_name} --delete-execd-swprofile ${burst_swprofile} &>/dev/null
echo "done."

# Remove /opt/tortuga/rules directory
[[ -d ${rules_dir} ]] && {
    readonly dstdir="${rules_dir}.$(date +%s)"

    echo -n "Moving directory ${rules_dir} to ${dstdir}... "
    
    [[ ! -d ${dstdir} ]] && {
        mv ${rules_dir} ${dstdir}

        echo "done."
    } || {
        echo "failed."
        echo "Error: backup directory ${dstdir} already exists. Please remove manually" >&2
        exit 1
    }
}

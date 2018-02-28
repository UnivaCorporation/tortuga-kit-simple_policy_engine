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

burst_swprofile="execd-burst"
burst_hwprofile="execd-burst"
uge_burst_queue="burst.q"
uge_burst_hostgroup="@bursthosts"
rules_dir="${TORTUGA_ROOT}/rules"
rule_app_name="simple_burst"
rules=(burstPoller basicUnburst basicBurst)
cluster_name=default

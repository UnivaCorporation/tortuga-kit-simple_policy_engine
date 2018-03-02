## Simple Policy Engine Kit

### Overview

The Simple Policy Engine provides automation and logic for node management and
operations within Tortuga. This includes adding and/or removing compute
resources to a Tortuga and/or Grid Engine cluster.

### Installing the Simple Policy Engine Kit

Install the Simple Policy Engine Kit using the following command:

    install-kit kit-simple_policy_engine-6.3.1-0.tar.bz2

Installing the Simple Policy Engine Kit adds a single component, intended to be enabled on the installer node:

    enable-component -p simple_policy_engine-6.3.1-0 engine-6.3
    /opt/puppetlabs/bin/puppet agent --onetime --no-daemonize

The `engine` component of the Simple Policy Engine *must* be enabled in order to activate the Simple Policy Engine.

### Managing the Simple Policy Engine

The Simple Policy Engine is managed by several command-line interfaces:

* `get-rule-list` -- Display list of all rules installed in the Simple Policy Engine
* `get-rule` -- Get an XML dump of specified rule along with execution statistics
* `add-rule` -- Add a rule to the Simple Policy Engine
* `enable-rule` -- Enable a previously disabled rule
* `disable-rule` -- Disable a rule
* `post-application-data` -- Post application data to an installed rule. Usually called by a rule action, however it may be called manually from a shell prompt.
* `delete-rule` -- Remove a rule from the Simple Policy Engine

As with all Tortuga commands, man pages for Simple Policy Engine commands are
available via `man <command>`

### Policy Rule Types

All examples referenced below can be found under the `examples` subdirectory in the kit installation directory (`$TORTUGA_ROOT/kits/kit-simple_policy_engine-6.3.1-0/examples`)

### Cloud Bursting

One of the most useful features of the Simple Policy Engine is to automate
management of Grid Engine cluster compute resources. This is done by adding
and/or removing compute (`execd`) nodes automatically based on a
user-defined condition.

The Simple Policy Engine includes example scripts and rules for creating a
"zero node queue", which automatically increases/decreases Grid Engine
cluster resources based on queue backlog.

#### Installation/Setup

Install the Simple Policy Engine as follows and then proceed with the
automatic or manual configuration of bursting.

    install-kit --i-accept-the-eula kit-simple_policy_engine-6.3.1-0.tar.bz2
    enable-component -p engine
    /opt/puppetlabs/bin/puppet agent --onetime --no-daemonize

##### Automatic installation

The automatic installation assumes Univa Grid Engine is installed and a
resource adapter is installed and configured.

If using a resource adapter other than AWS, Google Compute Engine or Azure
please follow the manual installation procedure.

Change to Simple Policy Engine `simple_burst` example directory and run
`enable-cloud-bursting.sh`:

        cd $(find $TORTUGA_ROOT/kits -type d -name simple_burst)
        ./enable-cloud-bursting.sh

This script will create hardware and software profiles named `execd-burst`
as well as a Grid Engine queue `burst.q`.

Any Grid Engine jobs submitted to `burst.q` will be queued until 10 or more
pending jobs exist, at which time Tortuga will automatically launch EC2
compute instances to add compute resources to the Grid Engine cluster.

This does not prevent other (non-bursted) compute nodes from running pending
jobs. It is also possible to (manually) add non-burstable nodes (ie.
physical/on-premise nodes) to the queue `burst.q`.

##### Manual procedure

1. Create software profile `execd-burst`

        create-software-profile --name execd-burst --no-os-media-required

    Enable `execd` component:

        enable-component --software-profile execd-burst execd

1. Add `execd-burst` software profile to UGE cluster configuration

        uge-cluster update default --add-execd-swprofile execd-burst

1. Map to existing hardware profile

    In this example, the hardware profile `execd-burst` already exists.

        set-profile-mapping --software-profile execd-burst \
            --hardware-profile execd-burst

1. Create Grid Engine configuration

    Create hostgroup `@bursthosts`:

        EDITOR=true qconf -ahgrp @bursthosts

    Create queue `burst.q`:

        EDITOR=true qconf -aq burst.q

    Add `@bursthosts` to `burst.q` *hostlist*:

        qconf -mattr queue hostlist @bursthosts burst.q

    Add `qmaster` host to @bursthosts hostgroup and create "dummy" slots entry
    to keep queue `burst.q` "open". The `qmaster` host will not run jobs (unless explicitly configured to do so). It is used to keep the queue `burst.q` "open" despite not having any
    allocated compute hosts.

        qconf -aattr hostgroup hostlist $(hostname -s) @bursthosts
        qconf -mattr queue slots "[$(hostname -s)=0]" burst.q

1. Copy example scripts/rules to working directory

    It is *recommended* to copy the example rules to a "working" directory. This example uses the directory `$TORTUGA_ROOT/rules`.

        mkdir $TORTUGA_ROOT/rules
        SRCDIR=$(find $TORTUGA_ROOT/kits -type d -name simple_burst)
        cp -ar $SRCDIR/* $TORTUGA_ROOT/rules

    Adjust hardcoded paths appropriately:

        cd $TORTUGA_ROOT/rules
        sed -i -e "s|${SRCDIR}|$TORTUGA_ROOT/rules|g" *.xml *.sh

1. Ensure hosts in "execd-burst" software profile are automatically added to
   @bursthosts hostgroup

    Create the software profile configuration file:

        echo "@bursthosts" >$SGE_ROOT/$SGE_CELL/common/config.execd-burst

    Adjust `$SGE_ROOT/$SGE_CELL` to suit non-default UGE root directory.

1. Install idle node detection script

    Create a symlink to the simple idle node detection script

        ln -s get-idle-node.simple get-idle-node

    This Python script can be modified to suit needs. It is provided as an
    example only.

1. Install Simple Policy Engine rules

    The polling rule (found in XML template file `post_basic_resource.xml`)
    polls the queue `burst.q` every 5 minutes and creates a temporary reporting
    file, which is sent to the Simply Policy Engine for evaluation.

    **Note:** make modifications (ie. polling interval) prior to installing the
    polling rule. This may include changing the UGE cell directory.

        add-rule --desc-file basic_burst.xml
        add-rule --desc-file basic_unburst.xml
        add-rule --desc-file post_basic_resource.xml

    Use `get-rule-list` to display installed rules. Output should appear as follows:

        [root@tortuga rules]# get-rule-list
        simple_burst/burstPoller (type: poll, status: enabled)
        simple_burst/basicUnburst (type: receive, status: enabled)
        simple_burst/basicBurst (type: receive, status: enabled)

    The Simple Policy Engine rules are now active.

1. Submit jobs to the `burst.q` queue

        qsub -q burst.q /opt/uge-8.5.3/examples/jobs/sleeper.sh 100

    The Simple Policy Engine will now automatically add one compute node if 10
    (or more) jobs are pending at the next polling interval.

    Conversely, the Simple Policy Engine will automatically remove inactive
    (ie. nodes not currently running jobs) when less than 10 pending jobs exist in
    `burst.q`.

#### Advanced idle node detection

The included script `get-idle-node.simple` is used by the Simple Policy Engine
to detect when a compute node is idle. It is very simplistic and does not
factor in node "cost" (ie. the "cost" of cloud-based node instances vs.
on-premise physical nodes), nor instance run time.

Because cloud-based instances incur expense and are billed in intervals, it is
may be desirable to allow compute node(s) to run for the entire billing
interval. For example, on Amazon EC2, the billing interval is 1 hour (60
minutes). If the Simple Policy Engine were to terminate an instance only a few
minutes into the billing interval, compute resources will be removed despite
having been billed for the entire interval.

The script `get-idle-node.ec2` attempts to keep an EC2 instance running for the
entire billing period by not allowing termination until the 57th
(user-configurable) minute of the billable hour.

Move the script `get-idle-node` out of place and copy `get-idle-node.ec2` to
`get-idle-node` to use this advanced termination logic.

#### Adjusting the cloud bursting environment

##### Polling interval

Change the value of `pollPeriod` in the rule "simple_burst/burstPoller"
(defined in `post_basic_resource.xml`). Default value is 300 seconds.

It is also recommended to change the value of `POLLING_INTERVAL` in the
helper script `idleOneNode.sh`.

After changing the polling interval, apply the change as follows:

    delete-rule --app-name simple_burst --rule-name burstPoller
    add-rule --desc-file post_basic_resource.xml

##### Burst condition

The Simple Policy Engine rule "simple_burst/basicBurst" (as defined in the
rule XML file `basic_burst.xml`) contains the logic to determine how many
pending jobs must exist in `burst.q` before a burst condition is reached.

This file can be found in the Simple Policy Engine kit directory:

    find $TORTUGA_ROOT/kits -type d -name simple_burst

or if using the automatic installation procedure:

    $TORTUGA_ROOT/rules

Adjust the value of `triggerValue` in the condition `__neededNodes__`.

Default:

    ...
    <condition metricXPath="__neededNodes__" evaluationOperator=">" triggerValue="10">
        <description>Needed nodes must be greater than 10</description>
    </condition>
    ...

Adjusted to require only 5 pending jobs before bursting:

    ...
    <condition metricXPath="__neededNodes__" evaluationOperator=">" triggerValue="5">
      <description>Needed nodes must be greater than 5</description>
    </condition>
    ...

After making the change to the rule, it is necessary to delete the current rule and apply the updated rule:

    delete-rule --app-name simple_burst --rule-name basicBurst
    add-rule --desc-file basic_burst.xml

### Troubleshooting

The Simple Policy Engine verbosely logs to `/var/log/tortuga`.

\newpage



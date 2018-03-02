Simple Policy Engine
====================

Version 1.0 -- August 2017

Overview
--------

The Simple Policy Engine allows automation of actions based on user-defined
policies. These actions would be defined in a "ruleset".

A ruleset contains a "polling" rule and one or more "receive" rules. On each
polling interval, the polling rule generates XML formatted application data.
Application data is then "posted" to the Simple Policy Engine using the
UniCloud `post-application-data` CLI. 

\newpage

## Polling rules

Polling rules are defined as type `poll` (attribute `type` in
`applicationMonitor` element) and run on a configured interval (attribute
`pollPeriod`; value is in seconds). It is recommended that the polling interval
is not too short (frequent) to prevent thrashing and overall increased system
load caused by monitoring scripts.

```xml
<?xml version="1.0"?>
<rule applicationName="appname" name="rulename">
    <applicationMonitor type="poll" pollPeriod="90">
         <actionCommand>...</actionCommand>
    </applicationMonitor>
<rule>
```

The value of the element `actionCommand` is a command/script run by the Simple
Policy Engine. Typically, it would call a process that writes XML data to a
file, which is then ingested by the Simple Policy Engine using the UniCloud
command-line interface `post-application-data`.

```xml
...
   ...
      <actionCommand>generate-data && post-application-data ...</actionCommand>
   ...
...
```

The structure/format of the posted XML data is user-defined and entirely
arbitrary.

Polling rules do not run action commands themselves. They are solely
responsible for querying data from external sources and posting used by the
"receive" rules to perform actions.

The action command in the polling rule is responsible for reducing complex
application data, perhaps from many sources, into a simple XML document
containing only pertinent data.

For example, in the Simple Policy Engine cloud bursting example, the polling
rule action command queries the pending jobs in a specific Grid Engine and
reports that value back as hosts in demand. The key logic for reducing the
number of pending jobs to the number of Grid Engine slots requested to number
of nodes is performed by the script `get-resource-info`. See the UniCloud
Installation and Adminisration Guide for additional information about the
simple cloud burst example included with UniCloud.

\newpage

## Receive rules

Receive rules evaluate application data posted by a polling rule and execute an
action command if (*optional*) conditions are met.

Receive rules can be used to report events to third-party services and/or
monitoring tools based on application data reported by the polling rule.

### Extracting metrics from application data

Metrics are extracted from XML application data using [XML Path Lanaguage (XPath)](https://www.w3.org/TR/xpath/).

### Conditions

Conditions are *optional* and must evaluate to true in order for action command
to be executed. If the rule has no defined conditions, the action command will
ALWAYS be executed.

Assuming the following application data:

```xml
<?xml version="1.0"?>
<resourceData myattr="example">
    <sampleval>1234</sampleval>
</resourceData>
```

In the following receive rule, the value of the element "sampleval" is
extracted into a metric named `__myvalue__`.

```xml
<?xml version="1.0"?>
<rule applicationName="appname" name="rulename">
    <xPathVariable name="__myvalue__" xPath="number(resourceData[@myattr='example']/sampleval)"/>
    <applicationMonitor type="receive">
        <actionCommand>...</actionCommand>
    </applicationMonitor>
    <condition metricXPath="__myvalue__" evaluationOperator=">" triggerValue="10">
        <description>myvalue must be greater than 10</description>
    </condition>
    <description>Add compute node</description>
</rule>
```

In this example, the action command would only be executed if the value of
"__myvalue__" is greater than 10.

The metric `__myvalue__` can be passed as an argument to the action command or
simply used in the condition to determine when to execute the action command.

Refer to XPath documentation for methods by which XML application data can be
parsed and/or manipulated.

#### Valid operators

Conditions use any of the following operators:

* = (equal to)
* != (not equal to)
* &gt; (greater than)
* &gt;= (greater than or equal to)
* &lt;= (less than or equal to)
* &lt; (less than)

If multiple conditions are defined, they are "ORed" together. This means that
any one condition that evaluates to "True" will cause the action command to be
executed.

Operators containing greater-than and less-than symbols defined in the
"evaluationOperator" attribute of the "condition" element, must be properly
escaped.

### Action command

The action command within the receive rule is run within the UniCloud
environment with no other environments set (ie. Grid Engine). It is necessary
to set any environments within the shell script. This may require using a
wrapper script if calling an executable.

Only one action command per rule can be defined.  For receive rules that should
perform multiple actions per polling interval, it is necessary to define
separate rules for each action. The benefit of this is it is possible to
enable/disable individual actions within a ruleset.

\newpage

Simple Policy Engine Actions
----------------------------

### Import (add) rules

    add-rule --desc-file <filename>

where `<filename>` is a file containing a properly formatted XML rule definition.

### List all installed rules

    get-rule-list

### Display rule

Display the XML rule definition:

    get-rule --app-name APPNAME --rule-name RULENAME

### Enable/disable rules

Rules are automatically enabled when added using `add-rule`, unless the rule
definition explicitly disables it using the "status" element.

    enable-rule --app-name APPNAME --rule-name RULENAME

Rules can be (temporarily) disabled using `disable-rule`:

    disable-rule --app-name APPNAME --rule-name RULENAME

Rule state (enabled or disabled) is displayed in the output of `get-rule-list`
as well as `get-rule`.

### Delete rule

    delete-rule --app-name APPNAME --rule-name RULENAME

### (Force) execution of receive rule

Sample (XML formatted) application data, a receive rule can be manually
executed:

    execute-rule --app-name APPNAME --rule-name RULENAME --data-file FILENAME

\newpage

Simple Rule Example
-------------------

In this simple example, application data is generated by the script
`/tmp/generate.sh` and written to a temporary file `/tmp/sample-data.xml`. The
application data is posted to the Simple Policy Engine. The receive rule runs
the script `/tmp/action-command.sh` with the argument being a metric extracted
from the application data.

Files:

- `test1-poll.xml`
- `test1-action.xml`
- `/tmp/generate.sh`
- `/tmp/action-command.sh`

Polling rule is defined in file `test1-poll.xml` as follows:

```xml
<?xml version="1.0"?>
<rule applicationName="test1" name="test1-poll">
    <applicationMonitor type="poll" pollPeriod="60">
        <actionCommand>/tmp/generate.sh &amp;&amp; post-application-data --app-name=test1 --data-file=/tmp/sample-data.xml</actionCommand>
        <description>Sample data monitor</description>
    </applicationMonitor>
    <description>Post sample data to Simple Policy Engine</description>
</rule>
```

The polling rule calls the script `/tmp/generate.sh` that creates a basic XML
document. Create `/tmp/generate.sh` with the following contents:

```shell
#!/bin/bash

cat >/tmp/sample-data.xml <<ENDL
<?xml version="1.0"?>
<sample_data>
    <value>7</value>
</sample_data>
ENDL
```
Don't forget to set `/tmp/generate.sh` executable:

    chmod +x /tmp/generate.sh

Next, create a rule in file named `test1-action.xml`.

```xml
<?xml version="1.0"?>
<rule applicationName="test1" name="test1-action">
    <xPathVariable name="__value__" xPath="string(sample_data/value)"/>
    <applicationMonitor type="receive">
        <actionCommand>/tmp/action-command.sh __value__</actionCommand>
    </applicationMonitor>
    <description>Call action with value as argument </description>
</rule>
```

The receive rule action command executes the script `/tmp/action-command.sh`.
Create the script `/tmp/action-command.sh` as follows:

```shell
#!/bin/bash

logger -t rule-example the value is $1
```

Do not forget to set script as executable:

    chmod +x /tmp/action-command.sh

As can be seen in the "xPathVariable" element, the XPath Expression is
"string(sample_data/value)" matching the format of the XML document. In words,
the top-level element is "sample_data" containing a single element "value". The
value of "value" is then stored in the metric "__value__". This metric is used
as an argument to the action command.

#### Adding test rules

    add-rule --desc-file test1-poll.xml
    add-rule --desc-file test1-action.xml

Monitor `/var/log/unicloud` to observe the rule being added to the Simple
Policy Engine and being initiated to run on the configured interval.

Installed rules can be listed using `get-rule-list`.

#### Testing

The receive rule can be tested by creating sample input data and running the
receive rule using `execute-rule`:

    execute-rule --app-name test1 --rule-name test1-action --data-file sample.xml

Use sample rule data (contained in `sample.xml`) as follows:

```xml
<?xml version="1.0"?>
<sample_data>
    <value>12</value>
</sample_data>

```

Observe the result of the rule exection in `/var/log/unicloud`.

\newpage

Testing &amp; Debugging
-----------------------

* Use `xmllint` (contained in `libxml2` package on Red Hat Enterprise
  Linux/CentOS) to validate XML rules
* Set a short(er) polling interval for testing
* Use `disable-rule` to disable action rules while observing observe poller
  behaviour
* `execute-rule` with properly formatted data to test 'receive' rules

### Analyzing Simple Policy Engine Logs

Using the log output from the Simple Example above.


Log entries extracted from `/var/log/unicloud`. Log level set to DEBUG.

#### Polling rule

Application name: "test1", Rule name: "test1-poll"

```
1. YYYY-MM-DD XX:XX:XX DEBUG XXXX [RuleEngine] Timer execution started for [test1/test1-poll]
2. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Query command: None
3. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Action command: /tmp/generate.sh && post-application-data --app-name=test1 --data-file=/tmp/sample-data.xml
4. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] About to invoke: [/tmp/generate.sh && post-application-data --app-name=test1 --data-file=/tmp/sample-data.xml]
5. YYYY-MM-DD HH:MM:SS DEBUG XXXX [tortuga.web_service.controllers.applicationMonitorController] Received data for: test1
6. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Received data for [test1]
7. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Starting processing timer
8. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Done with command: [/tmp/generate.sh && post-application-data --app-name=test1 --data-file=/tmp/sample-data.xml]
9. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Scheduling new timer for rule [test1/test1-poll] in [60.0] seconds
```

* Line #1: polling rule is being executed
* Line #2: always indicates "None"
* Line #3: shows full command-line of action command (as defined in the rule)
* Line #4: log message indicates action command is about to be invoked
* Line #5: response from UniCloud webservice inidicating that application post data has been received
* Line #6: confirmation from Simple Policy Engine of post application data
* Line #7: starts internal timer to track processing time
* Line #8: poll has completed, scheduling the next poll

#### Receive (action) rule

Application name: "test1", Rule name: "test1-action"

```
Line #9:  YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Processing data using rule [test1/test1-action]
Line #10: YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Action command: [/tmp/action-command.sh __value__]
Line #11: YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] xPath variable list: [{'xPath': 'string(sample_data/value)', 'name': u'__value__'}]
Line #12: YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Evaluating xPath variable __value__: string(sample_data/value)
Line #13: YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] XPath variable replacement dictionary: {u'__value__': '7'}
Line #14: YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Returning trigger action flag: [True]
Line #15: YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] About to invoke: [/tmp/action-command.sh 7]
Line #16: YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Done with command: [/tmp/action-command.sh 7]
```

* Line #9: Indication of receive rule being executed
* Line #10: Shows action command for specified rule
* Line #11: List of XPath variables: "xPath" is the XML Path, "name" is name of metric
* Line #12: Shows evaluation of XPath variables
* Line #13: shows substitution of XPath variable
* Line #14: because no conditions are defined, action will always be triggered
* Line #15: log entry prior to invoking action command
* Line #16: action command has been invoked

#### Receive (action) rule with condition

In the following log file snippet, the receive (action) rule was modified to
include a condition. This condition prevents the action command from running.

```
17. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Processing data using rule [test1/test1-action2]
18. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Action command: [/tmp/action-command.sh __value__]
19. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] xPath variable list: [{'xPath': 'string(sample_data/value)', 'name': u'__value__'}]
20. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Evaluating xPath variable __value__: string(sample_data/value)
21. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] XPath variable replacement dictionary: {u'__value__': '7'}
22. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Evaluating: [{'metricXPath': u'__value__', 'triggerValue': u'10', 'evaluationOperator': '>', 'description': u'value must be greater than 10'}]
23. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Got metric: [7]
24. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Evaluating as numbers: 7 > 10
25. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Evaluation result: [False]
26. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Returning trigger action flag: [False]
27. YYYY-MM-DD HH:MM:SS DEBUG XXXX [RuleEngine] Will skip action: [/tmp/action-command.sh __value__]
```

* Line 17: processing rule
* Line 18: action command is same as other (non-condition) receive rule
* Line 19: same XPath variables
* Line 20: shows evaluation of XPath variables
* Line 21: shows substitution of XPath variable
* Line 22: evaluating condition
* Line 23: displaying metric being used for evaluation
* Line 24: 7 is not greated than 10
* Line 25: ... evaluation result is False
* Line 26: ... set action trigger flag
* Line 27: action command will not be triggered

If the evaluation operator was set to "less-than" (instead of "greater-than"),
the trigger condition would be "True" and the action command would be executed.

Frequently Asked Questions
--------------------------

Q: How do I adjust the polling interval?  
A: Edit the rule definition, delete existing rule, and add updated rule.

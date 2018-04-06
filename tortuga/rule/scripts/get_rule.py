#!/usr/bin/env python

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

from tortuga.rule.ruleCli import RuleCli


class GetRuleCli(RuleCli):
    """
    Get rule command line interface.

    """
    def __init__(self):
        super().__init__()
        self.addOption('--app-name', dest='applicationName',
                       help=_('Application name'))
        self.addOption('--rule-name', dest='ruleName', help=_('Rule name'))

    def runCommand(self):
        self.parseArgs(_("""
    get-rule --app-name=APPLICATIONNAME --rule-name=RULENAME

Description:
    The get-rule tool returns details of a single rule  that  is  in  the
    Tortuga Rule Engine.
"""))
        application_name, rule_name = self.getApplicationNameAndRuleName()
        rule = self.get_rule_api().getRule(application_name, rule_name)
        print((rule.getXmlRep()))


def main():
    GetRuleCli().run()

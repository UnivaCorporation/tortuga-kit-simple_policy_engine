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

import os

from tortuga.exceptions.fileNotFound import FileNotFound
from tortuga.exceptions.invalidCliRequest import InvalidCliRequest
from tortuga.rule.ruleCli import RuleCli


class ExecuteRuleCli(RuleCli):
    """
    Execute rule command line interface.

    """
    def __init__(self):
        RuleCli.__init__(self)
        self.addOption('--app-name', dest='applicationName',
                       help=_('Application name'))
        self.addOption('--rule-name', dest='ruleName', help=_('Rule name'))
        self.addOption('--data-file', dest='dataFile',
                       help=_('Application data file'))

    def runCommand(self):
        self.parseArgs(_("""
    execute-rule --app-name=APPNAME --rule-name=RULENAME [--data-file=DATAFILE]

Description:
    The execute-rule tool forces execution of a given rule in the Tortuga Rule
    Engine.
"""))
        application_name, rule_name = self.getApplicationNameAndRuleName()
        data_file = self.getOptions().dataFile
        application_data = ''
        if data_file:
            if not os.path.exists(data_file):
                raise FileNotFound(
                    _('Invalid application data file: {}').format(data_file)
                )
            else:
                f = open(data_file, 'r')
                application_data = f.read()
                f.close()
                if not len(application_data):
                    raise InvalidCliRequest(_('Empty application data file.'))

        self.get_rule_api().executeRule(application_name, rule_name,
                                        application_data)
        print(_('Executed rule {}/{}').format(application_name, rule_name))


def main():
    ExecuteRuleCli().run()

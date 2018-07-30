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

import os.path

from tortuga.exceptions.fileNotFound import FileNotFound
from tortuga.exceptions.invalidCliRequest import InvalidCliRequest
from ..ruleCli import RuleCli


class PostApplicationDataCli(RuleCli):
    """
    Post app. data command line interface.
    """
    def __init__(self):
        super().__init__()
        self.addOption('--app-name', dest='applicationName',
                       help=_('Application name'))
        self.addOption('--data-file', dest='dataFile',
                       help=_('Application data file'))

    def runCommand(self):
        self.parseArgs(_("""
    post-application-data --app-name=APPLICATIONNAME --data-file=DATAFILE

Description:
    The  post-application-data tool posts an XML file to the Tortuga Rule
    Engine web service as input for configured rules.
"""))
        application_name = self.getArgs().applicationName

        if not application_name:
            raise InvalidCliRequest(_('Missing application name.'))
        data_file = self.getArgs().dataFile

        if not data_file:
            raise InvalidCliRequest(_('Missing application data file.'))

        if not os.path.exists(data_file):
            raise FileNotFound(_('Invalid application data file: %s.') % data_file)

        f = open(data_file, 'r')
        application_data = f.read()
        f.close()

        if not len(application_data):
            raise InvalidCliRequest(_('Empty application data file.'))

        self.get_rule_api().postApplicationData(application_name,
                                                application_data)


def main():
    PostApplicationDataCli().run()

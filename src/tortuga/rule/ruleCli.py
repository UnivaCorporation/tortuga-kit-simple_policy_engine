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

from tortuga.cli.tortugaCli import TortugaCli
from tortuga.exceptions.invalidCliRequest import InvalidCliRequest
from .wsapi.ruleWsApi import RuleWsApi


class RuleCli(TortugaCli):
    """
    Base rule command line interface class.

    """
    def __init__(self):
        super().__init__()
        self._rule_api = None

    def get_rule_api(self):
        if not self._rule_api:
            self._rule_api = RuleWsApi(username=self.getUsername(),
                                       password=self.getPassword(),
                                       baseurl=self.getUrl())
        return self._rule_api

    def getApplicationNameAndRuleName(self):
        application_name = self._options.applicationName
        rule_name = self._options.ruleName

        if not application_name:
            raise InvalidCliRequest(_('Missing application name.'))

        if not rule_name:
            raise InvalidCliRequest(_('Missing rule name.'))

        return application_name, rule_name

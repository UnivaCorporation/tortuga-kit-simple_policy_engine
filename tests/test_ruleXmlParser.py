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

#!/usr/bin/env python

import unittest
import pprint
from tortuga.rule.ruleXmlParser import RuleXmlParser
from tortuga.objects.ruleCondition import RuleCondition
from tortuga.exceptions.invalidXml import InvalidXml


class TestRuleXmlParser(unittest.TestCase):
    def setUp(self):
        self.filename = '../examples/scenario2/basic_unburst.xml'

        self.ruleXmlParser = RuleXmlParser()

    def teardown(self):
        self.ruleXmlParser = None

    def test_ruleXmlParser_parse(self):
        print('Attempting to XML file %s' % (self.filename))

        rule = self.ruleXmlParser.parse(self.filename)

        conditions = rule.getConditionList()

        pprint.pprint(conditions)

        self.assertTrue(conditions)

        pprint.pprint(type(conditions[0]))

        self.assertTrue(isinstance(conditions[0], RuleCondition))

    def test_ruleXmlParser_parseString(self):
        with open(self.filename) as fp:
            xmlbuf = fp.read()

        rule = self.ruleXmlParser.parseString(xmlbuf)

        pprint.pprint(rule)

        self.assertTrue(rule)

    def test_ruleXmlParser_parseString_negative1(self):
        """Attempt to parse empty string"""

        self.assertRaises(InvalidXml, self.ruleXmlParser.parseString, '')

    def test_ruleXmlParser_parseString_negative2(self):
        """Attempt to parse rule from empty XML document"""

        self.assertRaises(
            InvalidXml,
            self.ruleXmlParser.parseString,
            '<?xml version=\'1.0\'/>')


if __name__ == '__main__':
    unittest.main()

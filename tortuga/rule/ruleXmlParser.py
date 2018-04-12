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

import logging
import os.path
from xml.dom import minidom

from jinja2 import Template

from tortuga.config.configManager import ConfigManager
from tortuga.exceptions.fileNotFound import FileNotFound
from tortuga.exceptions.invalidXml import InvalidXml
from tortuga.exceptions.tortugaException import TortugaException
from tortuga.kit.kitApi import KitApi
from tortuga.kit.utils import format_kit_descriptor
from tortuga.objects.xPathVariable import XPathVariable
from tortuga.utility import xmlParserUtility
from .objects.applicationMonitor import ApplicationMonitor
from .objects.rule import Rule
from .objects.ruleCondition import RuleCondition
from .ruleXmlParserInterface import RuleXmlParserInterface


class RuleXmlParser(RuleXmlParserInterface):
    def __init__(self):
        self._logger = logging.getLogger(
            'tortuga.rule.%s' % self.__class__.__name__)
        self._logger.addHandler(logging.NullHandler())

    def parse(self, ruleXmlFile):
        """
        Parse rule XML file and return rule object.

        Raises:
            InvalidXml
            FileNotFound
        """

        if not os.path.exists(ruleXmlFile):
            raise FileNotFound('File %s is not found' % (ruleXmlFile))

        try:
            self._logger.debug('Parsing: %s' % (ruleXmlFile))

            xmlDoc = minidom.parse(ruleXmlFile)

            return self.__buildRule(xmlDoc)
        except TortugaException as ex:
            raise
        except Exception as ex:
            raise InvalidXml(
                'Could not parse XML file %s (%s)' % (ruleXmlFile, ex))

    def parseString(self, ruleXmlString):
        """
        Parse rule XML string and return rule object.

        Raises:
            InvalidXml
        """

        try:
            xmlDoc = minidom.parseString(ruleXmlString)

            return self.__buildRule(xmlDoc)
        except TortugaException as ex:
            raise
        except Exception as ex:
            raise InvalidXml('Could not parse XML string (%s)' % (ex))

    def __buildRule(self, xmlDoc):
        """ Parse rule XML return rule object. """

        rule = Rule()

        try:
            rootNode = xmlParserUtility.getRequiredElement(xmlDoc, 'rule')

            name = xmlParserUtility.getRequiredAttribute(rootNode, 'name')

            rule.setName(name)

            applicationName = xmlParserUtility.getRequiredAttribute(
                rootNode, 'applicationName')

            rule.setApplicationName(applicationName)

            self._logger.debug('Building rule [%s]' % (rule))

            desc = xmlParserUtility.getOptionalTextElement(
                rootNode, 'description')

            rule.setDescription(desc)

            status = xmlParserUtility.getOptionalTextElement(
                rootNode, 'status')

            if status:
                rule.setStatus(status)

            # Build application monitor.
            appMonitor = ApplicationMonitor()

            appMonitorNode = xmlParserUtility.getRequiredElement(
                rootNode, 'applicationMonitor')

            monitorType = appMonitorNode.getAttribute('type')

            appMonitor.setType(monitorType)

            if appMonitorNode.hasAttribute('pollPeriod'):
                pollPeriod = appMonitorNode.getAttribute('pollPeriod')
                appMonitor.setPollPeriod(pollPeriod)

            if appMonitorNode.hasAttribute('maxActionInvocations'):
                maxActionInvocations = xmlParserUtility.getOptionalAttribute(
                    appMonitorNode, 'maxActionInvocations')

                appMonitor.setMaxActionInvocations(maxActionInvocations)

            desc = xmlParserUtility.getOptionalTextElement(
                appMonitorNode, 'description')

            appMonitor.setDescription(desc)

            queryCommand = xmlParserUtility.getOptionalTextElement(
                appMonitorNode, 'queryCommand')

            if queryCommand != '':
                appMonitor.setQueryCommand(queryCommand)

            analyzeCommand = xmlParserUtility.getOptionalTextElement(
                appMonitorNode, 'analyzeCommand')

            if analyzeCommand != '':
                appMonitor.setAnalyzeCommand(analyzeCommand)

            actionCommand = xmlParserUtility.getRequiredTextElement(
                appMonitorNode, 'actionCommand')

            appMonitor.setActionCommand(expandVars(actionCommand))

            rule.setApplicationMonitor(appMonitor)

            # XPath variables that rule utilizes.
            xPathVariableNodeList = xmlParserUtility.getOptionalElementList(
                rootNode, 'xPathVariable')

            for vNode in xPathVariableNodeList:
                v = XPathVariable()

                v.setName(xmlParserUtility.getRequiredAttribute(vNode, 'name'))

                v.setXPath(
                    xmlParserUtility.getRequiredAttribute(vNode, 'xPath'))

                rule.addXPathVariable(v)

            conditionNodeList = xmlParserUtility.getOptionalElementList(
                rootNode, 'condition')

            for cNode in conditionNodeList:
                cond = RuleCondition()

                cond.setMetricXPath(
                    xmlParserUtility.getRequiredAttribute(
                        cNode, 'metricXPath'))

                cond.setEvaluationOperator(
                    xmlParserUtility.getRequiredAttribute(
                        cNode, 'evaluationOperator'))

                cond.setTriggerValue(
                    xmlParserUtility.getRequiredAttribute(
                        cNode, 'triggerValue'))

                cond.setDescription(
                    xmlParserUtility.getOptionalTextElement(
                        cNode, 'description'))

                rule.addCondition(cond)
        except TortugaException as ex:
            raise
        except Exception as ex:
            raise InvalidXml(exception=ex)
        return rule


def expandVars(actionCommand):
    kit = [kit for kit in KitApi().getKitList()
           if kit.getName() == 'simple_policy_engine']

    if not kit:
        # This cannot happen but handle it anyway...
        return actionCommand

    ddict = {
        'spe_kitdir': os.path.join(
            ConfigManager().getKitDir(),
            'kit-{0}'.format(
                format_kit_descriptor(kit[0].getName(),
                                      kit[0].getVersion(),
                                      kit[0].getIteration()))),
    }

    return Template(actionCommand).render(ddict)

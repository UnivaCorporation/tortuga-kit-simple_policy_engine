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
import threading
# TODO: fix this... I don't know how to reproduce the scenario that
# calls the libxml2 parsing code.
try:
    import libxml2
except ImportError:
    pass
import copy
import time
import queue
import logging

from tortuga.rule.ruleEngineInterface import RuleEngineInterface
from tortuga.exceptions.ruleAlreadyExists import RuleAlreadyExists
from tortuga.exceptions.ruleNotFound import RuleNotFound
from tortuga.exceptions.ruleAlreadyEnabled import RuleAlreadyEnabled
from tortuga.exceptions.ruleAlreadyDisabled import RuleAlreadyDisabled
from tortuga.exceptions.ruleDisabled import RuleDisabled
from tortuga.exceptions.tortugaException import TortugaException
from tortuga.config.configManager import ConfigManager
from tortuga.os_utility import tortugaSubprocess
from tortuga.os_utility import osUtility
from tortuga.objects.tortugaObject import TortugaObjectList
from tortuga.rule.ruleXmlParser import RuleXmlParser


class RuleEngine(RuleEngineInterface):
    def __init__(self, minTriggerInterval=60):
        self._cm = ConfigManager()
        self._lock = threading.RLock()
        self._processingLock = threading.RLock()
        self._minTriggerInterval = minTriggerInterval
        self._ruleDict = {}
        self._disabledRuleDict = {}  # Used for rules in the disabled state
        self._eventRuleDict = {}  # used for "event" type monitoring
        self._pollTimerDict = {}  # used for "poll" monitoring
        self._receiveRuleDict = {}  # used for "receive" type monitoring
        self._receiveQ = queue.Queue(0)  # infinite size FIFO queue
        self._rulesDir = self._cm.getRulesDir()
        self._logger = logging.getLogger(
            'tortuga.rule.%s' % self.__class__.__name__)
        self._logger.addHandler(logging.NullHandler())
        self.__initRules()

        # the following are used for "receive" type monitoring
        self._processingTimer = None
        self._processingTimerRunning = False

    def __getRuleDirName(self, applicationName):
        return '%s/%s' % (self._rulesDir, applicationName)

    def __getRuleFileName(self, applicationName, ruleName):
        return '%s/%s.xml' % (self.__getRuleDirName(applicationName), ruleName)

    def __readRuleFile(self, applicationName, ruleName):
        with open(self.__getRuleFileName(applicationName,
                                         ruleName)) as ruleFile:
            content = ruleFile.read()

        return content

    def __writeRuleFile(self, rule):
        ruleDir = self.__getRuleDirName(rule.getApplicationName())

        if not os.path.exists(ruleDir):
            os.makedirs(ruleDir)

        with open(self.__getRuleFileName(rule.getApplicationName(),
                                         rule.getName()), 'w') as ruleFile:
            ruleFile.write('%s\n' % (rule.getXmlRep()))

    def __getRuleId(self, applicationName, ruleName):
            # pylint: disable=no-self-use
        return '%s/%s' % (applicationName, ruleName)

    def __checkRuleExists(self, ruleId):
        if ruleId not in self._ruleDict:
            raise RuleNotFound('Rule [%s] not found.' % ruleId)

    def __checkRuleDoesNotExist(self, ruleId):
        """
        Raises:
            RuleAlreadyExists
        """

        if ruleId in self._ruleDict:
            raise RuleAlreadyExists('Rule [%s] already exists.' % ruleId)

    def __checkRuleEnabled(self, ruleId):
        """
        Raises:
            RuleNotFound
            RuleDisabled
        """

        self.__checkRuleExists(ruleId)

        if ruleId in self._disabledRuleDict:
            raise RuleDisabled('Rule [%s] is disabled.' % ruleId)

    def __initRules(self):
        """ Initialize all known rules. """

        self._logger.debug(
            '[%s] Initializing known rules' % (self.__class__.__name__))

        fileList = osUtility.findFiles(self._rulesDir)

        parser = RuleXmlParser()

        for f in fileList:
            try:
                rule = parser.parse(f)
                ruleId = self.__getRuleId(
                    rule.getApplicationName(), rule.getName())

                self._logger.debug(
                    '[%s] Found rule [%s]' % (self.__class__.__name__, ruleId))

                self.addRule(rule)
            except Exception as ex:
                self._logger.error(
                    '[%s] Invalid rule file [%s] (Error: %s)' % (
                        self.__class__.__name__, f, ex))

    def __evaluateNumbers(self, metric, operator, triggerValue): \
            # pylint: disable=exec-used
        trigger = None

        try:
            triggerString = '%s %s %s' % (metric, operator, triggerValue)

            self._logger.debug(
                '[%s] Evaluating as numbers: %s' % (
                    self.__class__.__name__, triggerString))

            exec('trigger = %s' % triggerString)

            return trigger
        except Exception as ex:
            self._logger.debug(
                '[%s] Could not evaluate as numbers: %s' % (
                    self.__class__.__name__, ex))

        return None

    def __evaluateStrings(self, metric, operator, triggerValue): \
            # pylint: disable=exec-used
        trigger = None

        try:
            triggerString = '"%s" %s "%s"' % (metric, operator, triggerValue)

            self._logger.debug(
                '[%s] Evaluating as strings: %s' % (
                    self.__class__.__name__, triggerString))

            exec('trigger = %s' % triggerString)

            return trigger
        except Exception as ex:
            self._logger.debug(
                '[%s] Could not evaluate as strings: %s' % (
                    self.__class__.__name__, ex))

        return None

    def __parseMonitorData(self, monitorData=''):
        if not monitorData:
            return None

        self._logger.debug(
            '[%s] Parsing data: %s' % (self.__class__.__name__, monitorData))

        try:
            return libxml2.parseDoc(monitorData)
        except Exception as ex:
            self._logger.error(
                '[%s] Could not parse data: %s' % (self.__class__.__name__, ex))

        return None

    def __evaluateConditions(self, rule, monitorXmlDoc=None,
                             xPathReplacementDict=None):
        # Return True if all rule conditions were satisfied.
        triggerAction = False

        try:
            if monitorXmlDoc is not None:
                triggerAction = True
                for condition in rule.getConditionList():
                    self._logger.debug(
                        '[%s] Evaluating: [%s]' % (
                            self.__class__.__name__, condition))

                    metricXPath = condition.getMetricXPath()

                    metric = self.__replaceXPathVariables(
                        metricXPath, xPathReplacementDict or {})

                    if metric == metricXPath:
                        # No replacement was done, try to evaluate xpath.
                        metric = monitorXmlDoc.xpathEval('%s' % metricXPath)

                    self._logger.debug(
                        '[%s] Got metric: [%s]' % (self.__class__.__name__, metric))

                    if metric == "" or metric == "nan":
                        self._logger.debug(
                            '[%s] Metric is not defined, will not trigger'
                            ' action' % (self.__class__.__name__))

                        triggerAction = False

                        break

                    operator = condition.getEvaluationOperator()

                    triggerValue = self.__replaceXPathVariables(
                        condition.getTriggerValue(),
                        xPathReplacementDict or {})

                    trigger = self.__evaluateNumbers(
                        metric, operator, triggerValue)

                    if trigger is None:
                        trigger = self.__evaluateStrings(
                            metric, operator, triggerValue)

                    self._logger.debug(
                        '[%s] Evaluation result: [%s]' % (
                            self.__class__.__name__, trigger))

                    if not trigger:
                        triggerAction = False
                        break
            else:
                self._logger.debug(
                    '[%s] No monitor xml doc, will not trigger action' % (
                        self.__class__.__name__))
        except Exception as ex:
            self._logger.error(
                '[%s] Could not evaluate data: %s' % (self.__class__.__name__, ex))

            self._logger.debug(
                '[%s] Will not trigger action' % (self.__class__.__name__))

        self._logger.debug(
            '[%s] Returning trigger action flag: [%s]' % (
                self.__class__.__name__, triggerAction))

        return triggerAction

    def __evaluateXPathVariables(self, xmlDoc, xPathVariableList):
        resultDict = {}

        if not xmlDoc:
            return resultDict

        self._logger.debug(
            '[%s] xPath variable list: %s' % (
                self.__class__.__name__, xPathVariableList))

        for v in xPathVariableList:
            name = v.getName()

            value = ''

            try:
                self._logger.debug(
                    '[%s] Evaluating xPath variable %s: %s' % (
                        self.__class__.__name__, name, v.getXPath()))

                value = xmlDoc.xpathEval('%s' % v.getXPath())
            except Exception as ex:
                self._logger.error(
                    '[%s] Could not evaluate xPath variable [%s]: %s' % (
                        self.__class__.__name__, name, ex))

                self._logger.debug(
                    '[%s] Will replace it with empty string' % (
                        self.__class__.__name__))

            resultDict[name] = value

        self._logger.debug(
            '[%s] XPath variable replacement dictionary: %s' % (
                self.__class__.__name__, resultDict))

        return resultDict

    def __replaceXPathVariables(self, inputString, xPathReplacementDict): \
            # pylint: disable=no-self-use
        outputString = inputString

        #self._logger.debug('Original string: %s' % inputString)

        for key in xPathReplacementDict:
            #self._logger.debug('Replacing: %s' % key)

            outputString = outputString.replace(
                key, '%s' % xPathReplacementDict[key])

        #self._logger.debug('New string: %s' % outputString)

        return outputString

    def __poll(self, rule):
        ruleId = self.__getRuleId(rule.getApplicationName(), rule.getName())

        self._logger.debug('[%s] Begin poll timer for [%s]' % (
            self.__class__.__name__, ruleId))

        if not self.hasRule(ruleId):
            self._logger.debug(
                '[%s] Timer execution cancelled for [%s]' % (
                    self.__class__.__name__, ruleId))

            return

        rule.ruleInvoked()

        self._logger.debug(
            '[%s] Timer execution started for [%s]' % (
                self.__class__.__name__, ruleId))

        appMonitor = rule.getApplicationMonitor()

        queryCmd = appMonitor.getQueryCommand()

        self._logger.debug(
            '[%s] Query command: %s' % (self.__class__.__name__, queryCmd))

        actionCmd = appMonitor.getActionCommand()

        self._logger.debug(
            '[%s] Action command: %s' % (self.__class__.__name__, actionCmd))

        xPathReplacementDict = {}

        try:
            invokeAction = True
            queryStdOut = None

            if queryCmd:
                self._logger.debug(
                    '[%s] About to invoke: [%s]' % (
                        self.__class__.__name__, queryCmd))

                try:
                    p = tortugaSubprocess.executeCommand(
                        'source %s/tortuga.sh && ' % (
                            self._cm.getEtcDir()) + queryCmd)

                    queryStdOut = p.getStdOut()

                    appMonitor.queryInvocationSucceeded()
                except Exception as ex:
                    appMonitor.queryInvocationFailed()
                    raise

                monitorXmlDoc = self.__parseMonitorData(queryStdOut)

                xPathReplacementDict = self.__evaluateXPathVariables(
                    monitorXmlDoc, rule.getXPathVariableList())

                invokeAction = self.__evaluateConditions(
                    rule, monitorXmlDoc, xPathReplacementDict)

            if invokeAction:
                try:
                    actionCmd = self.__replaceXPathVariables(
                        actionCmd, xPathReplacementDict)

                    self._logger.debug(
                        '[%s] About to invoke: [%s]' % (
                            self.__class__.__name__, actionCmd))

                    p = tortugaSubprocess.executeCommand(
                        'source %s/tortuga.sh && ' % (
                            self._cm.getEtcDir()) + actionCmd)

                    appMonitor.actionInvocationSucceeded()

                    self._logger.debug(
                        '[%s] Done with command: [%s]' % (
                            self.__class__.__name__, actionCmd))
                except Exception as ex:
                    appMonitor.actionInvocationFailed()
                    raise
            else:
                self._logger.debug(
                    '[%s] Will skip action: [%s]' % (
                        self.__class__.__name__, actionCmd))
        except TortugaException as ex:
            self._logger.error('[%s] %s' % (self.__class__.__name__, ex))

        scheduleTimer = True

        if self.hasRule(ruleId):
            # Check if we need to stop invoking this rule.
            maxActionInvocations = appMonitor.getMaxActionInvocations()

            successfulActionInvocations = \
                appMonitor.getSuccessfulActionInvocations()

            if maxActionInvocations:
                if int(maxActionInvocations) <= successfulActionInvocations:
                    # Rule must be disabled.
                    self._logger.debug(
                        '[%s] Max. number of successful invocations (%s)'
                        ' reached for rule [%s]' % (
                            self.__class__.__name__, maxActionInvocations, ruleId))

                    scheduleTimer = False
                    self.disableRule(rule.getApplicationName(), rule.getName())
        else:
            # Rule is already deleted.
            scheduleTimer = False

        if scheduleTimer:
            pollPeriod = float(appMonitor.getPollPeriod())

            # Make sure we do not fire too often.
            lastSuccessfulActionTime = \
                appMonitor.getLastSuccessfulActionInvocationTime()

            if lastSuccessfulActionTime:
                now = time.time()

                possibleNewSuccessfulActionTime = \
                    now + pollPeriod - lastSuccessfulActionTime

                if possibleNewSuccessfulActionTime < self._minTriggerInterval:
                    pollPeriod = self._minTriggerInterval

                    self._logger.debug(
                        '[%s] Increasing poll period to [%s] for'
                        ' rule [%s]' % (
                            self.__class__.__name__, pollPeriod, ruleId))

            self._logger.debug(
                '[%s] Scheduling new timer for rule [%s] in'
                ' [%s] seconds' % (self.__class__.__name__, ruleId, pollPeriod))

            t = threading.Timer(pollPeriod, self.__poll, args=[rule])

            t.daemon = True

            self.__runPollTimer(ruleId, t)
        else:
            self._logger.debug(
                '[%s] Will not schedule new timer for rule [%s]' % (
                    self.__class__.__name__, rule))

    def __runPollTimer(self, ruleId, pollTimer):
        self._pollTimerDict[ruleId] = pollTimer

        self._logger.debug(
            '[%s] Starting poll timer for [%s]' % (self.__class__.__name__, ruleId))

        pollTimer.start()

    def __cancelPollTimer(self, ruleId):
        if ruleId not in self._pollTimerDict:
            self._logger.debug(
                '[%s] No poll timer for [%s]' % (self.__class__.__name__, ruleId))

            return

        pollTimer = self._pollTimerDict[ruleId]

        self._logger.debug(
            '[%s] Stopping poll timer for [%s]' % (self.__class__.__name__, ruleId))

        pollTimer.cancel()

        del self._pollTimerDict[ruleId]

    def __process(self):
        self._logger.debug(
            '[%s] Begin processing timer' % (self.__class__.__name__))

        while True:
            qSize = self._receiveQ.qsize()

            self._logger.debug(
                '[%s] Current receive Q size: %s' % (
                    self.__class__.__name__, qSize))

            if qSize == 0:
                break

            applicationName, applicationData = self._receiveQ.get()

            self._logger.debug(
                '[%s] Processing data for [%s]' % (
                    self.__class__.__name__, applicationName))

            monitorXmlDoc = self.__parseMonitorData(applicationData)

            for ruleId in self._receiveRuleDict.keys():
                rule = self._receiveRuleDict.get(ruleId)

                # Rule might have been cancelled before we use it.
                if not rule:
                    continue

                # Check if this is appropriate for the data.
                if rule.getApplicationName() != applicationName:
                    continue

                self._logger.debug(
                    '[%s] Processing data using rule [%s]' % (
                        self.__class__.__name__, ruleId))

                rule.ruleInvoked()

                appMonitor = rule.getApplicationMonitor()

                actionCmd = appMonitor.getActionCommand()

                self._logger.debug('[%s] Action command: [%s]' % (
                    self.__class__.__name__, actionCmd))

                try:
                    xPathReplacementDict = self.__evaluateXPathVariables(
                        monitorXmlDoc, rule.getXPathVariableList())

                    invokeAction = self.__evaluateConditions(
                        rule, monitorXmlDoc, xPathReplacementDict)

                    if invokeAction:
                        try:
                            actionCmd = self.__replaceXPathVariables(
                                actionCmd, xPathReplacementDict)

                            self._logger.debug(
                                '[%s] About to invoke: [%s]' % (
                                    self.__class__.__name__, actionCmd))

                            tortugaSubprocess.executeCommand(
                                'source %s/tortuga.sh && ' % (
                                    self._cm.getEtcDir()) + actionCmd)

                            appMonitor.actionInvocationSucceeded()

                            self._logger.debug(
                                '[%s] Done with command: [%s]' % (
                                    self.__class__.__name__, actionCmd))

                            maxActionInvocations = \
                                appMonitor.getMaxActionInvocations()

                            successfulActionInvocations = \
                                appMonitor.getSuccessfulActionInvocations()

                            if maxActionInvocations:
                                if int(maxActionInvocations) <= \
                                        successfulActionInvocations:
                                    # Rule must be disabled.
                                    self._logger.debug(
                                        '[%s] Max. number of successful'
                                        ' invocations (%s) reached for'
                                        ' rule [%s]' % (
                                            self.__class__.__name__,
                                            maxActionInvocations, ruleId))

                                    self.disableRule(
                                        rule.getApplicationName(),
                                        rule.getName())
                        except Exception as ex:
                            appMonitor.actionInvocationFailed()
                    else:
                        self._logger.debug(
                            '[%s] Will skip action: [%s]' % (
                                self.__class__.__name__, actionCmd))
                except TortugaException as ex:
                    self._logger.error('[%s] %s' % (self.__class__.__name__, ex))

            self._logger.debug(
                '[%s] No more rules appropriate for [%s]' % (
                    self.__class__.__name__, applicationName))

        # No more data to process, exit timer.
        self._logger.debug('[%s] No more data to process' % (self.__class__.__name__))

        self.__cancelProcessingTimer()

    def __runProcessingTimer(self):
        self._processingLock.acquire()

        try:
            if not self._processingTimerRunning:
                self._logger.debug(
                    '[%s] Starting processing timer' % (self.__class__.__name__))

                self._processingTimer = threading.Timer(5, self.__process)
                self._processingTimer.daemon = True
                self._processingTimer.start()
                self._processingTimerRunning = True
            else:
                self._logger.debug(
                    '[%s] Processing timer already running' % (
                        self.__class__.__name__))
        finally:
            self._processingLock.release()

    def __cancelProcessingTimer(self):
        self._processingLock.acquire()

        try:
            self._processingTimerRunning = False

            self._logger.debug(
                '[%s] Processing timer stopped' % (self.__class__.__name__))
        finally:
            self._processingLock.release()

    def hasRule(self, ruleId):
        return ruleId in self._ruleDict

    def addRule(self, rule):
        self._lock.acquire()

        try:
            return self.__addRule(rule)
        finally:
            self._lock.release()

    def __addRule(self, rule):
        ruleId = self.__getRuleId(rule.getApplicationName(), rule.getName())

        self._logger.debug('[%s] Adding rule: [%s]' % (
            self.__class__.__name__, ruleId))

        self.__checkRuleDoesNotExist(ruleId)

        # Write rule file.
        self.__writeRuleFile(rule)

        rule.decode()

        self._ruleDict[ruleId] = rule
        if rule.isStatusEnabled():
            self.__enableRule(rule)
        else:
            # Rule is disabled, just put it in the 'disabled' dict
            self._disabledRuleDict[ruleId] = rule

        return ruleId

    def __enableRule(self, rule):
        ruleId = self.__getRuleId(rule.getApplicationName(), rule.getName())

        self._logger.debug(
            '[%s] Enabling rule: [%s]' % (self.__class__.__name__, ruleId))

        appMonitor = rule.getApplicationMonitor()

        monitorType = appMonitor.getType()

        rule.setStatusEnabled()

        if monitorType == 'poll':
            self._logger.debug(
                '[%s] [%s] is poll rule' % (self.__class__.__name__, ruleId))

            pollPeriod = appMonitor.getPollPeriod()

            if not pollPeriod:
                pollPeriod = self._minTriggerInterval

            self._logger.debug(
                '[%s] Preparing poll timer with period %s second(s)' % (
                    self.__class__.__name__, pollPeriod))

            t = threading.Timer(float(pollPeriod), self.__poll, args=[rule])
            t.daemon = True
            self.__runPollTimer(ruleId, t)
        elif monitorType == 'receive':
            self._logger.debug(
                '[%s] [%s] is receive rule' % (self.__class__.__name__, ruleId))

            self._receiveRuleDict[ruleId] = rule
        else:
            # assume this is 'event' rule
            self._logger.debug(
                '[%s] [%s] is event rule' % (self.__class__.__name__, ruleId))

            self._eventRuleDict[ruleId] = rule

        if ruleId in self._disabledRuleDict:
            del self._disabledRuleDict[ruleId]

    def enableRule(self, applicationName, ruleName):
        """
        Raises:
            RuleAlreadyEnabled
        """

        self._lock.acquire()

        try:
            ruleId = self.__getRuleId(applicationName, ruleName)

            self.__checkRuleExists(ruleId)

            if ruleId not in self._disabledRuleDict:
                raise RuleAlreadyEnabled(
                    'Rule [%s] is already enabled.' % (ruleId))

            rule = self._ruleDict[ruleId]

            self.__enableRule(rule)

            rule.encode()

            self.__writeRuleFile(rule)

            rule.decode()
        finally:
            self._lock.release()

    def deleteRule(self, applicationName, ruleName):
        self._lock.acquire()
        try:
            return self.__deleteRule(applicationName, ruleName)
        finally:
            self._lock.release()

    def __deleteRule(self, applicationName, ruleName):
        ruleId = self.__getRuleId(applicationName, ruleName)

        self._logger.debug(
            '[%s] Deleting rule %s' % (self.__class__.__name__, ruleId))

        self.__checkRuleExists(ruleId)

        rule = self._ruleDict[ruleId]

        if rule.isStatusEnabled():
            self.__disableRule(rule)

        del self._disabledRuleDict[ruleId]

        del self._ruleDict[ruleId]

        osUtility.removeFile(
            self.__getRuleFileName(applicationName, ruleName))

    # Put rule in the 'disabled' state.
    def disableRule(self, applicationName, ruleName):
        """
        Raises:
            RuleAlreadyDisabled
        """

        self._lock.acquire()

        try:
            ruleId = self.__getRuleId(applicationName, ruleName)

            self.__checkRuleExists(ruleId)

            if ruleId in self._disabledRuleDict:
                raise RuleAlreadyDisabled(
                    'Rule [%s] is already disabled.' % ruleId)

            rule = self._ruleDict[ruleId]

            self.__disableRule(rule)

            rule.encode()

            self.__writeRuleFile(rule)

            rule.decode()
        finally:
            self._lock.release()

    def __disableRule(self, rule, status='disabled by administrator'):
        ruleId = self.__getRuleId(rule.getApplicationName(), rule.getName())

        self._logger.debug(
            '[%s] Disabling rule [%s]' % (self.__class__.__name__, ruleId))

        appMonitor = rule.getApplicationMonitor()

        monitorType = appMonitor.getType()

        rule.setStatus(status)

        if monitorType == 'poll':
            self.__cancelPollTimer(ruleId)
        elif monitorType == 'receive':
            del self._receiveRuleDict[ruleId]
        else:
            del self._eventRuleDict[ruleId]

        self._disabledRuleDict[ruleId] = rule

    def getRule(self, applicationName, ruleName):
        self._lock.acquire()

        try:
            return self.__getRule(applicationName, ruleName)
        finally:
            self._lock.release()

    def __getRule(self, applicationName, ruleName):
        ruleId = self.__getRuleId(applicationName, ruleName)

        self.__checkRuleExists(ruleId)

        return copy.deepcopy(self._ruleDict[ruleId])

    def getRuleList(self):
        self._lock.acquire()
        try:
            return self.__getRuleList()
        finally:
            self._lock.release()

    def __getRuleList(self):
        ruleList = TortugaObjectList()

        for ruleId in self._ruleDict.keys():
            ruleList.append(copy.deepcopy(self._ruleDict[ruleId]))

        return ruleList

    def receiveApplicationData(self, applicationName, applicationData):
        self._lock.acquire()
        try:
            return self.__receiveApplicationData(
                applicationName, applicationData)
        finally:
            self._lock.release()

    def __receiveApplicationData(self, applicationName, applicationData):
        self._logger.debug(
            '[%s] Received data for [%s]' % (
                self.__class__.__name__, applicationName))

        self._receiveQ.put((applicationName, applicationData))

        self.__runProcessingTimer()

    def executeRule(self, applicationName, ruleName, applicationData):
        self._lock.acquire()
        try:
            return self.__executeRule(
                applicationName, ruleName, applicationData)
        finally:
            self._lock.release()

    def __executeRule(self, applicationName, ruleName, applicationData):
        """
        Raises:
            RuleDisabled
        """

        ruleId = self.__getRuleId(applicationName, ruleName)

        self._logger.debug(
            '[%s] Received request to execute rule [%s]' % (
                self.__class__.__name__, ruleId))

        self.__checkRuleExists(ruleId)

        if ruleId in self._disabledRuleDict:
            raise RuleDisabled('Rule [%s] is disabled.' % (ruleId))

        rule = self._ruleDict[ruleId]

        appMonitor = rule.getApplicationMonitor()

        monitorType = appMonitor.getType()

        if monitorType == 'poll':
            self._logger.debug(
                '[%s] [%s] is poll rule' % (self.__class__.__name__, ruleId))

            self.__cancelPollTimer(ruleId)

            self.__poll(rule)
        elif monitorType == 'receive':
            self._logger.debug(
                '[%s] [%s] is receive rule' % (self.__class__.__name__, ruleId))

            self._receiveQ.put((applicationName, applicationData))

            self.__runProcessingTimer()
        else:
            # assume this is 'event' rule
            self._logger.debug(
                '[%s] [%s] is event rule' % (self.__class__.__name__, ruleId))

            self.__execute(rule)

    def __execute(self, rule):
        ruleId = self.__getRuleId(rule.getApplicationName(), rule.getName())

        self._logger.debug(
            '[%s] Begin execution for [%s]' % (self.__class__.__name__, ruleId))

        rule.ruleInvoked()

        appMonitor = rule.getApplicationMonitor()

        queryCmd = appMonitor.getQueryCommand()

        self._logger.debug(
            '[%s] Query command: [%s]' % (self.__class__.__name__, queryCmd))

        actionCmd = appMonitor.getActionCommand()

        self._logger.debug(
            '[%s] Action command: [%s]' % (self.__class__.__name__, actionCmd))

        xPathReplacementDict = {}

        try:
            invokeAction = True
            queryStdOut = None

            if queryCmd:
                self._logger.debug(
                    '[%s] About to invoke: [%s]' % (
                        self.__class__.__name__, queryCmd))

                try:
                    p = tortugaSubprocess.executeCommand(
                        'source %s/tortuga.sh && ' % (
                            self._cm.getEtcDir()) + queryCmd)

                    queryStdOut = p.getStdOut()

                    appMonitor.queryInvocationSucceeded()
                except Exception as ex:
                    appMonitor.queryInvocationFailed()
                    raise

                monitorXmlDoc = self.__parseMonitorData(queryStdOut)

                xPathReplacementDict = self.__evaluateXPathVariables(
                    monitorXmlDoc, rule.getXPathVariableList())

                invokeAction = self.__evaluateConditions(
                    rule, monitorXmlDoc, xPathReplacementDict)

            if invokeAction:
                try:
                    actionCmd = self.__replaceXPathVariables(
                        actionCmd, xPathReplacementDict)

                    self._logger.debug(
                        '[%s] About to invoke: [%s]' % (
                            self.__class__.__name__, actionCmd))

                    p = tortugaSubprocess.executeCommand(
                        'source %s/tortuga.sh && ' % (
                            self._cm.getEtcDir()) + actionCmd)

                    appMonitor.actionInvocationSucceeded()

                    self._logger.debug(
                        '[%s] Done with command: [%s]' % (
                            self.__class__.__name__, actionCmd))
                except Exception as ex:
                    appMonitor.actionInvocationFailed()
                    raise
            else:
                self._logger.debug(
                    '[%s] Will skip action: [%s]' % (
                        self.__class__.__name__, actionCmd))
        except TortugaException as ex:
            self._logger.error('[%s] %s' % (self.__class__.__name__, ex))

        if self.hasRule(ruleId):
            # Check if we need to stop invoking this rule.
            maxActionInvocations = appMonitor.getMaxActionInvocations()

            successfulActionInvocations = \
                appMonitor.getSuccessfulActionInvocations()

            if maxActionInvocations:
                if int(maxActionInvocations) <= successfulActionInvocations:
                    # Rule must be disabled.
                    self._logger.debug(
                        '[%s] Max. number of successful invocations (%s)'
                        ' reached for rule [%s]' % (
                            self.__class__.__name__, maxActionInvocations, ruleId))

                    self.disableRule(rule.getApplicationName(), rule.getName())

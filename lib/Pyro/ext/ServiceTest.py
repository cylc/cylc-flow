#############################################################################
#
#	A test for the PyroNS_NTService program
#   Author: Syver Enstad  syver-en@online.no
#
#	This is part of "Pyro" - Python Remote Objects
#	Which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

import unittest
import win32serviceutil
import win32service
import time
import Pyro.nsc

ServiceName = 'PyroNS'

class Test(unittest.TestCase):
	def setUp(self):
		win32serviceutil.StartService(ServiceName)
		
	def testStartPending(self):
		svcType, svcState, svcControls, err, svcErr, svcCP, svcWH = \
				 win32serviceutil.QueryServiceStatus(ServiceName)
		assert svcState & win32service.SERVICE_START_PENDING
		
	def testFullyStarted(self):
		self._waitForStarted()
		svcType, svcState, svcControls, err, svcErr, svcCP, svcWH = \
				 win32serviceutil.QueryServiceStatus(ServiceName)
		assert svcType & win32service.SERVICE_WIN32_OWN_PROCESS
		assert svcState & win32service.SERVICE_RUNNING
		assert svcControls & win32service.SERVICE_ACCEPT_STOP

	def testStop(self):
		self._waitForStarted()
		svcType, svcState, svcControls, err, svcErr, svcCP, svcWH = \
				 win32serviceutil.StopService(ServiceName)
		assert svcState & win32service.SERVICE_STOPPED
		assert svcType & win32service.SERVICE_WIN32_OWN_PROCESS

	def testNameserverAvailable(self):
		self._waitForStarted()
		ctrl = Pyro.nsc.PyroNSControl()
		ctrl.args(None)
		ctrl.ping()

	def testNameserverShutdownFromNsc(self):
		self._waitForStarted()
		ctrl = Pyro.nsc.PyroNSControl()
		ctrl.args(None)
		ctrl.shutdown()
		for each in range(100):
			svcType, svcState, svcControls, err, svcErr, svcCP, svcWH = \
					 win32serviceutil.QueryServiceStatus(ServiceName)
			if svcState & win32service.SERVICE_STOPPED:
				return
			time.sleep(0.20)
		self.fail()

	def tearDown(self):
		for each in range(1000):
			svcType, svcState, svcControls, err, svcErr, svcCP, svcWH = \
					 win32serviceutil.QueryServiceStatus(ServiceName)
			if svcState & win32service.SERVICE_RUNNING:
				svcType, svcState, svcControls, err, svcErr, svcCP, svcWH = \
						 win32serviceutil.StopService(ServiceName)
				time.sleep(0.1)
			elif svcState & win32service.SERVICE_STOPPED:
				time.sleep(0.10)
				break
			else:
				time.sleep(0.10)
		assert svcState & win32service.SERVICE_STOPPED
		time.sleep(3)

	def _waitForStarted(self):
		for each in range(100):
			svcType, svcState, svcControls, err, svcErr, svcCP, svcWH = \
					 win32serviceutil.QueryServiceStatus(ServiceName)
			if svcState & win32service.SERVICE_RUNNING:
				break
			else:
				time.sleep(0.10)

		
if __name__ == '__main__':
	unittest.main()

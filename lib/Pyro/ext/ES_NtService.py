#############################################################################
#
#	An NT service that runs the Pyro Event Service
#   Author: Syver Enstad  syver-en@online.no
#
#	This is part of "Pyro" - Python Remote Objects
#	Which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

import win32serviceutil
import threading
import win32service
import win32api
from BasicNTService import BasicNTService, getRegistryParameters


def setConfig():
	Pyro.config.PYRO_TRACELEVEL=3
	Pyro.config.PYRO_STORAGE = os.path.splitdrive(win32api.GetSystemDirectory())[0]+os.sep
	Pyro.config.PYRO_LOGFILE = "Pyro_ES_svc.log"


import os,sys
import Pyro.util
setConfig()
Log=Pyro.util.Log
from Pyro.EventService import Server


class PyroESThread(threading.Thread):
	""" The Pyro Event Service will run in this thread
	"""
	def __init__(self, args, stopcallback):
		threading.Thread.__init__(self)
		self._args = list(args)
		self._stopcallback = stopcallback
		
	def run(self):
		self.startPyroES()
		self._stopcallback()

	def startPyroES(self):
		Log.msg("PyroES_svc","Pyro ES service is starting, arguments=",self._args)	
		""" ripped out of Pyro.EventService.Server and slightly changed to
		accomodate not using sys.argv, but self._args instead
		"""

		try:
			Args = Pyro.util.ArgParser()
			Args.parse(self._args,'hn:p:i:')
			if Args.hasOpt('h'):
				Log.error("PyroES_svc","""
Usage: es [-h] [-n hostname] [-p port] [-i identification]
  where -p = ES server port
        -n = non-default hostname to bind on
        -i = the required authentication ID for ES clients,
             also used to connect to other Pyro services
        -h = print this help
""")
				raise SystemExit
			host = Args.getOpt('n','')
			port = Args.getOpt('p',None)
			ident = Args.getOpt('i',None)
			if port:
				port=int(port)
			if Args.ignored:
				Log.warn("PyroES_svc",'Ignored options:',Args.ignored)
			if Args.args:
				Log.warn("PyroES_svc",'Ignored arguments:',Args.args)

			Log.msg("PyroES_scv", "Starting the Event Server.")
			self.starter=Server.EventServiceStarter(identification=ident)
			self.starter.start(host,port)

		except Exception,x :
			Log.error("PyroES_scv","COULD NOT START!!!",x)
			raise SystemExit
	
	def shutdown(self):
		self.starter.running=0

	
class PyroES_NTService(BasicNTService):
	_svc_name_ = 'PyroES'
	_svc_display_name_ = "Pyro Event Service"
	_svc_description_ = "Provides event topics and publish/subscribe communication for Pyro"
	def __init__(self, args):
		super(PyroES_NTService, self).__init__(args)
		setConfig()
		try:
			args = getRegistryParameters(self._svc_name_).split()
		except Exception,x:
			Log.error("PyroES_svc","PROBLEM GETTING ARGS FROM REGISTRY:",x)
		self._esThread = PyroESThread(args, self.SvcStop)
		
	def _doRun(self):
		""" Overriden """
		self._esThread.start()

	def _doStop(self):
		""" Overridden """
		self._esThread.shutdown()
		self._esThread.join()

	def SvcStop(self):
		"""Overriden """
		super(PyroES_NTService, self).SvcStop()
		

if __name__ == '__main__':
	PyroES_NTService.HandleCommandLine()

#############################################################################
#
#	An NT service that runs the Pyro Name Server
#   Author: Syver Enstad; syver-en@online.no
#   Bugfix for recent win32 builds: David Rushby; woodsplitter@rocketmail.com
#
#	This is part of "Pyro" - Python Remote Objects
#	Which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################

import sys
import win32serviceutil
import threading
import win32service
import win32api
import win32con


class BasicNTService(win32serviceutil.ServiceFramework, object):
	""" Abstract base to help out with building NT services
	in Python with the win32all(by Mark Hammond) support for
	python nt services.

	Remember to set the two following class attributes
	to something sensible in your subclass
	_svc_name_ = 'PyroNS'
	_svc_display_name_ = 'Pyro Naming Service NT service'

	The following are optional
	 _svc_deps_: This should be set to the list of service names
				 That need to be started before this one.
	 _exe_name_: This should be set to a service .EXE if you're not
				 going to use PythonService.exe
	 _svc_description_ : This is the descriptive string that you find
						 in the services applet

	To register the service with the SCM the easiest way is to include the
	following at the bottom of the file where your subclass is defined.
	if __name__ == '__main__':
		TheClassYouDerivedFromBasicNTService.HandleCommandLine()

	"""
	def __init__(self, args):
		_redirectSystemStreamsIfNecessary()

		win32serviceutil.ServiceFramework.__init__(self, args)
		self._stopEvent = threading.Event()

	def SvcStop(self):
		""" Template method from win32serviceutil.ServiceFramework"""
		# first tell SCM that we have started the stopping process
		self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
		self._stopEvent.set()

	def _shouldStop(self):
		return self._stopEvent.isSet()

	def _doRun(self):
		raise NotImplementedError

	def _doStop(self):
		raise NotImplementedError

	def SvcDoRun(self):
		""" part of Template method SvcRun
		from win32serviceutil.ServiceFramework"""
		self.logStarted()
		self._doRun()
		self._stopEvent.wait()
		self._doStop()
		self.logTermination()
		return 0

	def logTermination(self):
		import servicemanager
		servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
									  servicemanager.PYS_SERVICE_STOPPED,
									   (self._svc_name_, ""))

	def logStarted(self):
		import servicemanager
		servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
							  servicemanager.PYS_SERVICE_STARTED,
							  (self._svc_name_, ''))

	def CustomOptionHandler(cls, opts):
		#out=open("c:\\log.txt","w")
		print "Installing the Pyro %s" % cls._svc_name_
		args = raw_input("Enter command line arguments for %s: " % cls._svc_name_)
		try:
			createRegistryParameters(cls._svc_name_, args.strip())
		except Exception,x:
			print "Error occured when setting command line args in the registry: ",x
		try:
			cls._svc_description_
		except LookupError:
			return

		key = win32api.RegCreateKey(win32con.HKEY_LOCAL_MACHINE,
			"System\\CurrentControlSet\\Services\\%s" % cls._svc_name_)
		try:
			win32api.RegSetValueEx(key, "Description", 0, win32con.REG_SZ, cls._svc_description_);
		finally:
			win32api.RegCloseKey(key)
	CustomOptionHandler = classmethod(CustomOptionHandler)


	def HandleCommandLine(cls):
		if win32serviceutil.HandleCommandLine(cls, customOptionHandler=cls.CustomOptionHandler) != 0:
			return     # some error occured
		if sys.argv[1] in ("install", "update"):
			print "\nYou can configure the command line arguments in the Registry."
			print "The key is: HKLM\\System\\CurrentControlSet\\Services\\%s" % cls._svc_name_
			print "The value under that key is:  ", pyroArgsRegkeyName
			args=getRegistryParameters(cls._svc_name_)
			if args:
				print "(it is currently set to:  '%s')" % args
			else:
				print "(it is currently not set)"
			print
	HandleCommandLine = classmethod(HandleCommandLine)



pyroArgsRegkeyName = "PyroServiceArguments"


def getRegistryParameters(servicename):
	key=win32api.RegOpenKey(win32con.HKEY_LOCAL_MACHINE, "System\\CurrentControlSet\\Services\\"+servicename)
	try:
		try:
			(commandLine, regtype) = win32api.RegQueryValueEx(key,pyroArgsRegkeyName)
			return commandLine
		except:
			pass
	finally:
		key.Close()

	createRegistryParameters(servicename, pyroArgsRegkeyName)
	return ""


def createRegistryParameters(servicename, parameters):
	newkey=win32api.RegOpenKeyEx(win32con.HKEY_LOCAL_MACHINE, "System\\CurrentControlSet\\Services\\"+servicename,0,win32con.KEY_ALL_ACCESS)
	try:
		win32api.RegSetValueEx(newkey, pyroArgsRegkeyName, 0, win32con.REG_SZ, parameters)
	finally:
		newkey.Close()


def _redirectSystemStreamsIfNecessary():
	# Python programs running as Windows NT services must not send output to
	# the default sys.stdout or sys.stderr streams, because those streams are
	# not fully functional in the NT service execution environment.  Sending
	# output to them will eventually (but not immediately) cause an IOError
	# ("Bad file descriptor"), which can be quite mystifying to the
	# uninitiated.  This problem can be overcome by replacing the default
	# system streams with a stream that discards any data passed to it (like
	# redirection to /dev/null on Unix).
	#
	# However, the pywin32 service framework supports a debug mode, under which
	# the streams are fully functional and should not be redirected.
	shouldRedirect = True
	try:
		import servicemanager
	except ImportError:
		# If we can't even 'import servicemanager', we're obviously not running
		# as a service, so the streams shouldn't be redirected.
		shouldRedirect = False
	else:
		# Unlike previous builds, pywin32 builds >= 200 allow the
		# servicemanager module to be imported even in a program that isn't
		# running as a service.  In such a situation, it would not be desirable
		# to redirect the system streams.
		#
		# However, it was not until pywin32 build 203 that a 'RunningAsService'
		# predicate was added to allow client code to determine whether it's
		# running as a service.
		#
		# This program logic redirects only when necessary if using any build
		# of pywin32 except 200-202.  With 200-202, the redirection is a bit
		# more conservative than is strictly necessary.
		if (
			servicemanager.Debugging()
			or (
					hasattr(servicemanager, 'RunningAsService')
				and not servicemanager.RunningAsService()
			  )
		  ):
			shouldRedirect = False

	if shouldRedirect:
		sys.stdout = sys.stderr = open('nul', 'w')

	return shouldRedirect

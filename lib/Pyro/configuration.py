#############################################################################
#
#	Sets up Pyro's configuration (Pyro.config).
#
#	This is part of "Pyro" - Python Remote Objects
#	Which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################


# Initialize Pyro Configuration.

import re, os, random, tempfile
import Pyro.errors
from Pyro.errors import PyroError
import Pyro.constants
import Pyro.util2				# not util because of cyclic dependency

try:
	from pickle import HIGHEST_PROTOCOL as PICKLE_HIGHEST_PROTOCOL
except ImportError:
	PICKLE_HIGHEST_PROTOCOL = 1
	

# ---------------------- DEFAULT CONFIGURATION VARIABLES -----------

# Special characters are '$CURDIR' (current directory, absolute) and
# $STORAGE which is replaced by the PYRO_STORAGE path.
_defaults= {
	'PYRO_STORAGE':			'$CURDIR',	# current dir (abs)
	'PYRO_HOST':			'',
	'PYRO_PUBLISHHOST':		None,
	'PYRO_PORT':			7766,
	'PYRO_PORT_RANGE':		100,
	'PYRO_NS_HOSTNAME':		None,
	'PYRO_NS_PORT':			9090,	# tcp
	'PYRO_NS_BC_ADDR':		None,
	'PYRO_NS_BC_PORT':		9090,	# udp
	'PYRO_NS2_HOSTNAME':	None,
	'PYRO_NS2_PORT':		9091,	# tcp
	'PYRO_NS2_BC_ADDR':		None,
	'PYRO_NS2_BC_PORT':		9091,	# udp
	'PYRO_NS_URIFILE':		'$STORAGE/Pyro_NS_URI', # (abs)
	'PYRO_NS_DEFAULTGROUP': ':Default',
	'PYRO_BC_RETRIES':		1,
	'PYRO_BC_TIMEOUT':		0.75,
	'PYRO_PICKLE_FORMAT':	PICKLE_HIGHEST_PROTOCOL,
	'PYRO_XML_PICKLE':		None,
	'PYRO_GNOSIS_PARANOIA': 0,
	'PYRO_TRACELEVEL':		0,
	'PYRO_USER_TRACELEVEL':	0,
	'PYRO_LOGFILE':			'$STORAGE/Pyro_log',		# (abs)
	'PYRO_USER_LOGFILE':	'$STORAGE/Pyro_userlog',	# (abs)
	'PYRO_STDLOGGING':		0,
	'PYRO_STDLOGGING_CFGFILE': 'logging.cfg',
	'PYRO_MAXCONNECTIONS':	200,
	'PYRO_TCP_LISTEN_BACKLOG':   200,
	'PYRO_BROKEN_MSGWAITALL':   0,
	'PYRO_MULTITHREADED':	1,							# assume 1
	'PYRO_COMPRESSION':		0,
	'PYRO_MOBILE_CODE':		0,
	'PYRO_DNS_URI':			0,
	'PYRO_CHECKSUM':		0,
	'PYRO_SOCK_KEEPALIVE':	1,
	'PYRO_ES_QUEUESIZE':	1000,
	'PYRO_ES_BLOCKQUEUE':	1,
	'PYRO_DETAILED_TRACEBACK': 0,
	'PYRO_ONEWAY_THREADED': 1,
	'PYROSSL_CERTDIR':		'$STORAGE/certs',			# (abs)
	'PYROSSL_CA_CERT':		'ca.pem',
	'PYROSSL_CERT':	'host.pem',
	'PYROSSL_KEY':	None,
	'PYROSSL_POSTCONNCHECK': 1
}

# ---------------------- END OF DEFAULT CONFIGURATION VARIABLES -----


class Config(object):

	def __init__(self):
		_defaults['PYRO_MULTITHREADED']=Pyro.util2.supports_multithreading()
		self.__dict__[Pyro.constants.CFGITEM_PYRO_INITIALIZED] = 0

	def __eq__(self, other):
		return self.__dict__==other.__dict__

	def setup(self, configFile):
		reader = ConfigReader(_defaults)
		try:
			reader.parse(configFile)
		except EnvironmentError,x:
			raise PyroError("Error reading config file: "+configFile+"; "+str(x));
		self.__dict__.update(reader.items)
		if configFile:
			self.__dict__['PYRO_CONFIG_FILE'] = os.path.abspath(configFile)
		else:
			self.__dict__['PYRO_CONFIG_FILE'] = ''

	def finalizeConfig_Client(self):
		# For the client, we're done for now!
		# It's nice if the storage directory exists and is
		# writable, but if it isn't, we can continue happily.
		# If Pyro needs to write something (log?), it will
		# fail at that point if it can't access the storage dir.
		# This behavior is good enough for clients.
		pass

	def finalizeConfig_Server(self, storageCheck):
		if storageCheck:
			# The server needs a storage dir. Because it's a server,
			# this usually is no problem. So create & test it here.
			# Create the storage directory if it doesn't exist yet
			if not os.path.exists(self.PYRO_STORAGE):
				os.mkdir(self.PYRO_STORAGE)
			# see if we have permission there, in a thread-safe fashion.
			if not os.path.isdir(self.PYRO_STORAGE):
				raise IOError('PYRO_STORAGE is not a directory ['+self.PYRO_STORAGE+']')
				
			try:
				if os.name=='java':
					# jython doesn't have suitable TemporaryFile implementation (lacks dir param)
					javatestfile=os.path.join(self.PYRO_STORAGE,'_pyro_'+str(random.random())+".tmp")
					f=open(javatestfile,"w")
				else:
					# use tempfile to safely create a unique temporary file even on multi-cpu nodes
					f=tempfile.TemporaryFile(dir=self.PYRO_STORAGE, suffix='.tmp', prefix='_pyro_')
			except Exception,x:
				print x
				raise IOError('no write access to PYRO_STORAGE ['+self.PYRO_STORAGE+']')
			else:
				f.close()
				if os.name=='java':
					os.remove(javatestfile)

#	def __getattr__(self,name):
#		# add smart code here to deal with other requested config items!



class ConfigReader(object):
	def __init__(self, defaults):
		self.matcher=re.compile(r'^(\w+)\s*=\s*(\S*)')
		self.items=defaults.copy()

	def _check(self, filename):
		print "ConfigReader: checking file", filename
		items=[]
		for l in open(filename).readlines():
			l=l.rstrip()
			if not l or l.startswith('#'):  
				continue     # skip empty line or comment
			match=self.matcher.match(l)
			if match:
				items.append(match.group(1))
		allitems=self.items.keys()
		allitems.sort()
		for item in allitems:
			if item not in items:
				print "MISSING item: ",item
			try:
				items.remove(item)
			except ValueError:
				pass
		if items:
			print "items NOT in DEFAULTS:", items
		else:
			print "ok!"


	def parse(self, filename):
		linenum=0
		if filename:
			for l in open(filename).readlines():
				l=l.rstrip()
				linenum=linenum+1
				if not l or l.startswith('#'):  
					continue     # skip empty line or comment
				match=self.matcher.match(l)
				if match:
					if match.group(1) in _defaults.keys():
						if match.group(2):
							self.items[match.group(1)] = match.group(2)
					else:
						raise KeyError('Unknown config item in configfile (line %d): %s' % (linenum, match.group(1)))
				else:
					raise ValueError('Syntax error in config file, line '+str(linenum))

		# Parse the environment variables (they override the config file)
		self.items.update(self.processEnv(_defaults.keys()))

		# First, fix up PYRO_STORAGE because others depend on it.
		self.items['PYRO_STORAGE'] = self.treatSpecial(self.items['PYRO_STORAGE'])
		# Now fix up all other items:
		for i in self.items.keys():
			newVal = self.treatSpecial(self.items[i])
			if i in ('PYRO_STORAGE', 'PYRO_LOGFILE', 'PYRO_USER_LOGFILE', 'PYRO_NS_URIFILE'):
				newVal=os.path.abspath(newVal)
			# fix the variable type if it's an integer or float
			if type(_defaults[i]) == type(42):
				newVal = int(newVal)
			if type(_defaults[i]) == type(0.1):
				newVal = float(newVal)
			self.items[i]= newVal

	def processEnv(self, keys):
		env={}
		for key in keys:
			try: env[key] = os.environ[key]
			except KeyError: pass
		return env

	def treatSpecial(self, value):
		# treat special escape strings
		if type(value)==type(""):
			if value=='$CURDIR':
				return os.curdir
			elif value.startswith('$STORAGE/'):
				return os.path.join(self.items['PYRO_STORAGE'], value[9:])
		return value

# easy config diagnostic with python -m
if __name__=="__main__":
	print "Pyro version:",Pyro.constants.VERSION
	r=ConfigReader(_defaults)
	if os.path.exists("Pyro.conf"):
		r._check("Pyro.conf")
	x=Config()
	if os.path.exists("Pyro.conf"):
		x.setup("Pyro.conf")
	else:
		x.setup(None)
	x.finalizeConfig_Server(1)
	items=vars(x).items()
	items.sort()
	print "Active configuration settings:"
	for item,value in items:
		print item+"="+str(value)

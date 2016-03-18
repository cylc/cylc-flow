#############################################################################
#
#	Pyro global constants
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@razorvine.net
#
#############################################################################


# General Pyro Version String ####
VERSION = '3.16'

# Fixed (internal) GUIDs
INTERNAL_DAEMON_GUID='c0000000'+'01100000'+'10000000'+'10000001'

# Pyro names for the standard Services
NAMESERVER_NAME		= ":Pyro.NameServer"
EVENTSERVER_NAME	= ":Pyro.EventService"

# Pyro traceback attribute for remote exceptions
TRACEBACK_ATTRIBUTE	= "remote_stacktrace"


#### Remote Invocation Flags (bit flags) ####

RIF_Varargs  = (1<<0)		# for '*args' syntax
RIF_Keywords = (1<<1)		# for '**keywords' syntax
RIF_Oneway   = (1<<2)		# for oneway (no result) messages - currently internal use only
RIF_VarargsAndKeywords = RIF_Varargs | RIF_Keywords


#### Reasons why a connection may be denied ####
DENIED_UNSPECIFIED=0
DENIED_SERVERTOOBUSY=1
DENIED_HOSTBLOCKED=2
DENIED_SECURITY=3

deniedReasons={
	DENIED_UNSPECIFIED:'unspecified reason',
	DENIED_SERVERTOOBUSY:'server too busy',
	DENIED_HOSTBLOCKED:'host blocked',
	DENIED_SECURITY:'security reasons' 
	}

# special config items
CFGITEM_PYRO_INITIALIZED = "_PYRO_INITIALIZED"

# NS roles
NSROLE_SINGLE=0
NSROLE_PRIMARY=1
NSROLE_SECONDARY=2

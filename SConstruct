# Basic scons build control file for cycon
# Hilary Oliver,  April 2009

import os, sys

version=""

# Read $CYCON_VERSION from the environment and refuse to build if
# the variable is not defined

try:
	version = os.environ['CYCON_VERSION']
except:
	print "ERROR: environment variable $CYCON_VERSION not defined"
	sys.exit()

if len( version ) == 0:
	print "ERROR: environment variable $CYCON_VERSION empty"
	sys.exit()

print "Installing CYCON version " + version
# For now, just copy into a top level directory called 'cycon'

install_dir = os.environ.get("HOME") + '/cycon'

# MODIFY THE SOURCE CODE BEFORE INSTALLING
# insert the version tag into the banner in the cycon main program
command = """
	cd bin; 
	cat cycon | sed -e 's/\(\s*cycon_version =\).*/\\1 \"""" + version + """\";/' > tmp1 || exit 1;
	mv tmp1 cycon || exit 1
	chmod +x cycon || exit 1
	"""
if os.system( command ):
	print "Failed to insert cycon version number into cycon"
	sys.exit()

# INSTALL FILES
all = [ 'bin', 'doc', 'system-def', 'src', 'README.install', 'README.dirs', 'README.run' ]
env = Environment()
i_a = env.Install( install_dir, all )

# define an alias so we can say 'scons install'
Alias( 'install', i_a )

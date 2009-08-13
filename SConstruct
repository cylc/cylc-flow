# Basic scons build control file for cyclon
# Hilary Oliver,  April 2009

import os, sys

version=""

# Read $CYCLON_VERSION from the environment and refuse to build if
# the variable is not defined

try:
	version = os.environ['CYCLON_VERSION']
except:
	print "ERROR: environment variable $CYCLON_VERSION not defined"
	sys.exit()

if len( version ) == 0:
	print "ERROR: environment variable $CYCLON_VERSION empty"
	sys.exit()

print "Installing CYCLON version " + version
# For now, just copy into a top level directory called 'cyclon'

install_dir = os.environ.get("HOME") + '/cyclon'

# MODIFY THE SOURCE CODE BEFORE INSTALLING
# insert the version tag into the banner in the cyclon main program
command = """
	cd bin; 
	cat cyclon | sed -e 's/\(\s*cyclon_version =\).*/\\1 \"""" + version + """\";/' > tmp1 || exit 1;
	mv tmp1 cyclon || exit 1
	chmod +x cyclon || exit 1
	"""
if os.system( command ):
	print "Failed to insert cyclon version number into cyclon"
	sys.exit()

# INSTALL FILES
all = [ 'bin', 'doc', 'system-def', 'src', 'README.install', 'README.dirs', 'README.run' ]
env = Environment()
i_a = env.Install( install_dir, all )

# define an alias so we can say 'scons install'
Alias( 'install', i_a )

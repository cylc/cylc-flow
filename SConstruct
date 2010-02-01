# Basic scons build control file for cylc
# Hilary Oliver,  April 2009

import os, sys

version=""

# Read $CYLC_VERSION from the environment and refuse to build if
# the variable is not defined

try:
	version = os.environ['CYLC_VERSION']
except:
	print "ERROR: environment variable $CYLC_VERSION not defined"
	sys.exit()

if len( version ) == 0:
	print "ERROR: environment variable $CYLC_VERSION empty"
	sys.exit()

print "Installing CYLC version " + version
# For now, just copy into a top level directory called 'cylc'

install_dir = os.environ.get("HOME") + '/cylc'

# MODIFY THE SOURCE CODE BEFORE INSTALLING
# insert the version tag into the banner in the cylc main program
command = """
	cd bin; 
	cat cylc | sed -e 's/\(\s*cylc_version =\).*/\\1 \"""" + version + """\";/' > tmp1 || exit 1;
	mv tmp1 cylc || exit 1
	chmod +x cylc || exit 1
	"""
if os.system( command ):
	print "Failed to insert cylc version number into cylc"
	sys.exit()

# INSTALL FILES
all = [ 'bin', 'doc', 'sys', 'src', 'README.install', 'README.dirs', 'README.run' ]
env = Environment()
i_a = env.Install( install_dir, all )

# define an alias so we can say 'scons install'
Alias( 'install', i_a )

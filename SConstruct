# Basic scons build control file for cylon
# Hilary Oliver,  April 2009

import os, sys

version=""

# Read $CYLON_VERSION from the environment and refuse to build if
# the variable is not defined

try:
	version = os.environ['CYLON_VERSION']
except:
	print "ERROR: environment variable $CYLON_VERSION not defined"
	sys.exit()

if len( version ) == 0:
	print "ERROR: environment variable $CYLON_VERSION empty"
	sys.exit()

print "Installing CYLON version " + version
# For now, just copy into a top level directory called 'cylon'

install_dir = os.environ.get("HOME") + '/cylon'

# MODIFY THE SOURCE CODE BEFORE INSTALLING
# insert the version tag into the banner in the cylon main program
command = """
	cd bin; 
	cat cylon | sed -e 's/\(\s*cylon_version =\).*/\\1 \"""" + version + """\";/' > tmp1 || exit 1;
	mv tmp1 cylon || exit 1
	chmod +x cylon || exit 1
	"""
if os.system( command ):
	print "Failed to insert cylon version number into cylon"
	sys.exit()

# INSTALL FILES
all = [ 'bin', 'doc', 'sys', 'src', 'README.install', 'README.dirs', 'README.run' ]
env = Environment()
i_a = env.Install( install_dir, all )

# define an alias so we can say 'scons install'
Alias( 'install', i_a )

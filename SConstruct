# Basic scons build control file for sequenz
# Hilary Oliver,  April 2009

import os, sys

version=""

# Read $SEQUENZ_VERSION from the environment and refuse to build if
# the variable is not defined

try:
	version = os.environ['SEQUENZ_VERSION']
except:
	print "ERROR: environment variable $SEQUENZ_VERSION not defined"
	sys.exit()

if len( version ) == 0:
	print "ERROR: environment variable $SEQUENZ_VERSION empty"
	sys.exit()

print "Installing SEQUENZ version " + version
# For now, just copy into a top level directory called 'sequenz'

install_dir = os.environ.get("HOME") + '/sequenz'

# MODIFY THE SOURCE CODE BEFORE INSTALLING
# insert the version tag into banner in sequenz.py
command = """
	cd bin; 
	cat sequenz.py | sed -e 's/\(\s*sequenz_version =\).*/\\1 \"""" + version + """\";/' > tmp1 || exit 1;
	mv tmp1 sequenz.py || exit 1
	chmod +x sequenz.py || exit 1
	"""
if os.system( command ):
	print "Failed to insert sequenz version number into sequenz.py"
	sys.exit()

# INSTALL FILES
all = [ 'bin', 'doc', 'ecoconnect', 'example', 'src', 'taskdef',
    'README.install', 'README.dirs', 'README.run' ]
env = Environment()
i_a = env.Install( install_dir, all )

# define an alias so we can say 'scons install'
Alias( 'install', i_a )

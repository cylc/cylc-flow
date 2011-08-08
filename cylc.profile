#!/bin/bash

# CYLC USER LOGIN SCRIPT EXAMPLE. Copy the following to your .profile
# and adapt according to your preferences and local cylc installation.

# These environment variables are required for interactive cylc usage. 
# Access to cylc by running tasks is automatically configured by cylc.

#_______________________________________________________________________
# Add the cylc bin directory to $PATH. The 'cylc' and 'gcylc' commands
# configure access to cylc sub-commands and python modules at run time.
export PATH=/path/to/cylc/bin:$PATH

#_______________________________________________________________________
# For 'cylc edit' or gcylc -> Edit, set terminal and GUI editors:
export EDITOR=vim
export GEDITOR='gvim -f'
# (See 'cylc edit --help' for examples of other editors).

#_______________________________________________________________________
# To access the Cylc User Guide via the gcylc GUI menus:
export PDF_READER=evince
export HTML_READER=firefox
# (The HTML guide is opened via file path, not http URL).

#_______________________________________________________________________
# Some cylc commands require $TMPDIR to be set and writeable.
export TMPDIR=/path/to/my/temporary/directory

#_______________________________________________________________________
# For a local user install of Pyro, Graphviz, and Pygraphviz (if you
# can't easily get them installed at system level on the cylc host):
### PYTHONPATH=$HOME/external/installed/lib64/python2.6/site-packages:$PYTHONPATH
### PATH=$HOME/external/installed/bin:$PATH
# (See the Cylc User Guide "Installation" Section for instructions). 



Python temporary files:

# tempfile.NamedTemporaryFile( delete=False ) creates a file and opens
# it, but delete=False is post python 2.6 and we still currently run 2.4
# on some platforms!  (auto-delete on close() will remove file before
# the 'at' command runs it!)

# tempfile.mktemp() is deprecated in favour of mkstemp() but the latter
# was also introduced at python 2.6.

Sudo: run task as owner

# /etc/sudoers must be configured to allow the cylc operator to submit 
# jobs as the task owner, e.g. by allowing sudo access to 'at', qsub, or
# loadleveler. 

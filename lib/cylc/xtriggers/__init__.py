# Note that xtrigger modules can't store persistent information Pythonically
# (only via the filesystem) - because each call is via an independent process
# in the process pool.

# If an xtrigger function depends on suite-created directories, just return
# False until the directory exists.

# Xtrigger result names {'var1': val1, 'var2': val2} etc., are qualified with
# label names. E.g. for '@x1 => foo` result would be 'x1_var1' = val1 etc.

# Note auto debug arg.

# Out-of-order kafka trigger messages are not a problem because each trigger
# starts again from the beginning of the topic.

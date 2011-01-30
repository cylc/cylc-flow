# from pre-parallel batch processing housekeeping utility:

try:
    import subprocess
    use_subprocess = True
except:
    use_subprocess = False
    print "+++++++++++++++++++++++++++++++++++++++++++++++"
    print "WARNING: UNABLE TO IMPORT THE SUBPROCESS MODULE"
    pyver = sys.version_info
    if pyver < (2, 4):
        print "  (subprocess was introduced in Python 2.4)"
    print "=> the file differencing check functionality is"
    print "not available for housekeeping delete operation"
    print "+++++++++++++++++++++++++++++++++++++++++++++++"



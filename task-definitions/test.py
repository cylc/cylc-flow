#!/usr/bin/python

import string
import re

DEF = open( 'def/nzlam.def', 'r' )
lines = DEF.readlines()
DEF.close()

allowed_keys = [ 'TASK_NAME', 'VALID_REFERENCE_TIMES', 'EXTERNAL_TASK', 'EXPORT',
        'DELAYED_DEATH', 'USER_PREFIX', 'PREREQUISITES', 'POSTREQUISITES' ]


parsed_def = {}
for lline in lines:

    line = string.strip( lline )

    # skip blank lines
    if re.match( '^\s*$', line ):
        continue

    # skip comment lines
    if re.match( '^\s*#.*', line ):
        continue

    if re.match( '^%.*', line ):
        # new key identified
        current_key = string.lstrip( line, '%' )
        # print 'new key: ' + current_key,
        if current_key not in allowed_keys:
            print 'ILLEGAL KEY ERROR: ' + current_key
            sys.exit(1)
        parsed_def[ current_key ] = []

    else:
        if current_key == None:
            # can this ever happen?
            print "Error: no key identified"
            sys.exit(1)
    
        # data associated with current key
        parsed_def[ current_key ].append( line ) 


conditional_reqs = {}
unconditional_reqs = []
for line in parsed_def[ 'PREREQUISITES' ]:
    m = re.match( '^([\d,]+)\s*\|\s*(.*)$', line )
    if m:
        [ left, right ] = m.groups()
        if left in conditional_reqs.keys():
            conditional_reqs[ left ].append( right )
        else:
            conditional_reqs[ left ] = [ right ]

    else:
        unconditional_reqs.append( line )
           
for key in conditional_reqs.keys():
    print key + ':'
    for entry in conditional_reqs[key]:
        print '  ' + entry

print 'all: '
for entry in unconditional_reqs:
    print '  ' + entry



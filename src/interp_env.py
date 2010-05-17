#!/usr/bin/python

import os,re

def interp_local_str( strng ):
    # interpolate any local environment variables $FOO or ${FOO} in strng
    result = strng
    for var in re.findall( "\$\{{0,1}([a-zA-Z0-9_]+)\}{0,1}", strng ):
        if var in os.environ:
            result = re.sub( '\$\{{0,1}' + var + '\}{0,1}', os.environ[var], result )
    return result

def interp_local( env ):
    # interpolate any local environment variables $FOO or ${FOO} in
    # members of the env dict.
    intenv = {}
    for var in env:
        intenv[ var ] = interp_local_str( env[ var ] )
    return intenv
 
def interp_other_str( strng, other ):
    # interpolate any local environment variables $FOO or ${FOO} in strng
    result = strng
    for var in re.findall( "\$\{{0,1}([a-zA-Z0-9_]+)\}{0,1}", strng ):
        if var in other:
            result = re.sub( '\$\{{0,1}' + var + '\}{0,1}', other[var], result )
    return result

def replace_delayed_str( strng ):
    # replace '$[foo]' with '${foo}' (env vars to evaluate at execution time)
    return re.sub( "\$\[(?P<z>\w+)\]", "${\g<z>}", strng )

def replace_delayed( env ):
    new_env = {}
    for var in env:
        new_env[ var ] = replace_delayed_str( env[ var ] )
    return new_env

def interp_self( env ):
    #  env[ var_name ] = var_value
    
    # THIS FUNCTION USES EXCEPTION HANDLING IN CASE OF INFINITE
    # RECURSION DUE TO CIRCULAR VARIABLE DEFINITIONS (i.e. FOO=$BAR
    # and BAR=$FOO).

    intenv = {}
    for var in env:
        val = env[ var ]
        try:
            # recursively interpolate the value
            int_val = interp_recursive( val, env )
        except RuntimeError,x:
            print x
            print "CIRCULAR ENVIRONMENT DEFINITION involving " + var + "?"
            # leave uninterpolated and carry on
            intenv[ var ] = val
        else:
            # replace with recursively interpolated value
            intenv[ var ] = int_val

    return intenv

def interp_other( target, other ):
    # interpolate one environment dict into another
    new_target = {}
    for var in target:
        new_target[ var ] = interp_other_str( target[ var ], other )
    return new_target

def interp_recursive( val, env ):
    #  env[ var_name ] = var_value

    # interpolate potentially self-referencing environment variables
    # from the env dict, in val.

    # WARNING: USE EXCEPTION HANDLING WITH THIS FUNCTION, AS SHOWN ABOVE

    new_val = val
    for i_name in re.findall( "\$\{{0,1}([a-zA-Z0-9_]+)\}{0,1}", val ):
        if i_name in env:
            i_value = interp_recursive( env[ i_name ], env )
            new_val = re.sub( '\$\{{0,1}' + i_name + '\}{0,1}', i_value, new_val )
    return new_val

if __name__ == '__main__':
    # module test code

    # ENVIRONMENT VARIABLE INTERPOLATION
    print
    print interp_local_str( "I am $USER residing at${HOME}" )
    print interp_local_str( "This variable should be left alone: $UNKNOWN" ) 

    # SELF-INTERPOLATION
    testenv = {}
    testenv[ 'FOO' ] = '$HOME'  # not defined within testenv, will be left unchanged

    testenv[ 'BAR' ] = 'bar'    # multi-level self-referencing
    testenv[ 'BAZ' ] = '$BAR'
    testenv[ 'BAM' ] = '$BAZ'

    testenv[ 'WOO' ] = '$WAZ'   # circular reference
    testenv[ 'WAZ' ] = '$WOO'

    print
    intenv = interp_self( testenv )

    print
    for var in intenv:
        print var, intenv[ var ]
    print

    # CROSS REFERENCE
    glbl = {}
    local = {}

    glbl[ 'FOO' ] = 'foo'
    glbl[ 'BAR' ] = 'bar'

    local[ 'FOO' ] = '$FOO'
    local[ 'BAR' ] = 'local bar'

    local = interp_other( local, glbl )
    print
    print local[ 'FOO' ]
    print local[ 'BAR' ]
    print

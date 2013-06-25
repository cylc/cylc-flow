#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys, re
from cylc.config_list import get_expanded_float_list
from OrderedDict import OrderedDict
from cylc.dictcopy import m_override, override, un_many, replicate
from copy import copy

"""
Validate a nested dict parsed from a config file against a spec file:
    * check all items are legal
    * check all values are legal (type; min, max, allowed options)
    * coerce value type from string (to int, float, list, etc.)
Also provides default values from the spec as a nested dict.    
"""

class ValidationError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class IllegalValueError( ValidationError ):
    def __init__( self, vtype, keys, value ):
        msg = 'Illegal ' + vtype + ' value ' + \
                ': [' + ']['.join(keys) + '] = ' + str(value)
        ValidationError.__init__( self, msg )

def validate( cfig, spec, keys=[] ):
    """Validate and coerce a nested dict against a parsec spec."""
    for key,val in cfig.items():
        if key not in spec:
            if '__MANY__' not in spec:
                raise ValidationError('ERROR: illegal item: ' + key )
            else:
                speckey = '__MANY__'
        else:
            speckey = key
        if isinstance( val, dict ):
            validate( val, spec[speckey], keys+[key] )
        else:
            cfig[key] = spec[speckey].check( val, keys+[key] )

def override( target, source ):
    """Override values in nested dict target with those in source. Item
    keys do not have to exist in target already (so this will return a
    copy of source if target is emtpy)."""
    for key,val in source.items():
        if isinstance( val, dict ):
            if key not in target:
                target[key] = {}
            override( target[key], val )
        elif isinstance( val, list ):
            target[key] = copy(val)
        else:
            target[key] = val

def _populate_spec_defaults( defs, spec ):
    """Populate a nested dict with default values from a spec."""
    for key,val in spec.items():
        if isinstance( val, dict ):
            if key not in defs:
                if key in ['environment','directives']:
                    # TODO - IS THIS NECESSARY?
                    defs[key] = OrderedDict()
                else:
                    defs[key] = {}
            _populate_spec_defaults( defs[key], spec[key] )
        else:
            defs[key] = spec[key].args['default']

def get_defaults( spec ):
    """Return a nested dict of default values from a parsec spec."""
    defs = {}
    _populate_spec_defaults( defs, spec )
    return defs

def expand( sparse, spec ):
    # get dense defaults
    dense = get_defaults(spec)
    # override defaults with sparse values
    m_override( dense, sparse )
    un_many( dense )
    return dense

def _coerce_str( value, keys, args ):
    """Coerce value to a cleaned (stripped) string."""
    return str(value).strip()

def _coerce_int( value, keys, args ):
    """Coerce value to an integer."""
    try:
        return int( value )
    except ValueError:
        raise IllegalValueError( 'int', keys, value )

def _coerce_float( value, keys, args ):
    """Coerce value to a float."""
    try:
        return float( value )
    except ValueError:
        raise IllegalValueError( 'float', keys, value )

def _coerce_boolean( value, keys, args ):
    """Coerce value to a boolean."""
    if value == 'True':
        return True
    elif value == 'False':
        return False
    else:
        raise IllegalValueError( 'boolean', keys, value )

def _coerce_cycletime( value, keys, args ):
    """Coerce value to a cycle time."""
    # TODO - HANDLE PROPER CYCLE TIMES
    if re.match( '^[0-9]{10}$', value ):
        return int(value)
    else:
        raise IllegalValueError( 'cycle time', keys, value )

def _coerce_str_list( value, keys, args ):
    """Coerce value to a list of strings (comma-separated)."""
    lvalues = []
    for item in re.split( '\s*,\s*', value ):
        if item == '': # caused by a trailing comma
            continue
        lvalues.append( _coerce_str(item,keys,args))
    return lvalues

def _coerce_int_list( value, keys, args ):
    """Coerce value to a list of integers (comma-separated)."""
    lvalues = []
    for item in re.split( '\s*,\s*', value ):
        if item == '': # caused by a trailing comma
            continue
        lvalues.append( _coerce_int(item,keys,args))
    return lvalues

def _coerce_float_list( value, keys, args ):
    """Coerce value to a list of floats (comma-separated)"""
    lvalues = []
    for item in re.split( '\s*,\s*', value ):
        if item == '': # caused by a trailing comma
            continue
        lvalues.append( _coerce_float(item,keys, args))
    return lvalues

def _coerce_m_float_list( value, keys, args ):
    """Coerce value to a list of floats (comma-separated
    with optional multipliers e.g. suite 'retry delays')."""
    values = re.split( '\s*,\s*', value )
    if '' in values: # from trailing comma
        values.remove('')
    try:
        lvalues = get_expanded_float_list( values, args['allow zeroes'] )
    except:
        raise
        raise IllegalValueError( "float list", keys, value )
    else:
        if '' in lvalues: # from trailing comma
            lvalues.remove('')
        return lvalues

coercers = {
    'boolean'      : _coerce_boolean,
    'string'       : _coerce_str,
    'integer'      : _coerce_int,
    'float'        : _coerce_float,
    'cycletime'    : _coerce_cycletime,
    'string_list'  : _coerce_str_list,
    'integer_list' : _coerce_int_list,
    'float_list'   : _coerce_float_list,
    'm_float_list' : _coerce_m_float_list,
    }

class validator(object):
    """
    Validators for single values.
    """
    def __init__( self, vtype='string', default=None,
            options=[], vmin=None, vmax=None, allow_zeroes=False):
        self.coercer = coercers[vtype]
        self.args = {
                'options'      : options,
                'vmin'         : vmin,
                'vmax'         : vmax,
                'default'      : default,
                'allow zeroes' : allow_zeroes,
                }

    def check( self, value, keys ):
        value = self.coercer( value, keys, self.args )
        # handle option lists centrally here
        if self.args['options']:
            if value not in self.args['options']:
                raise IllegalValueError( 'option', keys, value )
        return value


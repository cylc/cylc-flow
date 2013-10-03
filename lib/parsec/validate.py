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
from OrderedDict import OrderedDict
from util import m_override, un_many
from copy import copy
from cylc.cycle_time import ct

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
        msg = 'Illegal value for ' + vtype + \
                ': [' + ']['.join(keys) + '] = ' + str(value)
        ValidationError.__init__( self, msg )

class IllegalItemError( ValidationError ):
    def __init__( self, keys, key ):
        msg = 'Illegal item: [' + ']['.join(keys) + ']' + key
        ValidationError.__init__( self, msg )

def validate( cfig, spec, keys=[] ):
    """Validate and coerce a nested dict against a parsec spec."""
    for key,val in cfig.items():
        if key not in spec:
            if '__MANY__' not in spec:
                raise IllegalItemError( keys, key )
            else:
                # only accept the item if it's value is of the same type
                # as that of the __MANY__  item, i.e. dict or not-dict.
                val_is_dict = isinstance( val, dict )
                spc_is_dict = isinstance( spec['__MANY__'], dict )
                if ( val_is_dict and spc_is_dict ) or \
                        ( not val_is_dict and not spc_is_dict ):
                    speckey = '__MANY__'
                else:
                    raise IllegalItemError( keys, key )
        else:
            speckey = key
        if isinstance( val, dict ):
            validate( val, spec[speckey], keys+[key] )
        elif val:
            # (if val is null we're only checking item validity)
            cfig[key] = spec[speckey].check( val, keys+[key] )

def _populate_spec_defaults( defs, spec ):
    """Populate a nested dict with default values from a spec."""
    for key,val in spec.items():
        if isinstance( val, dict ):
            if key not in defs:
                defs[key] = OrderedDict()
            _populate_spec_defaults( defs[key], spec[key] )
        else:
            defs[key] = spec[key].args['default']

def get_defaults( spec ):
    """Return a nested dict of default values from a parsec spec."""
    defs = OrderedDict()
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
    if value in ['True','true']:
        return True
    elif value in ['False','false']:
        return False
    else:
        raise IllegalValueError( 'boolean', keys, value )

def _coerce_cycletime( value, keys, args ):
    """Coerce value to a cycle time."""
    try:
        return ct( value ).get()
    except:
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
    """Coerce a list with optional multipliers to float values:
       ['1.0', '2*3.0', '4.0'] => [1.0, 3.0, 3.0, 4.0]""" 
    str_values = re.split( '\s*,\s*', value )
    if '' in str_values: # from trailing comma
        str_values.remove('')

    # expand the multiplier list
    lvalues = []
    for item in str_values:
        try:
            mult, val = item.split('*')
        except ValueError:
            # too few values to unpack: no multiplier
            try:
                lvalues.append(float(item))
            except ValueError:
                raise IllegalValueError( "float list", keys, value )
        else:
            # mult * val
            try:
                lvalues += int(mult) * [float(val)]
            except ValueError:
                raise IllegalValueError( "float list", keys, value )

    if not args['allow zeroes']:
        if 0.0 in lvalues:
            raise IllegalValueError( "float list with no zeroes", keys, value )

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
            options=[], vmin=None, vmax=None, allow_zeroes=True):
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


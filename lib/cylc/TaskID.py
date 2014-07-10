#!/usr/bin/env python

DELIM = '.'
DELIM_RE = '\.'

def get( name, tag ):
    return name + DELIM + tag

def split( id ):
    return id.split(DELIM)

def is_valid_name( name ):
    # TODO!
    return True

def is_valid_id( name ):
    # TODO!
    return DELIM in name


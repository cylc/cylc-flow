#!/usr/bin/env python

DELIM = '.'
DELIM_RE = '\.'

def get( name, point_string ):
    """Return a task id from name and a point string."""
    return name + DELIM + point_string

def split( id ):
    """Return a name and a point string from an id."""
    return id.split(DELIM)

def is_valid_name( name ):
    """Return whether a task name is valid."""
    # TODO!
    return True

def is_valid_id( name ):
    """Return whether a task id is valid."""
    # TODO!
    return DELIM in name

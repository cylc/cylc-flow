#!/usr/bin/env python
def pad( value, length, fillchar ):
    """A Jinja2 custom filter.
    Pad a string to some length with a fill character"""
    return str(value).rjust(int(length),str(fillchar))

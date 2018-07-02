#!/usr/bin/env python

def faker(name, debug=False):
    print "%s: failing" % name
    return (False, {"name": name})

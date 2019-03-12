#!/usr/bin/env python2

def faker(name, debug=False):
    print "%s: failing" % name
    return (False, {"name": name})

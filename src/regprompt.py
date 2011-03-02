#!/usr/bin/env python

def prompt( question, default ):
    def explain():
        print "Valid responses:"
        print "  [enter] - accept the default"
        print "  VALUE   - supply a new value"
        print "  q       - quit the operation"
        print "  s       - skip this item"
        print "  ?       - print this message"

    try_again = True
    while try_again:
        try_again = False
        res = raw_input( question + " (default '" + default + "', else VALUE,q,s,?) " )
        if res == '?':
            explain()
            try_again = True
        elif res == '':
            res = default
            break
        else:
            break
    return res
 

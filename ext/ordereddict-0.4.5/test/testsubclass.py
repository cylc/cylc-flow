
import sys

if len(sys.argv) > 1:
    from _ordereddict import sorteddict as SD
else:
    from _ordereddict import sorteddict
    class SD(sorteddict):
        def __init__(self, *argc, **kw):
            sorteddict.__init__(self, *argc, **kw)

s = SD({0: 'foo', 2: 'bar'})
print s
print repr(s)
print s.items()
s[1] = 'bla'
print s.items()

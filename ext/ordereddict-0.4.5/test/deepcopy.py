import sys
import copy
import gc
from _ordereddict import ordereddict

d = ordereddict([(1, 2)])
#d = dict([(1,2)])
nonerefcount = sys.getrefcount(None)
for i in xrange(1):
    print '>>> 1', nonerefcount, sys.getrefcount(None)
    copy.deepcopy(d)
    print '>>> a', nonerefcount, sys.getrefcount(None)
    gc.collect()
    print '>>> b', nonerefcount, sys.getrefcount(None)

print '>>>', nonerefcount, sys.getrefcount(None)

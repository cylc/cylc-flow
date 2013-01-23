
from distutils.core import setup, Extension

module1 = Extension('_ordereddict',
                    sources = ['ordereddict.c'],
                   )

setup (name = 'ordereddict',
       version = '0.4.5',
       description = 'a version of dict that keeps keys in insertion/sorted order',
       author = 'Anthon van der Neut',
       author_email = 'anthon@mnt.org',
       url = 'http://www.xs4all.nl/~anthon/ordereddict',
       long_description = """
A derivation of the pyton dictobject.c module that implements 
Key Insertion Order (KIO: the insertion order of 
new keys is being tracked, updating values of existing keys does not
change the order), Key Value Insertion Order (KVIO: KIO, but updates change
order), and Key Sorted Order (KSO: key are kept sorted).

The basic C structure is exented with a pointer to a list of item pointers.
When a *new* key is added, this list is extended with a pointer to the item.
The implementation compacts the list of pointers on every deletion (unless
the last added key is removed, such as in popitem()). That 
involves a memmove of all the pointers behind the pointer to the item in 
question.

The .keys, .values, .items, .iterkeys, itervalues, iteritems, __iter__
return things in the order of insertion.

.popitem takes an optional argument (defaulting to -1), which is the
order of the item.

the representation of the ordereddict is the same with Larosa/Foord: 
"ordereddict([(key1, val1), (key2, val2)])"

support for slices

And some more (see README).
 
""",
       ext_modules = [module1],
      )



#!/usr/bin/env python

# Ordered dictionary class implementation, taken from the public domain:
# http://stackoverflow.com/questions/60848/how-do-you-retrieve-items-from-a-dictionary-in-the-order-that-theyre-inserted
# Prepend method added by Hilary Oliver.

class ordered_dict(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self._order = self.keys()

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        if key in self._order:
            self._order.remove(key)
        self._order.append(key)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self._order.remove(key)

    def order(self):
        return self._order[:]

    def prepend( self, key, value ):
        dict.__setitem__(self, key, value)
        if key in self._order:
            self._order.remove(key)
        self._order.insert(0, key)

    def ordered_items(self):
        return [(key,self[key]) for key in self._order]

if __name__ == "__main__":
    od = ordered_dict()
    od["hello"] = "world"
    od["goodbye"] = "cruel world"
    print od.order()            # prints ['hello', 'goodbye']

    del od["hello"]
    od["monty"] = "python"
    print od.order()            # prints ['goodbye', 'monty']

    od["hello"] = "kitty"
    print od.order()            # prints ['goodbye', 'monty', 'hello']


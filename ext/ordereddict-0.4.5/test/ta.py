
import string

class basetimeall(object):
    def _create_26_entry(self):
        x = self.typ()
        for index, ch in enumerate(string.lowercase):
            x[ch] = index
        assert len(x) == 26
        return x

class timeall(basetimeall):
    def __init__(self, typ):
        self.typ = typ

    def time010_get_keys_from_26_entry(self):
        x = self._create_26_entry()
        y = x.keys()

    def time011_walk_keys(self):
        x = self._create_26_entry()
        for y in x.keys():
            pass

    def time012_walk_reverse_keys(self):
        x = self._create_26_entry()
        for y in reversed(x.keys()):
            pass

    def time013ordereddict_walk_keys_reverse(self):
        x = self._create_26_entry()
        for y in x.keys(reverse=True):
            pass


class timeall1(object):
    def __init__(self, typ):
        self.typ = typ

    def time000_empty(self):
        pass

    def time001_create_empty(self):
        x = self.typ()

    def time001_create_five_entry(self):
        x = self.typ()
        x['a'] = 1
        x['b'] = 2
        x['c'] = 3
        x['d'] = 4
        x['e'] = 5

    def time002_create_26_entry(self):
        x = self.typ()
        for index, ch in enumerate(string.lowercase):
            x[ch] = index
        assert len(x) == 26
        return x

    def time003_create_676_entry(self):
        x = self.typ()
        index = 0
        for ch1 in string.lowercase:
            for ch2 in string.lowercase:
                x[ch1 + ch2] = index
                index += 1
        assert len(x) == 676
        return x


    def _time004_create_17576_entry(self):
        # 17576 items
        x = self.typ()
        index = 0
        for ch1 in string.lowercase:
            for ch2 in string.lowercase:
                for ch3 in string.lowercase:
                    x[ch1 + ch2 + ch3] = index
                    index += 1
        assert len(x) == 17576
        return x

    def time010_get_keys_from_26_entry(self):
        x = self.time002_create_26_entry()
        y = x.keys()

    def time020_pop_5_items_26_entry(self):
        x = self.time002_create_26_entry()
        assert x.pop('f') == 5
        assert x.pop('k') == 10
        assert x.pop('p') == 15
        assert x.pop('u') == 20
        assert x.pop('z') == 25
        assert len(x) == 21

    def time021_pop_26_items_676_entry(self):
        x = self.time003_create_676_entry()
        for k in x.keys():
            if k[1] == 'q':
                i = x.pop(k)
                assert (i % 26) == 16
        assert len(x) == 650

    def time030_popitem_last_26_entry(self):
        x = self.time002_create_26_entry()
        x.popitem()
        assert len(x) == 25

    def time031_popitem_last_676_entry(self):
        x = self.time003_create_676_entry()
        x.popitem()
        assert len(x) == 675

    def time031nodict_popitem_100_676_entry(self):
        x = self.time003_create_676_entry()
        i = x.popitem(100)
        assert i[1] == 100
        assert len(x) == 675

    def time040nodict_walk_26_iteritems(self):
        x = self.time002_create_26_entry()
        index = 0
        for y in x.iteritems():
            assert y[0] == string.lowercase[index]
            assert y[1] == index
            index += 1

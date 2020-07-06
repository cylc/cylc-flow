BOTTLES = [99]


def drink():
    BOTTLES[0] -= 1
    return f'{BOTTLES[0]} bottles of beer on the wall.'

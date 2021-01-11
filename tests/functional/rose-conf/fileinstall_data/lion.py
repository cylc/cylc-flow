#!/usr/bin/env python3

class TerriblePunException(Exception):
    pass


def lion():
    raise TerriblePunException("This is a Lion's Main script")


if __name__ == "__main__":
    lion()

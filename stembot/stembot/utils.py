#!/usr/bin/python

from random import randrange

def sucky_uuid():
    hex_alpha_bet = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f"]

    uuid = ""
    
    for i in range(0, 8):
        uuid += hex_alpha_bet[randrange(0, 16, 1)]

    uuid += "-"

    for i in range(0, 4):
        uuid += hex_alpha_bet[randrange(0, 16, 1)]

    uuid += "-"

    for i in range(0, 4):
        uuid += hex_alpha_bet[randrange(0, 16, 1)]

    uuid += "-"

    for i in range(0, 4):
        uuid += hex_alpha_bet[randrange(0, 16, 1)]

    uuid += "-"

    for i in range(0, 12):
        uuid += hex_alpha_bet[randrange(0, 16, 1)]

    return uuid

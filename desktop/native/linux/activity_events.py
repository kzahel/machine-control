"""Kernel event classification only; never retain keys, positions or values."""
import re
import struct

EVENT = struct.Struct('@llHHi')
MAXIMUM_DEVICES = 64


def bitmap(text):
    words=text.split()
    if not words or len(words)>64 or any(not re.fullmatch('[0-9a-fA-F]{1,16}',word) for word in words):
        raise ValueError('invalid_input_capabilities')
    return sum(int(word,16) << (64*index) for index,word in enumerate(reversed(words)))


def deliberate(kind, code, value):
    if kind==1 and value in (1,2):
        # Ordinary keys and actual pointer/touch buttons. Tool-presence and
        # axes are movement facts, not a request to interrupt an agent.
        return 0<code<0x100 or 0x110<=code<=0x117 or code in (0x14a,0x14b,0x14c)
    return kind==2 and code in (6,8,11,12) and value!=0


def overflow(kind,code):
    return kind==0 and code==3  # SYN_DROPPED invalidates observation.


def relevant(keys, relative, absolute):
    keyboard=bool(keys & ((1<<28)|(1<<30)))
    pointer=bool((relative & 3 or absolute & 3) and keys & ((1<<0x110)|(1<<0x14a)))
    wheel=bool(relative & ((1<<6)|(1<<8)|(1<<11)|(1<<12)))
    return keyboard or pointer or wheel

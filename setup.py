import sys

from cx_Freeze import Executable
from cx_Freeze import setup

base = None
if sys.platform == 'win32':
    base = 'Win32GUI'

setup( 
    name = 'stembot',
    version = '0.1',
    description = 'stembot!',
    options = {},
    executables = [
        Executable('agcli', base=base),
        Executable('agcsc', base=base),
        Executable('agget', base=base),
        Executable('aglookup', base=base),
        Executable('agnet', base=base),
        Executable('agping', base=base),
        Executable('agput', base=base),
        Executable('agtest', base=base),
        Executable('config', base=base),
        Executable('kvs', base=base),
        Executable('server', base=base),
        Executable('tvs', base=base),
    ]
)

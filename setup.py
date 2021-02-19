from cx_Freeze import Executable
from cx_Freeze import setup

setup( 
    name = 'stembot',
    version = '0.1',
    description = 'stembot',
    packages=['stembot'],
    executables = [
        Executable('agcli'),
        Executable('agcsc'),
        Executable('agget'),
        Executable('aglookup'),
        Executable('agnet'),
        Executable('agping'),
        Executable('agput'),
        Executable('agtest'),
        Executable('config'),
        Executable('kvs'),
        Executable('server'),
        Executable('tvs')
    ]
)

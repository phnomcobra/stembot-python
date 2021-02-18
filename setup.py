from cx_Freeze import Executable
from cx_Freeze import setup

build_exe_options = {
    'packages': ['os', 'cherrypy', 'requests', 'sqlite3', 'Crypto']
}

setup( 
    name = 'stembot',
    version = '0.1',
    description = 'stembot',
    options = {'build_exe': build_exe_options},
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

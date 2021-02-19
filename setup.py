import sys

from cx_Freeze import Executable
from cx_Freeze import setup

options = {
    'bdist_msi': {
        'upgrade_code': '{9AF7F942-6106-4B29-A2AE-551C738648E2}',
        'add_to_path': True,
        'initial_target_dir': r'[ProgramFilesFolder]\Stembot'
    },
    'build_exe': {
        'include_msvcr': True
    }
}

setup( 
    name = 'stembot',
    version = '0.1',
    description = 'stembot',
    packages=['stembot'],
    options=options,
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

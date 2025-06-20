#!/usr/bin/python3
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

base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name = 'stembot',
    version = '0.1',
    description = 'stembot',
    packages=['stembot'],
    options=options,
    executables = [
        Executable('agnet'),
        Executable('config'),
        Executable('serverw', base=base),
        Executable('server')
    ]
)

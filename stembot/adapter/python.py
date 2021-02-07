import contextlib
import sys
import traceback

from io import StringIO

@contextlib.contextmanager
def stdoutIO(stdout=None):
    old = sys.stdout
    if stdout is None:
        stdout = StringIO()
    sys.stdout = stdout
    yield stdout
    sys.stdout = old

def interpret(code_str):
    stderr = None
    status = None
    
    with stdoutIO() as s:
        try:
            exec(code_str)
            stderr = ''
            status = 0
        except:
            stderr = str(traceback.format_exc())
            status = 1
    
    return status, s.getvalue(), stderr
    
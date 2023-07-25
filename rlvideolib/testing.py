import os
import sys
import tempfile

def doctest_absent(text, item):
    if item not in text:
        print("Yes")
    else:
        print(f"{item} found in text:")
        print(text)

def capture_stdout_stderr(fn, *args):
    sys.stdout.flush()
    sys.stderr.flush()
    FILENO_OUT = 1
    FILENO_ERR = 2
    old_stdout = os.dup(FILENO_OUT)
    old_stderr = os.dup(FILENO_ERR)
    try:
        with tempfile.TemporaryFile("w+") as f:
            os.dup2(f.fileno(), FILENO_OUT)
            os.dup2(f.fileno(), FILENO_ERR)
            return_value = fn(*args)
            f.seek(0)
            return (return_value, f.read())
    finally:
        os.dup2(old_stdout, FILENO_OUT)
        os.dup2(old_stderr, FILENO_ERR)

import contextlib
import os
import sys
import tempfile

@contextlib.contextmanager
def capture_stdout_stderr():
    FILENO_OUT = 1
    FILENO_ERR = 2
    old_stdout = os.dup(FILENO_OUT)
    old_stderr = os.dup(FILENO_ERR)
    try:
        with tempfile.TemporaryFile("w+") as f:
            os.dup2(f.fileno(), FILENO_OUT)
            os.dup2(f.fileno(), FILENO_ERR)
            result = CaptureResult()
            yield result
            f.seek(0)
            result.value = f.read()
    finally:
        os.dup2(old_stdout, FILENO_OUT)
        os.dup2(old_stderr, FILENO_ERR)

class CaptureResult:

    def __init__(self):
        self.value = ""

    def is_absent(self, item):
        doctest_absent(self.value, item)

def doctest_absent(text, item):
    if item not in text:
        print("Yes")
    else:
        print(f"{item} found in text:")
        print(text)

def doctest_equal(a, b):
    if a == b:
        print("Yes")
    else:
        print("Items not equal:")
        print("")
        print(a)
        print("")
        print(b)

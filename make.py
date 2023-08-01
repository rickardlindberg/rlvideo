#!/usr/bin/env python3

import doctest
import importlib
import subprocess
import sys
import unittest

def usage():
    return [
        "Usage:",
        "",
        "    ./make.py build",
        "    ./make.py rundev",
        "    ./make.py gdb",
        "    ./make.py commit",
    ]

def ensure(command):
    process = subprocess.run(command)
    if process.returncode != 0:
        sys.exit(process.returncode)

if __name__ == "__main__":
    command = sys.argv[1:]
    if command == ["build"]:
        ensure(["ctags", "--python-kinds=-i", "-R", "."])
        suite = unittest.TestSuite()
        for module in [
            "rlvideo",
            "rlvideolib",
            "rlvideolib.asciicanvas",
            "rlvideolib.debug",
            "rlvideolib.events",
            "rlvideolib.domain",
            "rlvideolib.domain.region",
            "rlvideolib.domain.source",
            "rlvideolib.domain.cut",
            "rlvideolib.domain.section",
            "rlvideolib.domain.project",
            "rlvideolib.domain.clip",
            "rlvideolib.graphics",
            "rlvideolib.graphics.rectangle",
            "rlvideolib.testing",
            "rlvideolib.jobs",
            "rlvideolib.gui",
            "rlvideolib.gui.generic",
            "rlvideolib.gui.gtk",
            "rlvideolib.gui.framework",
        ]:
            suite.addTest(doctest.DocTestSuite(
                importlib.import_module(module),
                optionflags=doctest.REPORT_NDIFF|doctest.FAIL_FAST
            ))
        if not unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful():
            sys.exit(1)
    elif command[0:1] == ["rundev"]:
        ensure([sys.executable, "rlvideo.py"]+command[1:])
    elif command[0:1] == ["gdb"]:
        ensure(["gdb", sys.executable, "--ex", f"run rlvideo.py {' '.join(command[1:])}"])
    elif command[0:1] == ["commit"]:
        ensure([sys.executable, "make.py", "build"])
        ensure(["bash", "-c", "if git status | grep -A 5 'Untracked files:'; then exit 1; fi"])
        ensure(["git", "commit", "-a", "--verbose"]+command[1:])
    else:
        sys.exit("\n".join(usage()))

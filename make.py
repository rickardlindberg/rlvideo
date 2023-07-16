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
    ]

if __name__ == "__main__":
    command = sys.argv[1:]
    if command == ["build"]:
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
            "rlvideolib.graphics",
            "rlvideolib.graphics.rectangle",
        ]:
            suite.addTest(doctest.DocTestSuite(
                importlib.import_module(module),
                optionflags=doctest.REPORT_NDIFF|doctest.FAIL_FAST
            ))
        if not unittest.TextTestRunner().run(suite).wasSuccessful():
            sys.exit(1)
    elif command[0:1] == ["rundev"]:
        sys.exit(subprocess.run([sys.executable, "rlvideo.py"]+command[1:]).returncode)
    else:
        sys.exit("\n".join(usage()))

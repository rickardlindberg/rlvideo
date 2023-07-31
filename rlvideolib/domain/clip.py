import subprocess

class Clip:

    def __init__(self, path):
        self.path = path

    def md5(self):
        return subprocess.check_output(["md5sum", self.path])[:32].decode("ascii")

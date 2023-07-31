import subprocess

import mlt

class Clip:

    def __init__(self, path):
        self.path = path

    def md5(self):
        return subprocess.check_output(["md5sum", self.path])[:32].decode("ascii")

    def get_number_of_frames(self, profile):
        return mlt.Producer(profile, self.path).get_playtime()

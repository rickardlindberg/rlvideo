import subprocess

import mlt

class Clip:

    def __init__(self, path):
        self.path = path

    def md5(self):
        return subprocess.check_output(["md5sum", self.path])[:32].decode("ascii")

    def calculate_length_at_fps(self, mlt_profile):
        return mlt.Producer(mlt_profile, self.path).get_playtime()

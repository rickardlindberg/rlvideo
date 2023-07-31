import time

import mlt

class FileInfo:

    def __init__(self, path):
        self.path = path

    def get_number_of_frames(self, profile):
        return mlt.Producer(profile, self.path).get_playtime()

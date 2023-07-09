from collections import namedtuple
import os

import mlt

from rlvideolib.domain.cut import Cut
from rlvideolib.domain.region import Region

# TODO: add some kind of container for source files (caching, background
# loading)

cache = {}

class Source(namedtuple("Source", "name")):

    def create_cut(self, start, end):
        # TODO: ensure cut is valid
        return Cut(
            source=self,
            in_out=Region(start=start, end=end),
            position=0
        )

    def to_mlt_producer(self, profile):
        if self.name not in cache or cache[self.name][0] is not profile:
            if os.path.exists(self.name):
                producer = mlt.Producer(profile, self.name)
            else:
                producer = mlt.Producer(profile, "pango")
                producer.set("text", self.name)
                producer.set("bgcolour", "red")
            cache[self.name] = (profile, producer)
        return cache[self.name][1]

    def starts_at(self, position):
        return True

    def ends_at(self, position):
        return True

    def get_label(self):
        return os.path.basename(self.name)

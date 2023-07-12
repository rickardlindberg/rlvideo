from collections import namedtuple
import os

import mlt

from rlvideolib.domain.cut import Cut
from rlvideolib.domain.region import Region

# TODO: add some kind of container for source files (caching, background
# loading)

class Source(namedtuple("Source", "name")):

    def create_cut(self, start, end):
        # TODO: ensure cut is valid
        return Cut(
            source=self,
            in_out=Region(start=start, end=end),
            position=0,
            id=None
        ).with_unique_id()

    def to_mlt_producer(self, profile, cache):
        if cache.get(self.name) is None:
            if os.path.exists(self.name):
                producer = mlt.Producer(profile, self.name)
            else:
                producer = mlt.Producer(profile, "pango")
                producer.set("text", self.name)
                producer.set("bgcolour", "red")
            cache.set(self.name, producer)
        return cache.get(self.name)

    def starts_at(self, position):
        return True

    def ends_at(self, position):
        return True

    def get_label(self):
        return os.path.basename(self.name)

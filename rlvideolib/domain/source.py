from collections import namedtuple
from rlvideolib.domain.cut import Cut
from rlvideolib.domain.region import Region
import mlt
import os

class Source(namedtuple("Source", "name")):

    def create_cut(self, start, end):
        # TODO: ensure cut is valid
        return Cut(
            source=self,
            in_out=Region(start=start, end=end),
            position=0
        )

    def to_mlt_producer(self, profile):
        if os.path.exists(self.name):
            return mlt.Producer(profile, self.name)
        else:
            producer = mlt.Producer(profile, "pango")
            producer.set("text", self.name)
            producer.set("bgcolour", "red")
            return producer

    def starts_at(self, position):
        return True

    def ends_at(self, position):
        return True

    def get_label(self):
        return os.path.basename(self.name)


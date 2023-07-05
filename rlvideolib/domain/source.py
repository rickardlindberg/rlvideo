from collections import namedtuple
from rlvideolib.domain.region import Region
import mlt
import os
import rlvideo

class Source(namedtuple("Source", "name")):

    def create_cut(self, start, end):
        # TODO: ensure cut is valid
        return rlvideo.Cut.create(
            source=self,
            in_out=Region(start=start, end=end)
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


from collections import namedtuple
import os

import mlt

from rlvideolib.domain.cut import Cut
from rlvideolib.domain.region import Region

# TODO: add some kind of container for source files (caching, background
# loading)

class FileSource(namedtuple("FileSource", "id,path")):

    def create_cut(self, start, end):
        # TODO: ensure cut is valid
        return Cut(
            source=self,
            in_out=Region(start=start, end=end),
            position=0,
            id=None
        ).with_unique_id()

    def to_mlt_producer(self, profile, cache):
        def create():
            producer = mlt.Producer(profile, self.path)
            return producer
        return cache.get_or_create(self.path, create)

    def starts_at(self, position):
        return True

    def ends_at(self, position):
        return True

    def get_label(self):
        return os.path.basename(self.path)

class TextSource(namedtuple("TextSource", "id,text")):

    def create_cut(self, start, end):
        return Cut(
            source=self,
            in_out=Region(start=start, end=end),
            position=0,
            id=None
        ).with_unique_id()

    def to_mlt_producer(self, profile, cache):
        producer = mlt.Producer(profile, "pango")
        producer.set("text", self.text)
        producer.set("bgcolour", "red")

    def starts_at(self, position):
        return True

    def ends_at(self, position):
        return True

    def get_label(self):
        return self.text

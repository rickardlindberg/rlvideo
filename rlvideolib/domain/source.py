from collections import namedtuple
import os
import uuid

import mlt

from rlvideolib.domain.cut import Cut
from rlvideolib.domain.cut import CutSource
from rlvideolib.domain.region import Region

class FileSource(namedtuple("FileSource", "id,path,length")):

    def with_unique_id(self):
        return self._replace(id=uuid.uuid4().hex)

    def create_cut(self, start, end):
        if start < 0 or end > self.length:
            raise ValueError("Invalid cut.")
        return Cut(
            source=CutSource(source_id=self.id),
            in_out=Region(start=start, end=end),
            position=0,
            id=None
        ).with_unique_id()

    def load_proxy(self, profile):
        producer = mlt.Producer(profile, self.path)
        return producer

    def get_label(self):
        return os.path.basename(self.path)

class TextSource(namedtuple("TextSource", "id,text")):

    def with_unique_id(self):
        return self._replace(id=uuid.uuid4().hex)

    def create_cut(self, start, end):
        return Cut(
            source=CutSource(source_id=self.id),
            in_out=Region(start=start, end=end),
            position=0,
            id=None
        ).with_unique_id()

    def load_proxy(self, profile):
        producer = mlt.Producer(profile, "pango")
        producer.set("text", self.text)
        producer.set("bgcolour", "red")

    def get_label(self):
        return self.text

class Sources(namedtuple("Sources", "id_to_source")):

    @staticmethod
    def empty():
        return Sources({})

    def add(self, source):
        if source.id in self.id_to_source:
            raise ValueError(f"Source with id {source.id} already exists.")
        new = dict(self.id_to_source)
        new[source.id] = source
        return self._replace(id_to_source=new)

    def get(self, id):
        return self.id_to_source[id]

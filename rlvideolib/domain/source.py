from collections import namedtuple
import os
import subprocess
import tempfile
import uuid

import mlt

from rlvideolib.domain.clip import Clip
from rlvideolib.domain.cut import Cut
from rlvideolib.domain.cut import CutSource
from rlvideolib.domain.region import Region
from rlvideolib.testing import capture_stdout_stderr

class FileSource(namedtuple("FileSource", "id,path,length")):

    @staticmethod
    def from_json(id, json):
        return FileSource(
            id=id,
            path=json["path"],
            length=json["length"],
        )

    def to_json(self):
        return {
            "type": "file",
            "path": self.path,
            "length": self.length,
        }

    def with_unique_id(self):
        return self._replace(id=uuid.uuid4().hex)

    def create_cut(self, start, end):
        if start < 0 or end > self.length:
            raise ValueError("Invalid cut.")
        return Cut.new(
            source=CutSource(source_id=self.id),
            in_out=Region(start=start, end=end),
        ).with_unique_id()

    def load(self, profile):
        return self.create_producer(profile, self.path)

    def load_proxy(self, profile, proxy_spec, progress):
        """
        >>> _ = mlt.Factory().init()
        >>> tmp = tempfile.TemporaryDirectory()
        >>> profile = mlt.Profile()
        >>> source = FileSource(id=None, path="resources/one.mp4", length=15)
        >>> from rlvideolib.domain.project import ProxySpec
        >>> with capture_stdout_stderr():
        ...     producer = source.load_proxy(
        ...         profile=profile,
        ...         proxy_spec=ProxySpec(dir=tmp.name),
        ...         progress=lambda progress: None,
        ...     )
        >>> isinstance(producer, mlt.Producer)
        True
        """
        return self.create_producer(
            profile,
            Clip(self.path).generate_proxy(proxy_spec, progress)
        )

    def create_producer(self, profile, path):
        producer = mlt.Producer(profile, path)
        # TODO: Why do proxies sometimes get a longer playtime?
        if producer.get_playtime() < self.length:
            raise ValueError(f"Producer {path} (original {self.path}) has a playtime of {producer.get_playtime()}, but length is {self.length}")
        return producer

    def get_label(self):
        return os.path.basename(self.path)

    def limit_in_out(self, cut):
        """
        >>> source = FileSource(id="source_a", path="a.mp4", length=5)

        >>> source.limit_in_out(Cut.test_instance(start=0, end=10)).in_out
        Region(start=0, end=5)

        >>> source.limit_in_out(Cut.test_instance(start=0, end=20, speed=0.5)).in_out
        Region(start=0, end=10)
        """
        return cut.limit_out(int(self.length/cut.speed))

class TextSource(namedtuple("TextSource", "id,text")):

    @staticmethod
    def from_json(id, json):
        return TextSource(
            id=id,
            text=json["text"],
        )

    def to_json(self):
        return {
            "type": "text",
            "text": self.text,
        }

    def with_unique_id(self):
        return self._replace(id=uuid.uuid4().hex)

    def create_cut(self, start, end):
        return Cut.new(
            source=CutSource(source_id=self.id),
            in_out=Region(start=start, end=end),
        ).with_unique_id()

    def load(self, profile):
        producer = mlt.Producer(profile, "pango")
        producer.set("text", self.text)
        producer.set("bgcolour", "red")
        return producer

    def load_proxy(self, profile, proxy_spec, progress):
        return self.load(profile)

    def get_label(self):
        return self.text

    def limit_in_out(self, cut):
        return cut

# TODO: add image sequence source

class Source:

    @staticmethod
    def from_json(id, json):
        if json["type"] == "text":
            return TextSource.from_json(id, json)
        elif json["type"] == "file":
            return FileSource.from_json(id, json)
        else:
            raise ValueError("unknown source type")

class Sources(namedtuple("Sources", "id_to_source")):

    @staticmethod
    def empty():
        return Sources({})

    @staticmethod
    def from_json(json):
        sources = Sources.empty()
        for id, json in json.items():
            sources = sources.add(Source.from_json(id, json))
        return sources

    def to_json(self):
        json = {}
        for key, value in self.id_to_source.items():
            json[key] = value.to_json()
        return json

    def get_ids(self):
        return list(self.id_to_source.keys())

    def add(self, source):
        if source.id in self.id_to_source:
            raise ValueError(f"Source with id {source.id} already exists.")
        new = dict(self.id_to_source)
        new[source.id] = source
        return self._replace(id_to_source=new)

    def get(self, id):
        return self.id_to_source[id]

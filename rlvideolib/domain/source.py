from collections import namedtuple
import os
import subprocess
import uuid

import mlt

from rlvideolib.domain.cut import Cut
from rlvideolib.domain.cut import CutSource
from rlvideolib.domain.region import Region
from rlvideolib.mlthelpers import FileInfo
from rlvideolib.mlthelpers import run_consumer
from rlvideolib.testing import capture_stdout_stderr

class FileSource(namedtuple("FileSource", "id,path,number_of_frames_at_project_fps")):

    # NOTE: The number_of_frames_at_project_fps depends on the FPS of the
    # project. Once the first FileSource is added to the project, the FPS of
    # the project can not be changed.

    @staticmethod
    def from_json(id, json):
        return FileSource(
            id=id,
            path=json["path"],
            number_of_frames_at_project_fps=json["number_of_frames_at_project_fps"],
        )

    def to_json(self):
        return {
            "type": "file",
            "path": self.path,
            "number_of_frames_at_project_fps": self.number_of_frames_at_project_fps,
        }

    def with_unique_id(self):
        return self._replace(id=uuid.uuid4().hex)

    def create_cut(self, start, end):
        if start < 0 or end > self.number_of_frames_at_project_fps:
            raise ValueError("Invalid cut.")
        return Cut.new(
            source=CutSource(source_id=self.id),
            in_out=Region(start=start, end=end),
        ).with_unique_id()

    def load(self, profile):
        return self.validate_producer(mlt.Producer(profile, self.path))

    def load_proxy(self, profile, proxy_profile, progress, testing=False):
        """
        >>> _ = mlt.Factory().init()
        >>> profile = mlt.Profile()
        >>> proxy_profile = mlt.Profile()
        >>> source = FileSource(id=None, path="resources/one.mp4", number_of_frames_at_project_fps=15)
        >>> with capture_stdout_stderr():
        ...     producer = source.load_proxy(
        ...         profile=profile,
        ...         proxy_profile=proxy_profile,
        ...         progress=lambda progress: None,
        ...         testing=True
        ...     )
        >>> isinstance(producer, mlt.Producer)
        True
        """
        producer = self.validate_producer(mlt.Producer(profile, self.path))
        chechsum = md5(self.path)
        proxy_path = f"/tmp/{chechsum}.mkv"
        proxy_tmp_path = f"/tmp/{chechsum}.tmp.mkv"
        if not os.path.exists(proxy_path) or testing:
            p = mlt.Profile()
            p.from_producer(producer)
            p.set_width(proxy_profile.width())
            p.set_height(proxy_profile.height())
            producer = mlt.Producer(p, self.path)
            consumer = mlt.Consumer(p, "avformat")
            consumer.set("target", proxy_tmp_path)
            consumer.set("vcodec", "mjpeg")
            consumer.set("acodec", "pcm_s16le")
            consumer.set("qscale", "3")
            run_consumer(consumer, producer, progress)
            os.rename(proxy_tmp_path, proxy_path)
        return self.validate_producer(mlt.Producer(profile, proxy_path))

    def validate_producer(self, producer):
        assert producer.get_playtime() == self.number_of_frames_at_project_fps
        return producer

    def get_label(self):
        return os.path.basename(self.path)

def md5(path):
    return subprocess.check_output(["md5sum", path])[:32].decode("ascii")

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

    def load_proxy(self, profile, proxy_profile, progress):
        return self.load(profile)

    def get_label(self):
        return self.text

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

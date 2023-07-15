from collections import namedtuple
import os
import subprocess
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
        """
        >>> _ = mlt.Factory().init()
        >>> profile = mlt.Profile()
        >>> source = FileSource(id=None, path="resources/one.mp4", length=15)
        >>> producer = source.load_proxy(profile)
        >>> isinstance(producer, mlt.Producer)
        True
        """
        assert self.length == mlt.Producer(profile, self.path).get_playtime()
        chechsum = md5(self.path)
        proxy_path = f"/tmp/{chechsum}.mp4"
        proxy_tmp_path = f"/tmp/{chechsum}.tmp.mp4"
        if not os.path.exists(proxy_path):
            # TODO: produce proxy with MLT (idea from Flowblade)
            subprocess.check_call([
                "ffmpeg",
                "-y", # Overwrite output files without asking.
                "-i", self.path,
                "-vf", "yadif,scale=960:540",
                "-qscale", "3",
                "-vcodec", "mjpeg",
                proxy_tmp_path
            ], stderr=subprocess.PIPE)
            os.rename(proxy_tmp_path, proxy_path)
        producer = mlt.Producer(profile, proxy_path)
        # TODO: does it make sense that proxies can get a different playtime?
        assert self.length <= producer.get_playtime() # proxy got larger in one case
        return producer

    def get_label(self):
        return os.path.basename(self.path)

def md5(path):
    return subprocess.check_output(["md5sum", path])[:32].decode("ascii")

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

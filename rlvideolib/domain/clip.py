import os
import subprocess

import mlt

class Clip:

    def __init__(self, path):
        self.path = path

    def md5(self):
        return subprocess.check_output(["md5sum", self.path])[:32].decode("ascii")

    def calculate_length_at_fps(self, mlt_profile):
        return mlt.Producer(mlt_profile, self.path).get_playtime()

    def generate_proxy(self, proxy_spec, progress):
        # TODO: call progress
        checksum = self.md5()
        proxy_path = proxy_spec.get_path(checksum)
        proxy_tmp_path = proxy_spec.get_tmp_path(checksum)
        if not os.path.exists(proxy_path):
            proxy_spec.ensure_dir()
            subprocess.check_call(
                [
                    "ffmpeg",
                    "-y",
                    "-i", self.path,
                ]
                +
                proxy_spec.get_ffmpeg_arguments()
                +
                [
                    proxy_tmp_path
                ]
            )
            os.rename(proxy_tmp_path, proxy_path)
        return proxy_path

class ProxySpec:

    @staticmethod
    def from_path(path):
        """
        >>> ProxySpec.from_path(None).dir
        '/tmp'

        >>> ProxySpec.from_path("a/file.rlvideo").dir
        'a/.cache'
        """
        if path is None:
            return ProxySpec()
        else:
            return ProxySpec(dir=os.path.join(os.path.dirname(path), ".cache"))

    def __init__(self, dir="/tmp"):
        self.extension = "mkv"
        self.height = 540
        self.vcodec = "mjpeg"
        self.acodec = "pcm_s16le"
        self.qscale = "3"
        self.dir = dir

    def adjust_profile(self, profile):
        ratio = profile.width() / profile.height()
        profile.set_width(int(self.height*ratio))
        profile.set_height(self.height)
        return profile

    def get_ffmpeg_arguments(self):
        return [
            "-vf", f"yadif,scale=-1:{self.height}",
            "-q:v", self.qscale,
            "-vcodec", self.vcodec,
            "-acodec", self.acodec,
        ]

    def get_tmp_path(self, name):
        """
        >>> ProxySpec().get_tmp_path("hello")
        '/tmp/hello.tmp.mkv'
        """
        return self.get_path(f"{name}.tmp")

    def get_path(self, name):
        return os.path.join(self.dir, f"{name}.{self.extension}")

    def ensure_dir(self):
        if not os.path.exists(self.dir):
            os.mkdir(self.dir)

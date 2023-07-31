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
            subprocess.check_call([
                "ffmpeg",
                "-y",
                "-i", self.path,
                "-vf", "yadif,scale=960:540",
                "-q:v", "3",
                "-vcodec", "mjpeg",
                "-acodec", "pcm_s16le",
                proxy_tmp_path
            ])
            os.rename(proxy_tmp_path, proxy_path)
        return proxy_path

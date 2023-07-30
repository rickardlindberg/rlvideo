import time

import mlt

class FileInfo:

    def __init__(self, path):
        self.path = path

    def get_number_of_frames(self, profile):
        return self.get_mlt_producer(profile).get_playtime()

    def get_mlt_producer(self, profile):
        return mlt.Producer(profile, self.path)

def run_consumer(consumer, producer, progress):
    consumer.connect(producer)
    consumer.start()
    while consumer.is_stopped() == 0:
        progress(producer.position()/producer.get_playtime())
        time.sleep(0.5)


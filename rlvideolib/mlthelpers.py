import time

import mlt

class FileInfo:

    def __init__(self, path):
        self.path = path

    def get_number_of_frames(self, profile):
        return mlt.Producer(profile, self.path).get_playtime()

def run_consumer(consumer, producer, progress):
    consumer.connect(producer)
    consumer.start()
    while consumer.is_stopped() == 0:
        progress(producer.position()/producer.get_playtime())
        time.sleep(0.5)


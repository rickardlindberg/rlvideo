import mlt

class LoadingProducer(mlt.Producer):

    def __init__(self, profile):
        mlt.Producer.__init__(self, profile, "pango")
        self.set("text", "Loading...")
        self.set("bgcolour", "red")

    def cut(self, in_, out):
        # An mlt.Producer has a default maximum length of 15000.
        max_out = max(out, int(self.get("out")))
        self.set("in", "0")
        self.set("out", max_out)
        self.set("length", max_out+1)
        return mlt.Producer.cut(self, in_, out)

def TimewarpProducer(profile, producer, speed):
    if speed != 1 and not isinstance(producer, LoadingProducer):
        old_path = producer.get('resource')
        producer = MltInconsistencyError.create_producer(profile, f"timewarp:{speed}:{old_path}")
    return producer

class MltInconsistencyError(Exception):

    @staticmethod
    def create_producer(profile, arg):
        producer = mlt.Producer(profile, arg)
        if not producer.is_valid():
            raise MltInconsistencyError(
                f"Invalid producer: {arg!r}."
            )
        return producer

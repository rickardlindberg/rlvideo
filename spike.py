import mlt
import time

CLIP1 = "/home/rick/downloads/VID_20230611_115932.mp4"
CLIP2 = "/home/rick/downloads/VID_20230611_120041.mp4"

def hello1():
    mlt.Factory().init()

    profile = mlt.Profile()

    producer = mlt.Producer(profile, CLIP1)

    consumer = mlt.Consumer(profile, "sdl")

    consumer.set("rescale", "none")
    consumer.connect(producer)
    consumer.start()

    while consumer.is_stopped() == 0:
        time.sleep(1)

def hello2():
    mlt.Factory().init()
    profile = mlt.Profile()
    playlist = mlt.Playlist()
    playlist.append(mlt.Producer(profile, CLIP2))
    playlist.append(mlt.Producer(profile, CLIP1))
    consumer = mlt.Consumer(profile, "sdl")
    consumer.set("rescale", "none")
    consumer.connect(playlist)
    consumer.start()
    while consumer.is_stopped() == 0:
        time.sleep(1)

def hello3():
    mlt.Factory().init()
    profile = mlt.Profile()
    grey = mlt.Filter(profile, "greyscale")
    playlist = mlt.Playlist()
    first = mlt.Producer(profile, CLIP2)
    first.attach(grey)
    playlist.append(first, 0, 100)
    playlist.append(mlt.Producer(profile, CLIP1), 0, 100)
    consumer = mlt.Consumer(profile, "sdl")
    consumer.set("rescale", "none")
    consumer.connect(playlist)
    consumer.start()
    while consumer.is_stopped() == 0:
        time.sleep(1)

def hello4():
    # mix / tractor
    mlt.Factory().init()
    profile = mlt.Profile()
    grey = mlt.Filter(profile, "greyscale")
    playlist = mlt.Playlist()
    first = mlt.Producer(profile, CLIP2)
    first.attach(grey)
    playlist.append(first, 0, 100)
    playlist.append(mlt.Producer(profile, CLIP1), 0, 100)
    playlist.mix(0, 50, mlt.Transition(profile, "luma"))
    consumer = mlt.Consumer(profile, "sdl")
    consumer.set("rescale", "none")
    consumer.connect(playlist)
    consumer.start()
    while consumer.is_stopped() == 0:
        time.sleep(1)

def hello5():
    # clip properties
    mlt.Factory().init()
    profile = mlt.Profile()
    clip = mlt.Producer(profile, CLIP2)
    print(profile.description())
    print(clip.get_fps())
    clip.debug()

def hello6():
    mlt.Factory().init()
    profile = mlt.Profile()
    producer = mlt.Producer(profile, CLIP1)
    consumer = mlt.Consumer(profile, "sdl")
    consumer.set("resolution", "300x300")
    consumer.set("rescale", "bicubic")
    consumer.set("resize", "0")
    consumer.set("real_time", "1")
    consumer.connect(producer)
    consumer.start()
    while consumer.is_stopped() == 0:
        time.sleep(1)

if __name__ == "__main__":
    hello4()
    print("OK")

import mlt

from rlvideolib.asciicanvas import AsciiCanvas
from rlvideolib.debug import timeit
from rlvideolib.domain.region import Region
from rlvideolib.graphics.rectangle import Rectangle

class Sections:

    def __init__(self):
        self.sections = []

    @property
    def length(self):
        return sum(section.length for section in self.sections)

    def add(self, *sections):
        self.sections.extend(sections)

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        if self.sections:
            offset = 1
            lines = [0]
            for section in self.sections:
                canvas.add_canvas(section.to_ascii_canvas(), dx=offset)
                lines.append(canvas.get_max_x()+1)
                offset += 1
                offset += section.length
            for line in lines:
                for y in range(canvas.get_max_y()+1):
                    canvas.add_text("|", line, y)
        return canvas

    def to_mlt_producer(self, profile, cache):
        playlist = mlt.Playlist(profile)
        for section in self.sections:
            playlist.append(section.to_mlt_producer(profile, cache))
        assert playlist.get_playtime() == self.length
        return playlist

    def to_cut_boxes(self, region, rectangle):
        boxes = {}
        self.collect_cut_boxes(region, boxes, rectangle, 0)
        return boxes

    def collect_cut_boxes(self, region, boxes, rectangle, pos):
        for section, section_rectangle in rectangle.divide_width(
            self.sections,
            lambda section: section.length
        ):
            if pos >= region.end:
                return
            elif pos + section.length > region.start:
                section.collect_cut_boxes(region, boxes, section_rectangle, pos)
            pos += section.length

class PlaylistSection:

    def __init__(self, length, parts):
        assert length == sum(part.length for part in parts)
        self.length = length
        self.parts = parts

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        x = 0
        for part in self.parts:
            canvas.add_canvas(part.to_ascii_canvas(), dx=x)
            x = canvas.get_max_x() + 1
        return canvas

    def to_mlt_producer(self, profile, cache):
        playlist = mlt.Playlist(profile)
        for part in self.parts:
            part.add_to_mlt_playlist(profile, cache, playlist)
        if playlist.get_playtime() != self.length:
            parts_string = "- "+"\n- ".join(str(x) for x in self.parts)
            raise MltInconsistencyError(
                f"The playlist length={playlist.get_playtime()} "
                f"does not match the PlaylistSection length={self.length}."
                f"\n\n{parts_string}"
            )
        return playlist

    def collect_cut_boxes(self, region, boxes, rectangle, pos):
        for part, part_rectangle in rectangle.divide_width(
            self.parts,
            lambda part: part.length
        ):
            if pos >= region.end:
                return
            elif pos + part.length > region.start:
                part.collect_cut_boxes(region, boxes, part_rectangle, pos)
            pos += part.length

class MltInconsistencyError(Exception):
    pass

class MixSection:

    def __init__(self, length, playlists):
        for playlist in playlists:
            assert playlist.length == length
        self.length = length
        self.playlists = playlists

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        for y, playlist in enumerate(self.playlists):
            canvas.add_canvas(playlist.to_ascii_canvas(), dy=y)
        return canvas

    def to_mlt_producer(self, profile, cache):
        """
        How do transitions work?

        From https://sourceforge.net/p/mlt/mailman/message/35244309/:

        > a transition merges the b_track onto the a_track

        So the b_track "disappears".

        Example:

        |-a-------| index=2
        |-b-------| index=1
        |-c-------| index=0

        transition(a=0, b=1) ->

        |-a-------| index=2
        |         | index=1
        |-bc------| index=0

        transition(a=0, b=2) ->

        |         | index=2
        |         | index=1
        |-abc-----| index=0

        The only track left now is that with index 0.
        """
        tractor = mlt.Tractor(profile)
        for playlist in self.playlists:
            tractor.insert_track(
                playlist.to_mlt_producer(profile, cache),
                0
            )
        for index in range(len(self.playlists)):
            if index > 0:
                a_track = 0
                b_track = index
                # 'qtblend' that was first used first seems to give problems
                # when used in a GTK context. The application segfaults when
                # started.
                #
                # Steps to reproduce:
                #
                # 1. ./make.py rundev foo.rlvideo resources/*mp4
                #
                # 2. Move a cut so that there is a overlap somewhere
                #
                # 3. ./make.py rundev foo.rlvideo
                #
                # Boom! Stacktrace:
                #
                #     (gdb) bt
                #     #0  0x00007ffff7a64474 in pthread_mutex_lock () at /lib64/libpthread.so.0
                #     #1  0x00007fffe96866af in XrmQGetResource () at /lib64/libX11.so.6
                #     #2  0x00007fffe9667fca in XGetDefault () at /lib64/libX11.so.6
                #     #3  0x00007fffe9a5ae8a in _cairo_xlib_surface_get_font_options () at /lib64/libcairo.so.2
                #     ...
                #
                # frei0r.cairoblend seems to work better.
                #
                # TODO: How to fix this problem? Is qtblend just incompatible?
                mix_video = mlt.Transition(profile, "frei0r.cairoblend")
                tractor.plant_transition(mix_video, a_track, b_track)
                mix_audio = mlt.Transition(profile, "mix")
                mix_audio.set("sum", "1")
                tractor.plant_transition(mix_audio, a_track, b_track)
        assert tractor.get_playtime() == self.length
        return tractor

    def collect_cut_boxes(self, region, boxes, rectangle, pos):
        for playlist, playlist_rectangle in rectangle.divide_height(
            self.playlists,
            lambda playlist: playlist.length
        ):
            playlist.collect_cut_boxes(region, boxes, playlist_rectangle, pos)

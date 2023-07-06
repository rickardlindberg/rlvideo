import mlt

from rlvideolib.asciicanvas import AsciiCanvas

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

    def to_mlt_producer(self, profile):
        playlist = mlt.Playlist()
        for section in self.sections:
            playlist.append(section.to_mlt_producer(profile))
        return playlist

    def draw_cairo(self, context, height, x_factor, rectangle_map, x_offset):
        for section in self.sections:
            section.draw_cairo(
                context=context,
                height=height,
                x_factor=x_factor,
                rectangle_map=rectangle_map,
                x_offset=x_offset
            )

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

    def to_mlt_producer(self, profile):
        playlist = mlt.Playlist()
        for part in self.parts:
            part.add_to_mlt_playlist(profile, playlist)
        assert playlist.get_playtime() == self.length
        return playlist

    def draw_cairo(self, context, height, x_factor, rectangle_map, x_offset):
        for part in self.parts:
            part.draw_cairo(context, height, x_factor, rectangle_map, x_offset)

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

    def to_mlt_producer(self, profile):
        tractor = mlt.Tractor()
        for playlist in self.playlists:
            tractor.insert_track(
                playlist.to_mlt_producer(profile),
                0
            )
        assert tractor.get_playtime() == self.length
        return tractor

    def draw_cairo(self, context, height, x_factor, rectangle_map, x_offset):
        sub_height = height // len(self.playlists)
        rest = height % len(self.playlists)
        context.save()
        for index, playlist in enumerate(self.playlists):
            if rest:
                rest -= 1
                h = sub_height + 1
            else:
                h = sub_height
            playlist.draw_cairo(context, h, x_factor, rectangle_map, x_offset)
            context.translate(0, h)
        context.restore()

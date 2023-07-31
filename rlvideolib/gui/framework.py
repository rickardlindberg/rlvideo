from collections import namedtuple

class MenuItem(namedtuple("MenuItem", "label,action")):
    pass

class Action:

    def left_mouse_down(self, x, y):
        pass

    def right_mouse_down(self, x, y, gui):
        pass

    def mouse_move(self, x, y):
        pass

    def mouse_up(self):
        pass

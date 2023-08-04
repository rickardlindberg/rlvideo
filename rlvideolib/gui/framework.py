from collections import namedtuple

class MenuItem(namedtuple("MenuItem", "label,action")):
    pass

NO_ACTION = object()

class Action:

    def left_mouse_down(self, x, y):
        return NO_ACTION

    def right_mouse_down(self, gui):
        return NO_ACTION

    def mouse_move(self, x, y):
        return NO_ACTION

    def mouse_up(self):
        return NO_ACTION

    def simulate_click(self, x=0, y=0):
        self.left_mouse_down(x=x, y=y)

class TestGui:

    def __init__(self, click_context_menu=None):
        self.click_context_menu = click_context_menu

    def show_context_menu(self, menu):
        self.last_context_menu = menu
        for item in menu:
            if item.label == self.click_context_menu:
                item.action()
                return

    def print_context_menu_items(self):
        for item in self.last_context_menu:
            print(item.label)

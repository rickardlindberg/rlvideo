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

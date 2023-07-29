class TestGui:

    def __init__(self, click_context_menu=None):
        self.click_context_menu = click_context_menu

    def show_context_menu(self, menu):
        for item in menu:
            if item.label == self.click_context_menu:
                item.action()
                return

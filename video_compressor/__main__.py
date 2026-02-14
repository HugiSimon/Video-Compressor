import sys

from video_compressor.utils import setup_logging
from video_compressor.view.main_window import MainView
from video_compressor.controller.app_controller import AppController


def main() -> None:
    setup_logging()

    initial_input = None
    if len(sys.argv) >= 2:
        initial_input = sys.argv[1]

    view = MainView(initial_input)
    AppController(view)

    if view.winfo_exists():
        view.mainloop()


if __name__ == "__main__":
    main()

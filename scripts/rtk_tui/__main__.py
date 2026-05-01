"""Entry point: ``python -m rtk_tui``."""

from rtk_tui.app import RtkApp


def main() -> None:
    RtkApp().run()


if __name__ == "__main__":
    main()

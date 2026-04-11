def main(argv=None):
    from .app import main as app_main

    return app_main(argv)


__all__ = ["main"]

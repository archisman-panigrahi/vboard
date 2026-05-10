def main(argv=None):
    from .environment import configure_gdk_backend

    configure_gdk_backend()
    from .app import main as app_main

    return app_main(argv)


__all__ = ["main"]

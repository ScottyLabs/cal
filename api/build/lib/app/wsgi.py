"""Gunicorn entrypoint for the kennel-deployed API service.

Replaces the Dockerfile CMD that Railway used. Kennel allocates a port and
injects it as PORT, then routes the public domain to it through Caddy, so the
port is read at startup rather than hardcoded.
"""

import os

from gunicorn.app.base import BaseApplication

from app import create_app


class StandaloneApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.application = app
        self.options = options or {}
        super().__init__()

    def load_config(self):
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


def main():
    port = os.getenv("PORT", "8080")

    options = {
        "bind": f"0.0.0.0:{port}",
        "workers": int(os.getenv("WEB_CONCURRENCY", "2")),
        "threads": int(os.getenv("GTHREADS", "4")),
        "timeout": int(os.getenv("TIMEOUT", "120")),
        "accesslog": "-",
        "errorlog": "-",
    }

    StandaloneApplication(create_app(), options).run()


if __name__ == "__main__":
    main()

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Local development only. Kennel runs app/wsgi.py under gunicorn and never
    # reaches this branch; binding 0.0.0.0 here is so the dev server is
    # reachable from a container or another device on the LAN.
    app.run(  # nosemgrep: python.flask.security.audit.app-run-param-config.avoid_app_run_with_bad_host
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        debug=app.config.get("DEBUG", False),
    )

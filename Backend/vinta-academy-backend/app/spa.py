"""
Vinta School OS — Single-page app static serving (portable test builds only).

In production the frontend is deployed separately (Vercel) and this module is
never used: `register_spa` is only called when the ``VINTA_WEB_DIR`` environment
variable points at a built frontend. That keeps the hosted deployment's routing
completely unchanged.

For the offline review build the frontend and the API are served from one
origin on 127.0.0.1. That is not just convenience — the frontend ships a strict
Content-Security-Policy in index.html:

    default-src 'self'; connect-src 'self'

so an API on a *different* origin would be blocked by the browser before CORS
was ever consulted. Same-origin serving is what makes the packaged build work
without relaxing that policy.

Routing notes:
  * The API blueprints register concrete rules such as ``/api/students``.
    Werkzeug ranks those above the ``/<path:path>`` catch-all, so API traffic
    keeps reaching the API. The explicit prefix guard below is belt-and-braces:
    without it an unknown path like ``/api/typo`` would fall through to the
    catch-all and be answered with index.html and a 200, which turns a plain
    404 into a confusing "HTML where JSON was expected" error in the client.
  * The frontend uses createBrowserRouter, so deep links such as
    ``/app/dashboard`` are resolved client-side. Any non-file path therefore has
    to return index.html rather than a 404.
"""
import os

from flask import abort, send_from_directory


def register_spa(app, web_dir):
    """
    Serve a built frontend from ``web_dir``, with history-API fallback.

    Raises RuntimeError if the directory does not look like a built frontend, so
    a misconfigured build fails loudly at startup instead of serving 404s.
    """
    web_dir = os.path.abspath(web_dir)
    index_path = os.path.join(web_dir, "index.html")
    if not os.path.isfile(index_path):
        raise RuntimeError(
            f"VINTA_WEB_DIR={web_dir!r} does not contain an index.html. "
            "Build the frontend before packaging, or unset VINTA_WEB_DIR."
        )

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def _serve_spa(path):
        # Never let the catch-all answer for the API or the Socket.IO channel.
        # Falling through here means the route genuinely does not exist, and the
        # app's JSON 404 handler should produce that answer.
        if path.startswith("api/") or path.startswith("socket.io/"):
            abort(404)

        if path:
            # Reject traversal before touching the filesystem: only paths that
            # stay inside web_dir are considered assets.
            candidate = os.path.abspath(os.path.join(web_dir, path))
            if candidate.startswith(web_dir + os.sep) and os.path.isfile(candidate):
                return _send_asset(web_dir, path)

        # History-API fallback. The shell must not be cached, otherwise a
        # tester who refreshes after an update keeps being served the old
        # index.html (and therefore the old asset hashes).
        response = send_from_directory(web_dir, "index.html")
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response

    def _send_asset(directory, relative):
        response = send_from_directory(directory, relative)
        # Vite writes content-hashed filenames, so an asset's contents can never
        # change under a given name: cache it hard. index.html is handled above.
        if relative.startswith("assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    app.logger.info("Serving frontend from %s", web_dir)
    return web_dir

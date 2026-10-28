"""HTTP-only WSGI application; importing this module never starts a scheduler."""

from app.server import create_app

app = create_app()

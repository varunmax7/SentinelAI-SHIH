"""Role gating.

Principle C4 - secure by default: if the twin cannot establish who the caller
is, it refuses rather than serving officials' operational data.

The twin adopts the host's `login_required` when one is handed to it at
registration time, and falls back to its own Flask-Login check otherwise. Roles
live in `config.TWIN_ROLES` / `TWIN_ADMIN_ROLES` - add a role there, never to an
individual route.
"""

from functools import wraps

from flask import jsonify, request
from flask_login import current_user

from . import config as twin_config

_HOST_LOGIN_REQUIRED = None


def adopt_login_required(decorator):
    """Use the host application's own auth decorator, if it provides one."""
    global _HOST_LOGIN_REQUIRED
    _HOST_LOGIN_REQUIRED = decorator


def _authenticated():
    try:
        return bool(current_user and current_user.is_authenticated)
    except Exception:  # noqa: BLE001 - no request context / no login manager
        return False


def _role_of(user):
    return (getattr(user, 'role', None) or '').lower()


def _wants_json():
    if request.path.startswith('/api/'):
        return True
    return 'application/json' in (request.headers.get('Accept') or '')


def _deny(status, message):
    if _wants_json():
        return jsonify({'error': message, 'status': status}), status
    return message, status


def twin_access_required(admin=False):
    """Gate a route on authentication plus twin role membership."""
    allowed = twin_config.TWIN_ADMIN_ROLES if admin else twin_config.TWIN_ROLES

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not _authenticated():
                return _deny(401, 'Authentication required')
            if getattr(current_user, 'is_admin', False):
                return view(*args, **kwargs)
            if _role_of(current_user) not in allowed:
                return _deny(403, 'This view requires one of: %s' % ', '.join(allowed))
            return view(*args, **kwargs)

        if _HOST_LOGIN_REQUIRED is not None:
            # The host's decorator runs outermost so unauthenticated browser
            # traffic gets its normal redirect to the login page.
            return _HOST_LOGIN_REQUIRED(wrapper)
        return wrapper

    return decorator

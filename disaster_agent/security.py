"""Role gating, identical contract to twin/security.py.

Kept as a separate copy rather than importing the twin's version so this
package stays independently portable - dropping `disaster_agent/` into an
app that does not have `twin/` must still work.
"""

from functools import wraps

from flask import jsonify, request
from flask_login import current_user

from . import config as agent_config

_HOST_LOGIN_REQUIRED = None


def adopt_login_required(decorator):
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


def agent_access_required():
    """Gate a route on authentication plus one of `config.AGENT_ROLES`."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not _authenticated():
                return _deny(401, 'Authentication required')
            if getattr(current_user, 'is_admin', False):
                return view(*args, **kwargs)
            if _role_of(current_user) not in agent_config.AGENT_ROLES:
                return _deny(403, 'This view requires one of: %s'
                            % ', '.join(agent_config.AGENT_ROLES))
            return view(*args, **kwargs)

        if _HOST_LOGIN_REQUIRED is not None:
            return _HOST_LOGIN_REQUIRED(wrapper)
        return wrapper

    return decorator

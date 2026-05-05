from functools import wraps
from flask import session, redirect, url_for, flash, g, abort, request


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录后再使用系统', 'error')
            return redirect(url_for('auth.login', next=request.path))
        user = g.get('current_user')
        if user and user.get('must_change_password') and request.endpoint != 'auth.change_password':
            flash('请先修改初始密码', 'warning')
            return redirect(url_for('auth.change_password'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录后再使用系统', 'error')
            return redirect(url_for('auth.login'))
        user = g.get('current_user')
        if not user or not user.get('is_admin'):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

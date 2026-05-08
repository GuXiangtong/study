from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.user import verify_user, get_user_by_id, update_password
from models.settings import fix_user_model_settings
from utils.decorators import login_required

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('auth/login.html')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        flash('请输入用户名和密码', 'error')
        return render_template('auth/login.html')

    user = verify_user(username, password)
    if user:
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']

        # Fix model settings if admin disabled a model the user had selected
        fix_user_model_settings(user['id'])

        if user.get('must_change_password'):
            flash('首次登录，请修改初始密码', 'warning')
            return redirect(url_for('auth.change_password'))
        flash(f'欢迎回来，{user["username"]}！', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('index'))

    flash('用户名或密码错误', 'error')
    return render_template('auth/login.html')


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    user_id = session['user_id']
    user = get_user_by_id(user_id)
    is_forced = bool(user and user.get('must_change_password'))

    if request.method == 'GET':
        return render_template('auth/change_password.html', is_forced=is_forced)

    from models.user import verify_user as _verify
    from models.user import get_user_by_username
    current_user_row = get_user_by_username(user['username'])

    old_password = request.form.get('old_password', '')
    new_password = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')

    from werkzeug.security import check_password_hash
    if not check_password_hash(current_user_row['password_hash'], old_password):
        flash('当前密码不正确', 'error')
        return render_template('auth/change_password.html', is_forced=is_forced)
    if len(new_password) < 6:
        flash('新密码至少需要 6 个字符', 'error')
        return render_template('auth/change_password.html', is_forced=is_forced)
    if new_password != confirm:
        flash('两次输入的新密码不一致', 'error')
        return render_template('auth/change_password.html', is_forced=is_forced)

    update_password(user_id, new_password, must_change=False)
    flash('密码修改成功', 'success')
    return redirect(url_for('index'))


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'success')
    return redirect(url_for('auth.login'))

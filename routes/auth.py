from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.user import create_user, verify_user

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
        flash(f'欢迎回来，{user["username"]}！', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('index'))

    flash('用户名或密码错误', 'error')
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('auth/register.html')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    confirm = request.form.get('confirm_password', '')

    if not username or not password:
        flash('请填写所有字段', 'error')
        return render_template('auth/register.html')
    if len(username) < 2:
        flash('用户名至少需要 2 个字符', 'error')
        return render_template('auth/register.html')
    if len(password) < 6:
        flash('密码至少需要 6 个字符', 'error')
        return render_template('auth/register.html')
    if password != confirm:
        flash('两次输入的密码不一致', 'error')
        return render_template('auth/register.html')

    user_id = create_user(username, password)
    if user_id is None:
        flash('用户名已存在，请选择其他用户名', 'error')
        return render_template('auth/register.html')

    flash('注册成功，请登录', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'success')
    return redirect(url_for('auth.login'))

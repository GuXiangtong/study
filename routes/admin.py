from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.user import list_all_users, create_user, delete_user, update_password, count_admins, get_user_by_id
from models.settings import (RECOGNITION_METHODS, ANALYSIS_METHODS,
                             get_enabled_recognition_methods, set_enabled_recognition_methods,
                             get_enabled_analysis_methods, set_enabled_analysis_methods)
from utils.decorators import admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/users')
@admin_required
def users():
    all_users = list_all_users()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/create', methods=['POST'])
@admin_required
def create_user_route():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    if not username or not password:
        flash('用户名和密码不能为空', 'error')
        return redirect(url_for('admin.users'))
    if len(username) < 2:
        flash('用户名至少需要 2 个字符', 'error')
        return redirect(url_for('admin.users'))
    if len(password) < 6:
        flash('密码至少需要 6 个字符', 'error')
        return redirect(url_for('admin.users'))

    user_id = create_user(username, password, is_admin=0, must_change_password=1)
    if user_id is None:
        flash(f'用户名「{username}」已存在', 'error')
    else:
        flash(f'用户「{username}」创建成功，初次登录需修改密码', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_password(user_id):
    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 6:
        flash('新密码至少需要 6 个字符', 'error')
        return redirect(url_for('admin.users'))

    target = get_user_by_id(user_id)
    if not target:
        flash('用户不存在', 'error')
        return redirect(url_for('admin.users'))

    update_password(user_id, new_password, must_change=True)
    flash(f'用户「{target["username"]}」密码已重置，下次登录需修改密码', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user_route(user_id):
    current_user_id = session['user_id']

    if user_id == current_user_id:
        flash('不能删除自己的账号', 'error')
        return redirect(url_for('admin.users'))

    target = get_user_by_id(user_id)
    if not target:
        flash('用户不存在', 'error')
        return redirect(url_for('admin.users'))

    if target.get('is_admin') and count_admins() <= 1:
        flash('不能删除最后一个管理员账号', 'error')
        return redirect(url_for('admin.users'))

    delete_user(user_id)
    flash(f'用户「{target["username"]}」及其所有数据已删除', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/models', methods=['GET', 'POST'])
@admin_required
def models_config():
    """管理员配置哪些大模型可供用户选择。"""
    if request.method == 'POST':
        # Get checked recognition methods from form
        recognition_keys = request.form.getlist('recognition_methods')
        analysis_keys = request.form.getlist('analysis_methods')

        set_enabled_recognition_methods(recognition_keys)
        set_enabled_analysis_methods(analysis_keys)

        flash('模型配置已保存', 'success')
        return redirect(url_for('admin.models_config'))

    enabled_recognition = get_enabled_recognition_methods()
    enabled_analysis = get_enabled_analysis_methods()

    return render_template('admin/models.html',
                           recognition_methods=RECOGNITION_METHODS,
                           analysis_methods=ANALYSIS_METHODS,
                           enabled_recognition=enabled_recognition,
                           enabled_analysis=enabled_analysis)
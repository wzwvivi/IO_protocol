# -*- coding: utf-8 -*-
"""
接口代码生成平台 - Flask Web 应用
用户通过网页表单填写协议变量部分，自动生成 Python 解析脚本
"""

import os
import json
import sys
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response, session, redirect, url_for, flash
from io import BytesIO
import zipfile

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generator_core import generate_parser_code, generate_c_parser_code, validate_config
from models import (
    login_required, admin_required, operator_required, viewer_required,
    get_current_user, is_logged_in, is_admin, is_operator, can_edit,
    authenticate_user, create_user, list_users, get_user, update_user,
    change_password, reset_password, delete_user, ensure_user_db
)
from device_manager import (
    import_device_tree_from_directory, find_device_node, get_all_devices,
    migrate_legacy_config, update_device_version, get_device_labels_for_generation,
    compute_labels_diff, save_device_tree_to_db, get_device_tree_from_db
)
from database import (
    init_database, db_get_labels, db_save_labels, db_get_device, db_create_device,
    db_delete_device, db_save_user_config, db_get_user_config, migrate_from_json
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'arinc429-generator-secret-key-2024'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # session 有效期 24 小时

# 存储目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 用户配置保存目录
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# 当前工作配置文件路径
CURRENT_CONFIG_PATH = os.path.join(DATA_DIR, 'current_config.json')

# 数据协议目录路径（用于导入设备树）
# Docker 环境下挂载到 /app/数据协议，本地环境在上级目录
_local_protocol_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '数据协议')
_docker_protocol_dir = '/app/数据协议'
# 优先检查本地目录，再检查 Docker 目录
if os.path.exists(_local_protocol_dir):
    DATA_PROTOCOL_DIR = _local_protocol_dir
elif os.path.exists(_docker_protocol_dir):
    DATA_PROTOCOL_DIR = _docker_protocol_dir
else:
    DATA_PROTOCOL_DIR = _local_protocol_dir  # 默认使用本地路径（即使不存在）

print(f'数据协议目录: {DATA_PROTOCOL_DIR} (存在: {os.path.exists(DATA_PROTOCOL_DIR)})')

# 初始化数据库
init_database()
ensure_user_db()

# 自动迁移旧数据（如果存在）
_old_users_json = os.path.join(DATA_DIR, 'users.json')
_old_users_bak = os.path.join(DATA_DIR, 'users.json.bak')
_db_path = os.path.join(DATA_DIR, 'arinc429.db')

# 如果数据库不存在但有旧配置文件，执行迁移
if not os.path.exists(_db_path):
    # 检查是否有需要迁移的数据
    _has_old_data = os.path.exists(_old_users_json) or os.path.exists(_old_users_bak)
    _has_config = any(f.startswith('current_config_') and f.endswith('.json') 
                      for f in os.listdir(DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f)))
    
    if _has_old_data or _has_config:
        print('检测到旧数据，正在迁移到 SQLite...')
        # 如果 users.json.bak 存在但 users.json 不存在，恢复它用于迁移
        if os.path.exists(_old_users_bak) and not os.path.exists(_old_users_json):
            import shutil
            shutil.copy(_old_users_bak, _old_users_json)
        migrate_from_json()
        # 备份旧文件
        if os.path.exists(_old_users_json):
            os.rename(_old_users_json, _old_users_json + '.bak')
        print('旧数据已迁移并备份')


# ============================================================
# 用户认证路由
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录页面"""
    if is_logged_in():
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        success, result = authenticate_user(username, password)
        
        if success:
            # 登录成功，保存用户信息到 session
            session.permanent = True
            session['user'] = {
                'username': result['username'],
                'display_name': result['display_name'],
                'role': result['role'],
                'email': result.get('email', '')
            }
            flash(f'欢迎回来，{result["display_name"]}！', 'success')
            
            # 重定向到原来要访问的页面
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash(result, 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """用户登出"""
    session.clear()
    flash('已安全退出', 'info')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册页面"""
    if is_logged_in():
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        display_name = request.form.get('display_name', '').strip()
        email = request.form.get('email', '').strip()
        
        # 验证密码确认
        if password != confirm_password:
            flash('两次输入的密码不一致', 'error')
            return render_template('register.html')
        
        success, message = create_user(username, password, display_name, email)
        
        if success:
            flash('注册成功，请登录', 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'error')
    
    return render_template('register.html')


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """用户个人资料页面"""
    user = get_current_user()
    user_data = get_user(user['username'])
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_profile':
            display_name = request.form.get('display_name', '').strip()
            email = request.form.get('email', '').strip()
            
            success, message = update_user(user['username'], 
                                          display_name=display_name, 
                                          email=email)
            if success:
                # 更新 session 中的信息
                session['user']['display_name'] = display_name
                session['user']['email'] = email
                flash('个人资料已更新', 'success')
            else:
                flash(message, 'error')
        
        elif action == 'change_password':
            old_password = request.form.get('old_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_new_password', '')
            
            if new_password != confirm_password:
                flash('两次输入的新密码不一致', 'error')
            else:
                success, message = change_password(user['username'], old_password, new_password)
                if success:
                    flash('密码修改成功', 'success')
                else:
                    flash(message, 'error')
        
        return redirect(url_for('profile'))
    
    return render_template('profile.html', user=user_data)


# ============================================================
# 用户管理 API (管理员)
# ============================================================

@app.route('/admin/users')
@admin_required
def admin_users():
    """用户管理页面"""
    users = list_users()
    return render_template('admin_users.html', users=users)


@app.route('/api/admin/users', methods=['GET'])
@admin_required
def api_list_users():
    """获取所有用户列表"""
    users = list_users()
    return jsonify({'success': True, 'users': users})


@app.route('/api/admin/users', methods=['POST'])
@admin_required
def api_create_user():
    """创建新用户"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    display_name = data.get('display_name', '').strip()
    email = data.get('email', '').strip()
    role = data.get('role', 'user')
    
    success, message = create_user(username, password, display_name, email, role)
    
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'error': message}), 400


@app.route('/api/admin/users/<username>', methods=['PUT'])
@admin_required
def api_update_user(username):
    """更新用户信息"""
    data = request.get_json()
    
    # 过滤允许更新的字段
    update_data = {}
    if 'display_name' in data:
        update_data['display_name'] = data['display_name']
    if 'email' in data:
        update_data['email'] = data['email']
    if 'role' in data:
        update_data['role'] = data['role']
    if 'is_active' in data:
        update_data['is_active'] = data['is_active']
    
    success, message = update_user(username, **update_data)
    
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'error': message}), 400


@app.route('/api/admin/users/<username>/reset_password', methods=['POST'])
@admin_required
def api_reset_user_password(username):
    """重置用户密码"""
    data = request.get_json()
    new_password = data.get('new_password', '')
    
    success, message = reset_password(username, new_password)
    
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'error': message}), 400


@app.route('/api/admin/users/<username>', methods=['DELETE'])
@admin_required
def api_delete_user(username):
    """删除用户"""
    # 不能删除自己
    current_user = get_current_user()
    if current_user['username'] == username:
        return jsonify({'success': False, 'error': '不能删除自己的账户'}), 400
    
    success, message = delete_user(username)
    
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'error': message}), 400


# ============================================================
# 主要功能路由 (需要登录)
# ============================================================

@app.route('/')
@login_required
def index():
    """主页 - 协议配置表单"""
    return render_template('index.html', user=get_current_user())


@app.route('/api/validate', methods=['POST'])
@login_required
def api_validate():
    """验证协议配置"""
    try:
        config = request.get_json()
        errors = validate_config(config)
        if errors:
            return jsonify({'valid': False, 'errors': errors})
        return jsonify({'valid': True, 'message': '配置验证通过'})
    except Exception as e:
        return jsonify({'valid': False, 'errors': [str(e)]})


@app.route('/api/generate', methods=['POST'])
@login_required
def api_generate():
    """生成解析代码"""
    try:
        config = request.get_json()
        
        # 验证配置
        errors = validate_config(config)
        if errors:
            return jsonify({'success': False, 'errors': errors}), 400
        
        # 生成代码
        code = generate_parser_code(config)
        
        # 生成文件名
        protocol_name = config.get('protocol_meta', {}).get('name', 'protocol')
        safe_name = ''.join(c for c in protocol_name if c.isalnum() or c in '_ -').strip()
        if not safe_name:
            safe_name = 'protocol'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 添加用户名到文件名
        username = get_current_user()['username']
        filename = f'{safe_name}_parser_{timestamp}_{username}.py'
        
        # 保存到输出目录
        output_path = os.path.join(OUTPUT_DIR, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # 同时保存配置文件
        config_filename = f'{safe_name}_config_{timestamp}_{username}.json'
        config_path = os.path.join(OUTPUT_DIR, config_filename)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': '代码生成成功',
            'filename': filename,
            'config_filename': config_filename,
            'code_preview': code[:2000] + '...' if len(code) > 2000 else code
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False, 
            'errors': [str(e)],
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/download/<filename>')
@login_required
def api_download(filename):
    """下载生成的文件"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': '文件不存在'}), 404


@app.route('/api/download_zip', methods=['POST'])
@login_required
def api_download_zip():
    """打包下载所有生成的文件"""
    try:
        data = request.get_json()
        filenames = data.get('filenames', [])
        
        # 创建 ZIP 文件
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 添加运行时模块
            runtime_path = os.path.join(os.path.dirname(__file__), 'arinc429_runtime.py')
            if os.path.exists(runtime_path):
                zf.write(runtime_path, 'arinc429_runtime.py')
            
            # 添加用户生成的文件
            for filename in filenames:
                filepath = os.path.join(OUTPUT_DIR, filename)
                if os.path.exists(filepath):
                    zf.write(filepath, filename)
        
        memory_file.seek(0)
        return Response(
            memory_file.getvalue(),
            mimetype='application/zip',
            headers={'Content-Disposition': 'attachment; filename=arinc429_parser_package.zip'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/load_example')
@login_required
def api_load_example():
    """加载示例配置"""
    example_path = os.path.join(os.path.dirname(__file__), 'example_protocol_config.json')
    if os.path.exists(example_path):
        with open(example_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return jsonify(config)
    return jsonify({'error': '示例文件不存在'}), 404


@app.route('/api/save_config', methods=['POST'])
@login_required
def api_save_config():
    """保存当前配置到服务器（持久化）"""
    try:
        config = request.get_json()
        username = get_current_user()['username']
        
        # 每个用户有自己的配置文件
        user_config_path = os.path.join(DATA_DIR, f'current_config_{username}.json')
        
        with open(user_config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': '配置已保存',
            'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/load_config')
@login_required
def api_load_config():
    """加载上次保存的配置"""
    username = get_current_user()['username']
    user_config_path = os.path.join(DATA_DIR, f'current_config_{username}.json')
    
    if os.path.exists(user_config_path):
        try:
            with open(user_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return jsonify({
                'success': True,
                'config': config,
                'message': '配置加载成功'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': False, 'error': '没有保存的配置'}), 404


@app.route('/api/list_saved_configs')
@login_required
def api_list_saved_configs():
    """列出当前用户保存的配置文件"""
    username = get_current_user()['username']
    configs = []
    
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
            # 过滤只显示当前用户的配置或公共配置
            if username in filename or filename == 'current_config.json':
                filepath = os.path.join(DATA_DIR, filename)
                stat = os.stat(filepath)
                configs.append({
                    'filename': filename,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'size': stat.st_size
                })
    
    # 管理员可以看到所有配置
    if is_admin():
        for filename in os.listdir(DATA_DIR):
            if filename.endswith('.json') and filename not in [c['filename'] for c in configs]:
                filepath = os.path.join(DATA_DIR, filename)
                stat = os.stat(filepath)
                configs.append({
                    'filename': filename,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'size': stat.st_size
                })
    
    configs.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify({'configs': configs})


@app.route('/api/save_config_as', methods=['POST'])
@login_required
def api_save_config_as():
    """另存配置为指定名称"""
    try:
        data = request.get_json()
        config = data.get('config')
        name = data.get('name', 'unnamed')
        username = get_current_user()['username']
        
        # 清理文件名
        safe_name = ''.join(c for c in name if c.isalnum() or c in '_ -中文').strip()
        if not safe_name:
            safe_name = 'config'
        
        filename = f'{safe_name}_{username}.json'
        filepath = os.path.join(DATA_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': f'配置已保存为 {filename}',
            'filename': filename
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/load_saved_config/<filename>')
@login_required
def api_load_saved_config(filename):
    """加载指定的配置文件"""
    filepath = os.path.join(DATA_DIR, filename)
    
    # 检查权限（只能加载自己的配置，管理员可以加载所有）
    username = get_current_user()['username']
    if not is_admin() and username not in filename:
        return jsonify({'success': False, 'error': '无权访问此配置'}), 403
    
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return jsonify({
                'success': True,
                'config': config,
                'filename': filename
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': False, 'error': '配置文件不存在'}), 404


@app.route('/api/delete_saved_config/<filename>', methods=['DELETE'])
@login_required
def api_delete_saved_config(filename):
    """删除指定的配置文件"""
    filepath = os.path.join(DATA_DIR, filename)
    
    # 检查权限
    username = get_current_user()['username']
    if not is_admin() and username not in filename:
        return jsonify({'success': False, 'error': '无权删除此配置'}), 403
    
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            return jsonify({'success': True, 'message': f'已删除 {filename}'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': False, 'error': '配置文件不存在'}), 404


@app.route('/api/preview_code', methods=['POST'])
@login_required
def api_preview_code():
    """实时预览生成的代码"""
    try:
        config = request.get_json()
        lang = request.args.get('lang', 'python')
        if lang == 'c':
            result = generate_c_parser_code(config)
            # 合并 header 和 source 用于预览
            code = f"// === arinc429_parser.h ===\n\n{result['header']}\n\n// === arinc429_parser.c ===\n\n{result['source']}"
        else:
            code = generate_parser_code(config)
        return jsonify({'success': True, 'code': code})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/generate_c', methods=['POST'])
@login_required
def api_generate_c():
    """生成 C 语言解析代码 (.h 和 .c 文件打包为 zip)"""
    try:
        config = request.get_json()
        
        # 验证配置 (跳过空 label_oct)
        errors = validate_config(config, skip_empty_labels=True)
        if errors:
            return jsonify({'success': False, 'errors': errors}), 400
        
        # 生成 C 代码
        result = generate_c_parser_code(config)
        header_code = result['header']
        source_code = result['source']
        
        # 生成文件名
        protocol_name = config.get('protocol_meta', {}).get('name', 'protocol')
        safe_name = ''.join(c for c in protocol_name if c.isalnum() or c in '_ -').strip()
        if not safe_name:
            safe_name = 'protocol'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 添加用户名到文件名
        username = get_current_user()['username']
        base_filename = f'{safe_name}_parser_{timestamp}_{username}'
        
        # 保存到输出目录
        header_path = os.path.join(OUTPUT_DIR, f'{base_filename}.h')
        source_path = os.path.join(OUTPUT_DIR, f'{base_filename}.c')
        with open(header_path, 'w', encoding='utf-8') as f:
            f.write(header_code)
        with open(source_path, 'w', encoding='utf-8') as f:
            f.write(source_code)
        
        # 创建 zip 文件
        zip_filename = f'{base_filename}.zip'
        zip_path = os.path.join(OUTPUT_DIR, zip_filename)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(header_path, 'arinc429_parser.h')
            zf.write(source_path, 'arinc429_parser.c')
        
        # 合并预览
        preview = f"// === arinc429_parser.h ===\n\n{header_code[:1000]}...\n\n// === arinc429_parser.c ===\n\n{source_code[:1000]}..."
        
        return jsonify({
            'success': True,
            'message': 'C代码生成成功 (包含 .h 和 .c 文件)',
            'filename': zip_filename,
            'files': [f'{base_filename}.h', f'{base_filename}.c'],
            'code_preview': preview
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False, 
            'errors': [str(e)],
            'traceback': traceback.format_exc()
        }), 500


# ============================================================
# 用户信息 API
# ============================================================

@app.route('/api/user/info')
@login_required
def api_user_info():
    """获取当前用户信息"""
    user = get_current_user()
    return jsonify({
        'success': True,
        'user': user
    })


@app.route('/api/user/change_password', methods=['POST'])
@login_required
def api_change_password():
    """修改当前用户密码"""
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    username = get_current_user()['username']
    success, message = change_password(username, old_password, new_password)
    
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'error': message}), 400


# ============================================================
# 设备树管理 API
# ============================================================

@app.route('/api/import_device_tree', methods=['POST'])
@login_required
def api_import_device_tree():
    """从数据协议目录导入设备树"""
    try:
        if not os.path.exists(DATA_PROTOCOL_DIR):
            return jsonify({
                'success': False, 
                'error': f'数据协议目录不存在: {DATA_PROTOCOL_DIR}'
            }), 400
        
        device_tree = import_device_tree_from_directory(DATA_PROTOCOL_DIR)
        
        if not device_tree:
            return jsonify({
                'success': False,
                'error': '未找到任何设备目录'
            }), 400
        
        # 保存到数据库
        save_device_tree_to_db(device_tree)
        
        return jsonify({
            'success': True,
            'device_tree': device_tree,
            'message': f'成功导入 {len(device_tree)} 个顶级节点'
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/system/<system_id>/next_device_number', methods=['GET'])
@login_required
def api_get_next_device_number(system_id):
    """获取系统下一个设备的编号"""
    try:
        # 获取系统信息
        system = db_get_device(system_id)
        if not system:
            return jsonify({'success': False, 'error': '系统不存在'}), 404
        
        # 从系统名称提取系统编号（如 ATA32-起落架系统 -> 32）
        import re
        system_name = system.get('name', '')
        match = re.search(r'ATA(\d+)', system_name, re.IGNORECASE)
        if match:
            system_prefix = match.group(1)
        else:
            # 没有 ATA 编号，尝试从 device_id 提取
            match = re.search(r'ata(\d+)', system_id, re.IGNORECASE)
            if match:
                system_prefix = match.group(1)
            else:
                system_prefix = '0'
        
        # 获取该系统下所有设备，找出最大的序号
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取系统的数据库主键 ID
        system_db_id = system.get('id')
        
        # 查询该系统下所有设备的名称
        cursor.execute('''
            SELECT name FROM devices WHERE parent_id = ? AND is_device = 1
        ''', (system_db_id,))
        
        devices = cursor.fetchall()
        conn.close()
        
        # 找出最大的序号
        max_seq = 0
        for device in devices:
            device_name = device['name']
            # 尝试从设备名称提取序号，如 "32-3-转弯控制单元-429" -> 3
            match = re.search(rf'^{system_prefix}-(\d+)', device_name)
            if match:
                seq = int(match.group(1))
                if seq > max_seq:
                    max_seq = seq
        
        next_seq = max_seq + 1
        
        return jsonify({
            'success': True,
            'system_prefix': system_prefix,
            'next_seq': next_seq,
            'current_max': max_seq
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/add_system', methods=['POST'])
@operator_required
def api_add_system():
    """添加新系统到设备树
    
    需要设备人员(operator)或管理员(admin)权限"""
    try:
        data = request.get_json()
        system_name = data.get('system_name', '').strip()
        
        if not system_name:
            return jsonify({'success': False, 'error': '请输入系统名称'}), 400
        
        # 生成系统 ID（从名称提取，如 ATA32-起落架系统 -> ata32）
        import re
        match = re.search(r'ATA(\d+)', system_name, re.IGNORECASE)
        if match:
            system_id = f"ata{match.group(1)}"
        else:
            # 没有 ATA 编号，使用名称的拼音首字母或时间戳
            import time
            system_id = f"sys_{int(time.time())}"
        
        # 检查系统 ID 是否已存在
        existing = db_get_device(system_id)
        if existing:
            return jsonify({'success': False, 'error': f'系统 "{system_name}" 已存在'}), 400
        
        # 创建新系统（顶级节点，parent_id 为 None）
        new_id = db_create_device(
            device_id=system_id,
            name=system_name,
            parent_id=None,
            is_device=False,
            device_version=None
        )
        
        if new_id:
            return jsonify({
                'success': True,
                'message': f'系统 "{system_name}" 添加成功',
                'system_id': system_id
            })
        else:
            return jsonify({'success': False, 'error': '创建系统失败'}), 400
            
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/add_device', methods=['POST'])
@operator_required
def api_add_device():
    """添加新设备到设备树
    
    需要设备人员(operator)或管理员(admin)权限"""
    try:
        data = request.get_json()
        parent_id = data.get('parent_id')  # 父节点的 device_id
        device_number = data.get('device_number')  # 如 32-1
        device_name = data.get('device_name', '').strip()  # 如 转弯控制单元
        protocol_type = data.get('protocol_type', '429')  # 协议类型
        full_device_name = data.get('full_device_name')  # 完整设备名称（如 32-1-转弯控制单元-429）
        parsed_labels = data.get('parsed_labels')  # 解析出的 labels（可选）
        
        if not parent_id:
            return jsonify({'success': False, 'error': '请选择所属系统'}), 400
        if not device_name:
            return jsonify({'success': False, 'error': '请输入设备名称'}), 400
        
        # 获取父节点信息
        parent_device = db_get_device(parent_id)
        
        if not parent_device:
            return jsonify({'success': False, 'error': '父节点不存在'}), 404
        
        # 生成新设备的 device_id
        parent_device_id = parent_device.get('device_id', '')
        
        # 使用完整设备名称作为显示名称
        if full_device_name:
            full_name = full_device_name
        elif device_number:
            full_name = f"{device_number}-{device_name}-{protocol_type}"
        else:
            full_name = f"{device_name}-{protocol_type}"
        
        # 生成设备 ID
        if device_number:
            device_number_normalized = device_number.replace('-', '_')
            new_device_id = f"{parent_device_id}_{device_number_normalized}"
        else:
            import time
            safe_name = device_name.replace(' ', '_').replace('-', '_')[:20]
            new_device_id = f"{parent_device_id}_{safe_name}_{int(time.time()) % 10000}"
        
        # 检查设备 ID 是否已存在
        existing = db_get_device(new_device_id)
        if existing:
            return jsonify({'success': False, 'error': f'设备 ID "{new_device_id}" 已存在'}), 400
        
        # 创建新设备
        new_id = db_create_device(
            device_id=new_device_id,
            name=full_name,
            parent_id=parent_device['id'],  # 使用数据库主键作为 parent_id
            is_device=True,
            device_version='V1.0'
        )
        
        if not new_id:
            return jsonify({'success': False, 'error': '创建设备失败'}), 400
        
        # 创建默认协议版本
        from database import db_create_protocol_version, db_save_labels
        version_id = db_create_protocol_version(
            db_device_id=new_id,
            version='V1.0',
            name=f'{full_name}-V1.0',
            source='user_created'
        )
        
        # 如果有解析出的 labels，保存它们
        if parsed_labels and version_id:
            db_save_labels(new_device_id, parsed_labels, protocol_version_id=version_id)
        
        return jsonify({
            'success': True,
            'message': f'设备 "{full_name}" 添加成功',
            'device_id': new_device_id,
            'protocol_type': protocol_type
        })
            
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/device/<device_id>', methods=['DELETE'])
@operator_required
def api_delete_device(device_id):
    """删除设备协议
    
    需要设备人员(operator)或管理员(admin)权限"""
    try:
        # 获取设备信息
        device = db_get_device(device_id)
        
        if not device:
            return jsonify({'success': False, 'error': '设备协议不存在'}), 404
        
        if not device.get('is_device'):
            return jsonify({'success': False, 'error': '只能删除设备协议节点，不能删除系统节点'}), 400
        
        # 删除设备
        success = db_delete_device(device_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'设备协议已删除'
            })
        else:
            return jsonify({'success': False, 'error': '删除失败'}), 400
            
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/device_tree')
@login_required
def api_get_device_tree():
    """获取当前用户的设备树"""
    from git_storage import get_lock_manager
    
    username = get_current_user()['username']
    
    try:
        # 优先从数据库获取设备树结构
        device_tree = get_device_tree_from_db()
        user_config = db_get_user_config(username)
        protocol_meta = user_config.get('protocol_meta', {})
        
        # 获取所有设备锁状态（使用内存锁管理器）
        lock_manager = get_lock_manager()
        all_locks = lock_manager.get_all_locks()
        
        if device_tree:
            # 为每个设备节点填充 labels 和锁状态
            from git_storage import get_version_manager
            version_manager = get_version_manager()
            
            def fill_labels(nodes):
                for node in nodes:
                    if node.get('is_device'):
                        device_id = node.get('device_id') or node.get('id')
                        if device_id:
                            # 优先从 Git 获取 labels 和版本历史
                            git_info = version_manager.get_device_info(device_id)
                            if git_info:
                                node['labels'] = git_info.get('labels', [])
                                node['version_history'] = version_manager.get_device_version_history(device_id)
                            else:
                                # 回退到数据库获取 labels（设备树结构仍从数据库读取）
                            node['labels'] = db_get_labels(device_id)
                                node['version_history'] = []
                            
                            # 添加锁状态（使用内存锁管理器）
                            lock_info = all_locks.get(device_id)
                            if lock_info:
                                node['is_locked'] = True
                                node['locked_by'] = lock_info['locked_by']
                                node['locked_by_display_name'] = lock_info['locked_by_display_name']
                                node['locked_by_self'] = lock_info['locked_by'] == username
                            else:
                                node['is_locked'] = False
                                node['locked_by'] = None
                                node['locked_by_display_name'] = None
                                node['locked_by_self'] = False
                    if 'children' in node:
                        fill_labels(node['children'])
            
            fill_labels(device_tree)
            
            return jsonify({
                'success': True,
                'device_tree': device_tree,
                'protocol_meta': protocol_meta
            })
        
        # 如果数据库为空，尝试从 JSON 文件加载（兼容旧数据）
        user_config_path = os.path.join(DATA_DIR, f'current_config_{username}.json')
        if os.path.exists(user_config_path):
            with open(user_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if 'device_tree' not in config or not config['device_tree']:
                config = migrate_legacy_config(config)
            
            # 迁移到数据库
            save_device_tree_to_db(config.get('device_tree', []))
            db_save_user_config(username, protocol_meta=config.get('protocol_meta', {}))
            
            return jsonify({
                'success': True,
                'device_tree': config.get('device_tree', []),
                'protocol_meta': config.get('protocol_meta', {})
            })
        
        # 没有配置，返回空设备树
        return jsonify({
            'success': True,
            'device_tree': [],
            'protocol_meta': {}
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<device_id>/labels')
@login_required
def api_get_device_labels(device_id):
    """获取指定设备的 labels（从 Git 存储读取）
    
    Query params:
        version: 可选，指定历史版本号（如 V1.0, V2.0）
    """
    from git_storage import get_version_manager, get_lock_manager
    
    requested_version = request.args.get('version', None)
    
    try:
        username = get_current_user()['username']
        version_manager = get_version_manager()
    
        # 优先从 Git 存储获取设备信息
        git_device_info = version_manager.get_device_info(device_id)
        
        if git_device_info:
            # 从 Git 存储读取
            labels = git_device_info.get('labels', [])
            current_ver = git_device_info.get('current_version', 'V1.0')
            device_name = git_device_info.get('device_name', device_id)
            device_description = git_device_info.get('description', '')
            base_commit = git_device_info.get('base_commit', '')
            updated_at = git_device_info.get('updated_at', '')
            updated_by = git_device_info.get('updated_by', '')
            current_protocol_version_name = git_device_info.get('current_protocol_version_name', '')
        
        # 获取版本历史
            version_history = version_manager.get_device_version_history(device_id)
        
            # 构建可切换的版本列表（去重，每个版本号只保留一条）
        saved_versions = [{
            'version': current_ver,
            'label_count': len(labels),
            'is_current': True,
                'updated_at': updated_at
        }]
        
            seen_versions = {current_ver}  # 用于去重
        for record in version_history:
                ver = record.get('version', '')
                if ver in seen_versions:
                continue
                seen_versions.add(ver)
            saved_versions.append({
                    'version': ver,
                'label_count': record.get('label_count', 0),
                'is_current': False,
                'updated_at': record.get('updated_at', ''),
                'change_summary': record.get('change_summary', '')
            })
        
        # 如果请求了特定历史版本
        labels_to_return = labels
        viewing_version = current_ver
        is_viewing_history = False
        
        if requested_version and requested_version != current_ver:
                snapshot = version_manager.get_version_snapshot(device_id, requested_version)
            if snapshot:
                    labels_to_return = snapshot.get('labels', [])
                viewing_version = requested_version
                is_viewing_history = True
        
            # 获取锁状态（使用内存锁管理器）
            lock_manager = get_lock_manager()
            lock_result = lock_manager.get_lock_info_for_user(device_id, username)
            lock_status = lock_result['lock_status']
            can_edit = lock_result['can_edit']
            lock_info = lock_result['lock_info']
            
        return jsonify({
            'success': True,
            'device_id': device_id,
                'device_name': device_name,
            'device_version': current_ver,
                'device_description': device_description,
            'viewing_version': viewing_version,
            'is_viewing_history': is_viewing_history,
            'current_version_name': current_protocol_version_name,
                'current_protocol_version_id': None,  # Git 存储不使用协议版本 ID
                'protocol_versions': [],  # Git 存储暂不支持多协议版本
            'saved_versions': saved_versions,
            'labels': labels_to_return,
                'version_history': version_history[:20],
                # 锁状态
                'lock_status': lock_status,
                'lock_info': lock_info,
                'can_edit': can_edit,
                # 乐观锁
                'base_commit': base_commit,
                'base_version': current_ver,
                'updated_at': updated_at,
                'updated_by': updated_by,
                # 标记数据来源
                'storage_type': 'git'
            })
        
        # Git 存储中没有该设备，返回错误
        return jsonify({'success': False, 'error': f'设备 {device_id} 不存在于 Git 存储中'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<device_id>/labels', methods=['POST'])
@operator_required
def api_save_device_labels(device_id):
    """保存设备的 labels（使用 Git 存储，带版本管理、锁检查和乐观锁）
    
    需要设备人员(operator)或管理员(admin)权限
    
    版本管理逻辑：
    - 每次保存会创建新版本（如 V5.0 -> V6.0 -> V7.0）
    - 版本快照保存到 Git 仓库的 versions/ 目录
    - 发布记录保存到 history/releases.json
    
    锁检查：
    - 保存前检查当前用户是否持有设备锁
    - 如果设备被他人锁定，拒绝保存
    
    乐观锁：
    - 保存时检查 base_commit 是否仍是最新
    - 如果已被他人更新，返回冲突信息
    
    返回结构化的保存结果，包括：
    - previous_version: 保存前版本
    - new_version: 保存后版本
    - changed: 是否有实际变化
    - change_stats: 变更统计 {added, modified, deleted}
    - change_summary: 用户填写的变更说明
    - saved_at: 保存时间
    - new_commit: Git commit hash
    """
    from database import db_get_device, db_update_device
    from git_storage import get_version_manager, get_lock_manager
    
    username = get_current_user()['username']
    
    try:
        data = request.get_json()
        new_labels = data.get('labels', [])
        change_summary = data.get('change_summary', '')
        new_description = data.get('description', '')
        protocol_version_name = data.get('protocol_version_name', '')
        
        # 乐观锁参数
        base_commit = data.get('base_commit')
        base_version = data.get('base_version')
        
        # 从数据库获取设备基础信息（用于验证设备存在）
        device = db_get_device(device_id)
        
        if not device:
            return jsonify({
                'success': False, 
                'error': '设备不存在',
                'error_type': 'device_not_found'
            }), 404
        
        if not device.get('is_device'):
            return jsonify({
                'success': False, 
                'error': '该节点不是设备节点',
                'error_type': 'not_a_device'
            }), 400
        
        # 【锁检查】检查当前用户是否持有设备锁（使用内存锁管理器）
        lock_manager = get_lock_manager()
        lock_result = lock_manager.get_lock_info_for_user(device_id, username)
        if lock_result['lock_status'] == 'locked_by_other':
            lock_info = lock_result['lock_info']
            return jsonify({
                'success': False,
                'error': f'设备正由 {lock_info["locked_by_display_name"] or lock_info["locked_by"]} 编辑中，无法保存',
                'error_type': 'device_locked',
                'lock_info': lock_info
            }), 403
        
        # 【使用 Git 存储保存】
        version_manager = get_version_manager()
        
        # 先获取当前版本用于 protocol_meta
        current_device_version = device.get('device_version', 'V1.0')
        
        success, message, result_data = version_manager.save_device_version(
            device_id=device_id,
            new_labels=new_labels,
            username=username,
            change_summary=change_summary,
            protocol_meta={
                'name': device.get('name', ''),
                'version': current_device_version,  # 使用当前版本，保存后会自动升级
                'description': new_description
            },
            base_commit=base_commit,
            base_version=base_version
        )
        
        if not success:
            # 处理冲突
            error_type = result_data.get('error_type', 'server_error')
            status_code = 409 if error_type == 'conflict' else 500
            return jsonify({
                'success': False,
                'error': message,
                'error_type': error_type,
                **result_data
            }), status_code
        
        # 同步更新数据库索引（保持数据库作为索引层）
        db_update_device(
            device_id, 
            device_version=result_data.get('new_version', device.get('device_version', 'V1.0')),
            current_version_name=protocol_version_name,
            description=new_description if new_description else None
        )
        
        # 同步保存 Labels 到数据库（作为缓存）
        db_save_labels(device_id, new_labels)
        
        return jsonify({
            'success': True,
            'changed': result_data.get('has_changed', False),
            'previous_version': result_data.get('old_version', ''),
            'new_version': result_data.get('new_version', ''),
            'device_version': result_data.get('new_version', ''),
            'device_name': device.get('name', ''),
            'change_stats': result_data.get('change_stats', {}),
            'change_summary': result_data.get('change_summary', change_summary),
            'saved_at': result_data.get('saved_at', ''),
            'saved_by': result_data.get('saved_by', username),
            'label_count': len(new_labels),
            'new_commit': result_data.get('new_commit', ''),
            'message': f'保存成功，当前版本: {result_data.get("new_version", "")}' + (' (版本已更新)' if result_data.get('has_changed') else '')
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': 'server_error',
            'traceback': traceback.format_exc()
        }), 500


def calculate_label_changes(old_labels, new_labels):
    """计算 Labels 的变更统计
    
    Returns:
        dict: {added: int, modified: int, deleted: int}
    """
    # 创建旧 labels 的 map（按 label_oct 索引）
    old_map = {}
    for idx, label in enumerate(old_labels):
        key = label.get('label_oct') or f'__idx_{idx}'
        old_map[key] = label
    
    added = 0
    modified = 0
    deleted = 0
    
    # 检查新增和修改
    new_keys = set()
    for idx, label in enumerate(new_labels):
        key = label.get('label_oct') or f'__idx_{idx}'
        new_keys.add(key)
        
        if key in old_map:
            # 检查是否修改（比较关键字段）
            old_label = old_map[key]
            if is_label_modified(old_label, label):
                modified += 1
        else:
            # 新增
            added += 1
    
    # 检查删除
    for key in old_map:
        if key not in new_keys:
            deleted += 1
    
    return {
        'added': added,
        'modified': modified,
        'deleted': deleted
    }


def is_label_modified(old_label, new_label):
    """检查 Label 是否被修改"""
    # 比较关键字段
    key_fields = ['label_oct', 'name', 'direction', 'data_type', 'unit', 'range', 'resolution', 'notes']
    
    for field in key_fields:
        old_val = old_label.get(field, '')
        new_val = new_label.get(field, '')
        if str(old_val) != str(new_val):
            return True
    
    # 比较复杂字段（JSON 序列化后比较）
    complex_fields = ['discrete_bits', 'special_fields', 'bnr_fields']
    for field in complex_fields:
        old_val = json.dumps(old_label.get(field, {}), sort_keys=True, ensure_ascii=False)
        new_val = json.dumps(new_label.get(field, {}), sort_keys=True, ensure_ascii=False)
        if old_val != new_val:
            return True
    
    return False


@app.route('/api/device/<device_id>/version_history')
@login_required
def api_get_device_version_history(device_id):
    """获取设备的版本历史（发布历史）
    
    Query params:
        type: 'releases' (默认) 或 'saves'
            - releases: 只返回正式发布的版本节点
            - saves: 返回完整保存时间线
    
    返回增强的版本历史信息，每条记录包含：
    - version: 版本号
    - updated_at: 更新时间
    - updated_by: 操作人
    - change_summary: 变更说明
    - change_stats: 变更统计 {added, modified, deleted}
    - diff_details: 详细变更 {added_details, removed_details, modified_details}
    - git_commit: Git commit hash
    - is_release: 是否是正式发布
    """
    from git_storage import get_version_manager
    
    history_type = request.args.get('type', 'releases')
    
    try:
        version_manager = get_version_manager()
        
        # 优先从 Git 存储获取
        if history_type == 'saves':
            # 获取完整保存历史
            git_history = version_manager.get_device_save_history(device_id)
        else:
            # 获取发布历史
            git_history = version_manager.get_device_version_history(device_id)
        
        if git_history:
            # 从 Git 存储获取设备信息
            device_info = version_manager.get_device_info(device_id)
            device_name = device_info.get('device_name', '') if device_info else device_id
            current_version = device_info.get('current_version', 'V1.0') if device_info else 'V1.0'
        
        return jsonify({
            'success': True,
            'device_id': device_id,
                'device_name': device_name,
                'current_version': current_version,
                'total_versions': len(git_history),
                'history_type': history_type,
                'version_history': git_history,
                'storage_type': 'git'
            })
        
        # Git 存储中没有该设备的版本历史
        return jsonify({
            'success': True,
            'device_id': device_id,
            'device_name': device_id,
            'current_version': 'V1.0',
            'total_versions': 0,
            'history_type': history_type,
            'version_history': [],
            'storage_type': 'git'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<device_id>/version/<version>/restore', methods=['POST'])
@operator_required
def api_restore_version(device_id, version):
    """恢复到指定历史版本
    
    将指定版本的 Labels 恢复为当前版本，会创建一个新的版本记录。
    
    请求体:
    {
        "restore_summary": "可选，恢复说明"
    }
    
    需要设备人员(operator)或管理员(admin)权限
    """
    from git_storage import get_version_manager, get_lock_manager
    
    try:
        user = get_current_user()
        username = user['username']
        
        # 检查设备锁
        lock_manager = get_lock_manager()
        lock_result = lock_manager.get_lock_info_for_user(device_id, username)
        if lock_result['lock_status'] == 'locked_by_other':
            lock_info = lock_result['lock_info']
            return jsonify({
                'success': False,
                'error': f'设备正由 {lock_info["locked_by_display_name"] or lock_info["locked_by"]} 编辑中，无法恢复',
                'error_type': 'device_locked'
            }), 403
        
        data = request.get_json() or {}
        restore_summary = data.get('restore_summary', f'从版本 {version} 恢复')
        
        version_manager = get_version_manager()
        success, message, result_data = version_manager.restore_version(
            device_id=device_id,
            version=version,
            username=username,
            restore_summary=restore_summary
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'restored_from': version,
                'new_version': result_data.get('new_version', ''),
                'new_commit': result_data.get('new_commit', ''),
                'label_count': result_data.get('label_count', 0)
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<device_id>/version/<version>/labels')
@login_required
def api_get_version_labels(device_id, version):
    """获取指定版本的 Labels（用于预览）
    
    返回指定历史版本的完整 Labels 列表
    """
    from git_storage import get_version_manager
    
    try:
        version_manager = get_version_manager()
        labels = version_manager.get_version_labels(device_id, version)
        
        if labels is not None:
            return jsonify({
                'success': True,
                'device_id': device_id,
                'version': version,
                'labels': labels,
                'label_count': len(labels)
            })
        else:
            return jsonify({
                'success': False,
                'error': f'版本 {version} 不存在或没有快照'
            }), 404
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<device_id>/versions')
@login_required
def api_list_versions(device_id):
    """列出设备所有可恢复的版本
    
    返回所有有快照的版本列表
    """
    from git_storage import get_version_manager
    
    try:
        version_manager = get_version_manager()
        versions = version_manager.list_available_versions(device_id)
        
        # 获取当前版本
        device_info = version_manager.get_device_info(device_id)
        current_version = device_info.get('current_version', 'V1.0') if device_info else 'V1.0'
        
        return jsonify({
            'success': True,
            'device_id': device_id,
            'current_version': current_version,
            'versions': versions,
            'total': len(versions)
        })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<device_id>/version/<version>', methods=['DELETE'])
@operator_required
def api_delete_version(device_id, version):
    """删除指定的历史版本
    
    需要设备人员(operator)或管理员(admin)权限"""
    try:
        username = session.get('username', 'unknown')
        version_manager = git_storage.get_version_manager()
        
        success, message = version_manager.delete_version(device_id, version, username)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'success': False, 'error': message}), 400
            
    except Exception as e:
        import traceback
        return jsonify({
            'success': False, 
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/device/<device_id>/compare_versions')
@login_required
def api_compare_versions(device_id):
    """对比两个版本的 Labels 差异"""
    from git_storage import get_version_manager
    
    try:
        version_manager = get_version_manager()
        
        # 从 Git 获取设备信息
        device_info = version_manager.get_device_info(device_id)
        if not device_info:
            return jsonify({'success': False, 'error': '设备不存在'}), 404
        
        version_a = request.args.get('version_a', '')
        version_b = request.args.get('version_b', '')
        
        if not version_a or not version_b:
            return jsonify({'success': False, 'error': '需要指定两个版本进行对比'}), 400
        
        current_ver = device_info.get('current_version', 'V1.0')
        device_name = device_info.get('device_name', device_id)
        
        # 获取版本 A 的 Labels
        if version_a == current_ver:
            labels_a = device_info.get('labels', [])
        else:
            labels_a = version_manager.get_version_labels(device_id, version_a)
            if labels_a is None:
                return jsonify({'success': False, 'error': f'版本 {version_a} 不存在'}), 404
        
        # 获取版本 B 的 Labels
        if version_b == current_ver:
            labels_b = device_info.get('labels', [])
        else:
            labels_b = version_manager.get_version_labels(device_id, version_b)
            if labels_b is None:
                return jsonify({'success': False, 'error': f'版本 {version_b} 不存在'}), 404
        
        # 计算差异
        diff = compute_labels_diff(labels_a, labels_b, version_a, version_b)
        
        return jsonify({
            'success': True,
            'device_id': device_id,
            'device_name': device_name,
            'version_a': version_a,
            'version_b': version_b,
            'labels_a_count': len(labels_a),
            'labels_b_count': len(labels_b),
            'diff': diff
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# 设备编辑锁 API（使用内存锁管理器，不依赖数据库）
# ============================================================

@app.route('/api/device/<device_id>/lock/acquire', methods=['POST'])
@login_required
def api_acquire_device_lock(device_id):
    """申请设备编辑锁
    
    请求体:
    {
        "session_id": "可选，如果不提供则自动生成"
    }
    
    返回:
    {
        "success": true/false,
        "message": "...",
        "lock_info": {...},
        "can_edit": true/false
    }
    """
    from git_storage import get_lock_manager
    import uuid
    
    try:
        user = get_current_user()
        username = user['username']
        display_name = user.get('display_name', username)
        
        data = request.get_json() or {}
        session_id = data.get('session_id') or str(uuid.uuid4())
        
        lock_manager = get_lock_manager()
        success, message, lock_info = lock_manager.acquire_lock(
            device_id, username, display_name, session_id
        )
        
        return jsonify({
            'success': success,
            'message': message,
            'lock_info': lock_info,
            'can_edit': success,
            'session_id': session_id if success else None
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e), 'can_edit': False}), 500


@app.route('/api/device/<device_id>/lock/release', methods=['POST'])
@login_required
def api_release_device_lock(device_id):
    """释放设备编辑锁
    
    请求体:
    {
        "session_id": "可选"
    }
    """
    from git_storage import get_lock_manager
    
    try:
        user = get_current_user()
        username = user['username']
        
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        lock_manager = get_lock_manager()
        success, message = lock_manager.release_lock(device_id, username, session_id)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<device_id>/lock/heartbeat', methods=['POST'])
@login_required
def api_heartbeat_device_lock(device_id):
    """心跳续租设备锁
    
    请求体:
    {
        "session_id": "必须"
    }
    """
    from git_storage import get_lock_manager
    
    try:
        user = get_current_user()
        username = user['username']
        
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'success': False, 'error': '缺少 session_id'}), 400
        
        lock_manager = get_lock_manager()
        success, message, lock_info = lock_manager.heartbeat(device_id, username, session_id)
        
        return jsonify({
            'success': success,
            'message': message,
            'lock_info': lock_info
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<device_id>/lock/status')
@login_required
def api_get_device_lock_status(device_id):
    """获取设备锁状态"""
    from git_storage import get_lock_manager
    
    try:
        user = get_current_user()
        username = user['username']
        
        lock_manager = get_lock_manager()
        lock_result = lock_manager.get_lock_info_for_user(device_id, username)
        
        return jsonify({
            'success': True,
            'lock_status': lock_result['lock_status'],
            'is_locked': lock_result['lock_status'] != 'free',
            'locked_by': lock_result['lock_info']['locked_by'] if lock_result['lock_info'] else None,
            'locked_by_display_name': lock_result['lock_info']['locked_by_display_name'] if lock_result['lock_info'] else None,
            'locked_by_self': lock_result['lock_status'] == 'locked_by_self',
            'can_edit': lock_result['can_edit'],
            'lock_info': lock_result['lock_info']
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<device_id>/lock/force_release', methods=['POST'])
@admin_required
def api_force_release_device_lock(device_id):
    """强制释放设备锁（管理员操作）"""
    from git_storage import get_lock_manager
    
    try:
        user = get_current_user()
        admin_username = user['username']
        
        lock_manager = get_lock_manager()
        success, message = lock_manager.force_release_lock(device_id, admin_username)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/locks/all')
@login_required
def api_get_all_device_locks():
    """获取所有设备锁状态（用于设备树展示）"""
    from git_storage import get_lock_manager
    
    try:
        user = get_current_user()
        username = user['username']
        
        lock_manager = get_lock_manager()
        all_locks = lock_manager.get_all_locks()
        
        # 添加 locked_by_self 标记
        result = {}
        for device_id, lock_info in all_locks.items():
            result[device_id] = {
                'is_locked': True,
                'locked_by': lock_info['locked_by'],
                'locked_by_display_name': lock_info['locked_by_display_name'],
                'locked_by_self': lock_info['locked_by'] == username,
                'lock_acquired_at': lock_info['lock_acquired_at'],
                'expires_at': lock_info['expires_at']
            }
        
        return jsonify({
            'success': True,
            'locks': result
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def compute_labels_diff(labels_a, labels_b, version_a, version_b):
    """计算两个版本 Labels 的详细差异"""
    # 构建 label_oct 到 label 的映射
    map_a = {label.get('label_oct', ''): label for label in labels_a if label.get('label_oct')}
    map_b = {label.get('label_oct', ''): label for label in labels_b if label.get('label_oct')}
    
    oct_a = set(map_a.keys())
    oct_b = set(map_b.keys())
    
    # 分类
    added_octs = oct_b - oct_a  # 在 B 中新增的
    removed_octs = oct_a - oct_b  # 在 B 中删除的
    common_octs = oct_a & oct_b  # 共同存在的
    
    # 新增的 Labels
    added = []
    for oct in sorted(added_octs):
        label = map_b[oct]
        added.append({
            'label_oct': oct,
            'name': label.get('name', ''),
            'direction': label.get('direction', ''),
            'data_type': label.get('data_type', '')
        })
    
    # 删除的 Labels
    removed = []
    for oct in sorted(removed_octs):
        label = map_a[oct]
        removed.append({
            'label_oct': oct,
            'name': label.get('name', ''),
            'direction': label.get('direction', ''),
            'data_type': label.get('data_type', '')
        })
    
    # 修改的 Labels（比较字段差异）
    modified = []
    for oct in sorted(common_octs):
        label_a = map_a[oct]
        label_b = map_b[oct]
        changes = compare_label_fields(label_a, label_b)
        if changes:
            modified.append({
                'label_oct': oct,
                'name_a': label_a.get('name', ''),
                'name_b': label_b.get('name', ''),
                'changes': changes
            })
    
    return {
        'added': added,
        'removed': removed,
        'modified': modified,
        'summary': {
            'added_count': len(added),
            'removed_count': len(removed),
            'modified_count': len(modified),
            'unchanged_count': len(common_octs) - len(modified)
        }
    }


def compare_label_fields(label_a, label_b):
    """比较两个 Label 的字段差异"""
    changes = []
    
    # 需要比较的简单字段
    simple_fields = ['name', 'direction', 'data_type', 'unit', 'range', 'resolution', 
                     'reserved_bits', 'notes']
    
    for field in simple_fields:
        val_a = label_a.get(field, '')
        val_b = label_b.get(field, '')
        if str(val_a) != str(val_b):
            changes.append({
                'field': field,
                'field_name': get_field_display_name(field),
                'old': val_a if val_a else '(空)',
                'new': val_b if val_b else '(空)'
            })
    
    # 比较 sources 数组
    sources_a = label_a.get('sources', []) or []
    sources_b = label_b.get('sources', []) or []
    if sources_a != sources_b:
        changes.append({
            'field': 'sources',
            'field_name': '数据源',
            'old': ', '.join(sources_a) if sources_a else '(空)',
            'new': ', '.join(sources_b) if sources_b else '(空)'
        })
    
    # 比较 discrete_bits
    bits_a = label_a.get('discrete_bits', {}) or {}
    bits_b = label_b.get('discrete_bits', {}) or {}
    if bits_a != bits_b:
        changes.append({
            'field': 'discrete_bits',
            'field_name': '离散位定义',
            'old': format_discrete_bits(bits_a),
            'new': format_discrete_bits(bits_b)
        })
    
    # 比较 bnr_fields
    bnr_a = label_a.get('bnr_fields', []) or []
    bnr_b = label_b.get('bnr_fields', []) or []
    if bnr_a != bnr_b:
        changes.append({
            'field': 'bnr_fields',
            'field_name': 'BNR 字段',
            'old': format_bnr_fields(bnr_a),
            'new': format_bnr_fields(bnr_b)
        })
    
    # 比较 special_fields
    special_a = label_a.get('special_fields', []) or []
    special_b = label_b.get('special_fields', []) or []
    if special_a != special_b:
        changes.append({
            'field': 'special_fields',
            'field_name': '特殊字段',
            'old': format_special_fields(special_a),
            'new': format_special_fields(special_b)
        })
    
    return changes


def get_field_display_name(field):
    """获取字段的中文显示名称"""
    names = {
        'name': '名称',
        'direction': '方向',
        'data_type': '数据类型',
        'unit': '单位',
        'range': '范围',
        'resolution': '分辨率',
        'reserved_bits': '保留位',
        'notes': '备注'
    }
    return names.get(field, field)


def format_discrete_bits(bits):
    """格式化离散位定义"""
    if not bits:
        return '(空)'
    items = [f"Bit{k}: {v}" for k, v in sorted(bits.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)]
    return '; '.join(items) if items else '(空)'


def format_bnr_fields(fields):
    """格式化 BNR 字段"""
    if not fields:
        return '(空)'
    items = []
    for f in fields:
        bits = f.get('data_bits', [])
        bit_range = f"{bits[0]}-{bits[1]}" if len(bits) == 2 else str(bits)
        items.append(f"{f.get('name', '')}[{bit_range}]")
    return ', '.join(items) if items else '(空)'


def format_special_fields(fields):
    """格式化特殊字段"""
    if not fields:
        return '(空)'
    items = []
    for f in fields:
        bits = f.get('bits', [])
        bit_range = f"{bits[0]}-{bits[1]}" if len(bits) == 2 else str(bits)
        items.append(f"{f.get('name', '')}[{bit_range}]")
    return ', '.join(items) if items else '(空)'


@app.route('/api/save_device_tree', methods=['POST'])
@login_required
def api_save_device_tree():
    """保存完整的设备树配置"""
    username = get_current_user()['username']
    
    try:
        data = request.get_json()
        device_tree = data.get('device_tree', [])
        protocol_meta = data.get('protocol_meta', {})
        
        # 保存到数据库
        save_device_tree_to_db(device_tree)
        db_save_user_config(username, protocol_meta=protocol_meta)
        
        return jsonify({
            'success': True,
            'message': '设备树保存成功',
            'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate_for_device/<device_id>', methods=['POST'])
@login_required
def api_generate_for_device(device_id):
    """为指定设备生成代码
    
    返回结构化的生成结果，包括：
    - device_name: 设备名称
    - device_version: 设备版本
    - label_count: Label 数量
    - language: 生成语言
    - filename: 输出文件名
    - generated_at: 生成时间
    - can_download: 是否可下载
    """
    username = get_current_user()['username']
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        data = request.get_json() or {}
        lang = data.get('lang', 'python')
        protocol_version_id = data.get('protocol_version_id')
        
        # 从数据库获取设备信息
        device = db_get_device(device_id)
        
        if not device:
            return jsonify({
                'success': False, 
                'error': '设备不存在',
                'error_type': 'device_not_found',
                'suggestion': '请检查设备是否已被删除，或刷新页面重试'
            }), 404
        
        if not device.get('is_device'):
            return jsonify({
                'success': False, 
                'error': '该节点不是设备节点',
                'error_type': 'not_a_device',
                'suggestion': '请选择一个具体的设备节点，而不是系统目录'
            }), 400
        
        device_name = device.get('name', 'device')
        device_version = device.get('device_version', 'V1.0')
        
        # 获取设备的 labels（从数据库）
        labels = db_get_labels(device_id, protocol_version_id)
        
        if not labels:
            return jsonify({
                'success': False, 
                'error': '该设备没有定义任何 Label',
                'error_type': 'no_labels',
                'suggestion': '请先为设备添加 Labels，然后再生成代码',
                'device_name': device_name,
                'device_version': device_version
            }), 400
        
        # 获取用户配置中的协议元信息
        user_config = db_get_user_config(username)
        protocol_meta = user_config.get('protocol_meta', {}) if user_config else {}
        
        # 构建生成用的配置
        gen_config = {
            'protocol_meta': {
                'name': f"{protocol_meta.get('name', '')} - {device_name}",
                'version': device_version,
                'description': f"设备: {device_name}"
            },
            'labels': labels
        }
        
        # 验证配置 (跳过空 label_oct)
        errors = validate_config(gen_config, labels, skip_empty_labels=True)
        if errors:
            return jsonify({
                'success': False, 
                'errors': errors,
                'error_type': 'validation_error',
                'suggestion': '请检查 Label 配置是否完整，修复错误后重试',
                'device_name': device_name,
                'device_version': device_version,
                'label_count': len(labels)
            }), 400
        
        # 生成文件名
        safe_name = ''.join(c for c in device_name if c.isalnum() or c in '_ -').strip()
        if not safe_name:
            safe_name = 'device'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f'{safe_name}_parser_{timestamp}_{username}'
        
        # 通用元数据
        base_metadata = {
            'device_id': device_id,
            'device_name': device_name,
            'device_version': device_version,
            'label_count': len(labels),
            'generated_at': generated_at,
            'generated_by': username,
            'can_download': True
        }
        
        # 生成代码
        if lang == 'c':
            result = generate_c_parser_code(gen_config)
            header_code = result['header']
            source_code = result['source']
            
            # 保存 .h 和 .c 文件
            header_path = os.path.join(OUTPUT_DIR, f'{base_filename}.h')
            source_path = os.path.join(OUTPUT_DIR, f'{base_filename}.c')
            with open(header_path, 'w', encoding='utf-8') as f:
                f.write(header_code)
            with open(source_path, 'w', encoding='utf-8') as f:
                f.write(source_code)
            
            # 创建 zip 文件
            zip_filename = f'{base_filename}.zip'
            zip_path = os.path.join(OUTPUT_DIR, zip_filename)
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(header_path, 'arinc429_parser.h')
                zf.write(source_path, 'arinc429_parser.c')
            
            preview = f"// === arinc429_parser.h ===\n\n{header_code[:1000]}...\n\n// === arinc429_parser.c ===\n\n{source_code[:1000]}..."
            
            return jsonify({
                'success': True,
                'message': 'C 代码生成成功',
                'language': 'c',
                'filename': zip_filename,
                'files': [f'{base_filename}.h', f'{base_filename}.c'],
                'file_description': '包含 .h 头文件和 .c 源文件',
                'code_preview': preview,
                **base_metadata
            })
        else:
            code = generate_parser_code(gen_config)
            filename = f'{base_filename}.py'
            
            # 保存文件
            output_path = os.path.join(OUTPUT_DIR, filename)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            return jsonify({
                'success': True,
                'message': 'Python 代码生成成功',
                'language': 'python',
                'filename': filename,
                'file_description': 'Python 解析脚本，支持 Excel 导出',
                'code_preview': code[:2000] + '...' if len(code) > 2000 else code,
                **base_metadata
            })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': 'server_error',
            'suggestion': '服务器内部错误，请稍后重试或联系管理员',
            'traceback': traceback.format_exc()
        }), 500


# ============================================================
# 协议文件导入 API
# ============================================================

@app.route('/api/protocol_import/upload', methods=['POST'])
@operator_required
def api_protocol_import_upload():
    """上传协议文件（需要设备人员或管理员权限）"""
    from protocol_importer import handle_file_upload
    
    username = get_current_user()['username']
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有上传文件'}), 400
    
    file = request.files['file']
    
    if not file.filename:
        return jsonify({'success': False, 'error': '文件名为空'}), 400
    
    try:
        draft_id, draft_info = handle_file_upload(file, username)
        return jsonify({
            'success': True,
            'draft_id': draft_id,
            'draft': draft_info,
            'message': f'文件上传成功，草稿ID: {draft_id}'
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/protocol_import/parse/<draft_id>', methods=['POST'])
@operator_required
def api_protocol_import_parse(draft_id):
    """解析上传的协议文件（需要设备人员或管理员权限）"""
    from protocol_importer import process_draft
    
    try:
        data = request.get_json() or {}
        use_llm = data.get('use_llm', True)
        protocol_type = data.get('protocol_type', '429')  # 协议类型：429, 422, CAN
        
        draft = process_draft(draft_id, use_llm=use_llm, protocol_type=protocol_type)
        
        return jsonify({
            'success': True,
            'draft': draft,
            'message': '解析完成'
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/protocol_import/drafts', methods=['GET'])
@login_required
def api_protocol_import_list_drafts():
    """获取草稿列表"""
    from protocol_importer import list_drafts
    
    username = get_current_user()['username']
    status = request.args.get('status')
    
    # 管理员可以看所有草稿
    if is_admin():
        drafts = list_drafts(status=status)
    else:
        drafts = list_drafts(username=username, status=status)
    
    return jsonify({
        'success': True,
        'drafts': drafts
    })


@app.route('/api/protocol_import/draft/<draft_id>', methods=['GET'])
@login_required
def api_protocol_import_get_draft(draft_id):
    """获取单个草稿详情"""
    from protocol_importer import get_draft
    
    draft = get_draft(draft_id)
    
    if not draft:
        return jsonify({'success': False, 'error': '草稿不存在'}), 404
    
    # 权限检查
    username = get_current_user()['username']
    if not is_admin() and draft.get('created_by') != username:
        return jsonify({'success': False, 'error': '无权访问'}), 403
    
    return jsonify({
        'success': True,
        'draft': draft
    })


@app.route('/api/protocol_import/draft/<draft_id>/labels', methods=['PUT'])
@operator_required
def api_protocol_import_update_labels(draft_id):
    """更新草稿的 Labels（需要设备人员或管理员权限）"""
    from protocol_importer import update_draft_labels, get_draft
    
    draft = get_draft(draft_id)
    if not draft:
        return jsonify({'success': False, 'error': '草稿不存在'}), 404
    
    # 权限检查
    username = get_current_user()['username']
    if not is_admin() and draft.get('created_by') != username:
        return jsonify({'success': False, 'error': '无权修改'}), 403
    
    try:
        data = request.get_json()
        labels = data.get('labels', [])
        
        updated_draft = update_draft_labels(draft_id, labels)
        
        return jsonify({
            'success': True,
            'draft': updated_draft,
            'message': 'Labels 已更新'
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/protocol_import/draft/<draft_id>/meta', methods=['PUT'])
@operator_required
def api_protocol_import_update_meta(draft_id):
    """更新草稿的元信息（需要设备人员或管理员权限）"""
    from protocol_importer import update_draft_meta, get_draft
    
    draft = get_draft(draft_id)
    if not draft:
        return jsonify({'success': False, 'error': '草稿不存在'}), 404
    
    # 权限检查
    username = get_current_user()['username']
    if not is_admin() and draft.get('created_by') != username:
        return jsonify({'success': False, 'error': '无权修改'}), 403
    
    try:
        data = request.get_json()
        protocol_meta = data.get('protocol_meta')
        device_info = data.get('device_info')
        
        updated_draft = update_draft_meta(draft_id, protocol_meta, device_info)
        
        return jsonify({
            'success': True,
            'draft': updated_draft,
            'message': '元信息已更新'
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/protocol_import/draft/<draft_id>/confirm', methods=['POST'])
@operator_required
def api_protocol_import_confirm(draft_id):
    """确认草稿并入库（需要设备人员或管理员权限）"""
    from protocol_importer import confirm_draft, get_draft
    
    draft = get_draft(draft_id)
    if not draft:
        return jsonify({'success': False, 'error': '草稿不存在'}), 404
    
    # 权限检查
    username = get_current_user()['username']
    if not is_admin() and draft.get('created_by') != username:
        return jsonify({'success': False, 'error': '无权操作'}), 403
    
    try:
        data = request.get_json() or {}
        
        result = confirm_draft(
            draft_id,
            device_id=data.get('device_id'),
            device_name=data.get('device_name'),
            system_id=data.get('system_id'),
            system_name=data.get('system_name'),
            version_name=data.get('version_name'),
            username=username
        )
        
        return jsonify({
            'success': True,
            'result': result,
            'message': f"已入库到设备 {result['device_name']}，版本 {result['version_name']}，共 {result['label_count']} 个 Label"
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/protocol_import/draft/<draft_id>', methods=['DELETE'])
@operator_required
def api_protocol_import_delete_draft(draft_id):
    """删除草稿（需要设备人员或管理员权限）"""
    from protocol_importer import delete_draft, get_draft
    
    draft = get_draft(draft_id)
    if not draft:
        return jsonify({'success': False, 'error': '草稿不存在'}), 404
    
    # 权限检查
    username = get_current_user()['username']
    if not is_admin() and draft.get('created_by') != username:
        return jsonify({'success': False, 'error': '无权删除'}), 403
    
    success = delete_draft(draft_id)
    
    if success:
        return jsonify({'success': True, 'message': '草稿已删除'})
    else:
        return jsonify({'success': False, 'error': '删除失败'}), 500


def init_git_storage():
    """初始化 Git 存储
    
    如果 Git 仓库目录为空，则从数据库导出数据
    """
    from git_storage import GitStorageConfig, get_repo_manager
    from git_storage.db_exporter import export_database_to_git
    
    config = GitStorageConfig()
    repo_manager = get_repo_manager()
    
    # 确保仓库根目录存在
    repo_manager.ensure_repos_root()
    
    # 检查是否已有 ATA 仓库
    repos_root = config.repos_root
    existing_repos = []
    if os.path.exists(repos_root):
        for name in os.listdir(repos_root):
            # 仓库目录名格式为 protocol-ataXX
            if name.startswith('protocol-') and os.path.isdir(os.path.join(repos_root, name)):
                existing_repos.append(name)
    
    if not existing_repos:
        print('Git 仓库为空，从数据库导出数据...')
        try:
            stats = export_database_to_git(dry_run=False)
            print(f'导出完成: {stats.get("devices_exported", 0)} 个设备')
        except Exception as e:
            print(f'导出失败: {e}')
            import traceback
            traceback.print_exc()
    else:
        print(f'Git 存储已初始化，发现 {len(existing_repos)} 个 ATA 仓库')


if __name__ == '__main__':
    import os
    
    # 检测是否在 Docker 中运行
    in_docker = os.path.exists('/.dockerenv')
    
    print('=' * 60)
    print('接口代码生成平台')
    print('=' * 60)
    print(f'输出目录: {OUTPUT_DIR}')
    print(f'默认管理员账户: admin / admin123')
    
    # 初始化 Git 存储
    print()
    print('初始化 Git 存储...')
    init_git_storage()
    print()
    
    if in_docker:
        print('运行环境: Docker 容器')
        print('访问地址: http://localhost:5001')
        app.run(debug=False, host='0.0.0.0', port=5000)  # Docker 内部用 5000，映射到外部 5001
    else:
        print('运行环境: 本地')
        print('访问地址: http://127.0.0.1:5001')
        print('=' * 60)
        app.run(debug=True, host='127.0.0.1', port=5001)

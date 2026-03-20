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
    login_required, admin_required, get_current_user, is_logged_in, is_admin,
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
    db_delete_device, db_get_version_history, db_get_version_snapshot, 
    db_save_user_config, db_get_user_config, migrate_from_json
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


@app.route('/api/add_device', methods=['POST'])
@login_required
def api_add_device():
    """添加新设备到设备树"""
    try:
        data = request.get_json()
        parent_id = data.get('parent_id')  # 父节点的 device_id
        device_number = data.get('device_number', '').strip()  # 如 32-4
        device_name = data.get('device_name', '').strip()  # 如 新控制单元
        
        if not parent_id:
            return jsonify({'success': False, 'error': '请选择所属系统'}), 400
        if not device_number:
            return jsonify({'success': False, 'error': '请输入设备协议编号'}), 400
        if not device_name:
            return jsonify({'success': False, 'error': '请输入设备协议名称'}), 400
        
        # 获取父节点信息
        parent_device = db_get_device(parent_id)
        
        if not parent_device:
            return jsonify({'success': False, 'error': '父节点不存在'}), 404
        
        # 生成新设备的 device_id
        # 从父节点的 device_id 提取前缀，如 ata32 -> ata32_32_4
        parent_device_id = parent_device.get('device_id', '')
        # 将设备编号中的 - 替换为 _，如 32-4 -> 32_4
        device_number_normalized = device_number.replace('-', '_')
        new_device_id = f"{parent_device_id}_{device_number_normalized}"
        
        # 检查设备 ID 是否已存在
        existing = db_get_device(new_device_id)
        if existing:
            return jsonify({'success': False, 'error': f'设备 ID "{new_device_id}" 已存在'}), 400
        
        # 组合完整设备名称: 编号-名称
        full_name = f"{device_number}-{device_name}"
        
        # 创建新设备
        new_id = db_create_device(
            device_id=new_device_id,
            name=full_name,
            parent_id=parent_device['id'],  # 使用数据库主键作为 parent_id
            is_device=True,
            device_version='V1.0'
        )
        
        if new_id:
            return jsonify({
                'success': True,
                'message': f'设备协议 "{full_name}" 添加成功',
                'device_id': new_device_id
            })
        else:
            return jsonify({'success': False, 'error': '创建设备失败，可能设备 ID 已存在'}), 400
            
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/device/<device_id>', methods=['DELETE'])
@login_required
def api_delete_device(device_id):
    """删除设备协议"""
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
    username = get_current_user()['username']
    
    try:
        # 优先从数据库获取
        device_tree = get_device_tree_from_db()
        user_config = db_get_user_config(username)
        protocol_meta = user_config.get('protocol_meta', {})
        
        if device_tree:
            # 为每个设备节点填充 labels
            def fill_labels(nodes):
                for node in nodes:
                    if node.get('is_device'):
                        device_id = node.get('device_id') or node.get('id')
                        if device_id:
                            node['labels'] = db_get_labels(device_id)
                            node['version_history'] = db_get_version_history(device_id)
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
    """获取指定设备的 labels
    
    Query params:
        version: 可选，指定历史版本号（如 V1.0, V2.0）
        protocol_version: 可选，指定协议版本名称（如 "转弯系统ARINC429通讯协议-V5.0"）
    """
    requested_version = request.args.get('version', None)
    requested_protocol_version = request.args.get('protocol_version', None)
    
    try:
        # 从数据库获取设备信息
        device = db_get_device(device_id)
        
        if not device:
            return jsonify({'success': False, 'error': '设备不存在'}), 404
        
        device_pk = device['id']
        
        # 从数据库获取设备的协议版本列表
        protocol_versions = []
        protocol_version_id = None
        current_protocol_version_name = device.get('current_version_name', '')
        
        try:
            from database import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, version_name, version FROM device_protocol_versions 
                    WHERE device_id = ? ORDER BY version_name
                ''', (device_pk,))
                rows = cursor.fetchall()
                for row in rows:
                    ver_info = {'id': row[0], 'name': row[1], 'version': row[2]}
                    protocol_versions.append(ver_info)
                    
                    # 确定当前协议版本ID
                    if requested_protocol_version:
                        if row[1] == requested_protocol_version:
                            protocol_version_id = row[0]
                            current_protocol_version_name = row[1]
                    elif row[1] == current_protocol_version_name:
                        protocol_version_id = row[0]
        except Exception as e:
            import traceback
            print(f"获取协议版本失败: {e}")
            traceback.print_exc()
        
        # 如果指定了协议版本但未找到，使用第一个版本
        if requested_protocol_version and protocol_version_id is None and protocol_versions:
            protocol_version_id = protocol_versions[0]['id']
            current_protocol_version_name = protocol_versions[0]['name']
        
        # 如果没有当前版本但有版本列表，使用第一个
        if protocol_version_id is None and protocol_versions:
            protocol_version_id = protocol_versions[0]['id']
            current_protocol_version_name = protocol_versions[0]['name']
        
        # 获取指定协议版本的 labels
        labels = db_get_labels(device_id, protocol_version_id)
        
        # 获取版本历史
        version_history = db_get_version_history(device_id)
        
        current_ver = device.get('device_version', 'V1.0')
        
        # 构建可切换的版本列表（保存的历史版本）
        saved_versions = [{
            'version': current_ver,
            'label_count': len(labels),
            'is_current': True,
            'updated_at': datetime.now().isoformat()
        }]
        
        for record in version_history:
            if record.get('version', '') == current_ver:
                continue
            saved_versions.append({
                'version': record.get('version', ''),
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
            snapshot = db_get_version_snapshot(device_id, requested_version)
            if snapshot:
                labels_to_return = snapshot
                viewing_version = requested_version
                is_viewing_history = True
        
        return jsonify({
            'success': True,
            'device_id': device_id,
            'device_name': device.get('name', ''),
            'device_version': current_ver,
            'device_description': device.get('description', ''),
            'viewing_version': viewing_version,
            'is_viewing_history': is_viewing_history,
            'current_version_name': current_protocol_version_name,
            'current_protocol_version_id': protocol_version_id,
            'protocol_versions': [{'name': v['name'], 'version': v['version'], 'id': v['id']} for v in protocol_versions],
            'saved_versions': saved_versions,
            'labels': labels_to_return,
            'version_history': version_history[:20]
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<device_id>/labels', methods=['POST'])
@login_required
def api_save_device_labels(device_id):
    """保存设备的 labels（带版本管理和协议版本支持）
    
    版本管理逻辑：
    - 每次保存会创建新版本（如 V5.0 -> V6.0 -> V7.0）
    - 旧版本的 Labels 会保存到 version_history 的 label_snapshot 字段
    - 可以通过版本历史查看和恢复旧版本
    """
    username = get_current_user()['username']
    
    try:
        data = request.get_json()
        new_labels = data.get('labels', [])
        new_version = data.get('new_version')
        change_summary = data.get('change_summary')
        new_description = data.get('description', '')
        protocol_version_id = data.get('protocol_version_id')
        protocol_version_name = data.get('protocol_version_name', '')
        
        # 从数据库获取设备
        device = db_get_device(device_id)
        
        if not device:
            return jsonify({'success': False, 'error': '设备不存在'}), 404
        
        if not device.get('is_device'):
            return jsonify({'success': False, 'error': '该节点不是设备节点'}), 400
        
        # 【重要】先获取旧的 labels，用于版本历史记录
        old_labels = db_get_labels(device_id, protocol_version_id)
        current_version = device.get('device_version', 'V1.0')
        
        # 构建节点用于版本管理
        node = {
            'id': device_id,
            'device_id': device_id,
            'device_version': current_version,
            'labels': old_labels,
            'version_history': db_get_version_history(device_id)
        }
        
        # 更新设备版本（会将旧版本保存到历史记录，并保存新 Labels）
        # save_labels=True 表示在 update_device_version 内部保存 Labels
        # protocol_version_id 确保 Labels 保存到正确的协议版本
        changed, version = update_device_version(
            node, new_labels, username, new_version, change_summary,
            save_labels=True, protocol_version_id=protocol_version_id
        )
        
        # 更新设备的当前协议版本名
        if protocol_version_name:
            from database import db_update_device
            db_update_device(device_id, current_version_name=protocol_version_name)
        
        # 更新描述
        if new_description is not None:
            from database import db_update_device
            db_update_device(device_id, description=new_description)
        
        # 获取最新的版本历史
        version_history = db_get_version_history(device_id)
        
        return jsonify({
            'success': True,
            'changed': changed,
            'new_version': version,
            'device_version': version,
            'version_history': version_history[:10],
            'message': f'保存成功，当前版本: {version}' + (' (版本已更新)' if changed else '')
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/device/<device_id>/version_history')
@login_required
def api_get_device_version_history(device_id):
    """获取设备的版本历史"""
    try:
        device = db_get_device(device_id)
        
        if not device:
            return jsonify({'success': False, 'error': '设备不存在'}), 404
        
        version_history = db_get_version_history(device_id)
        
        return jsonify({
            'success': True,
            'device_id': device_id,
            'device_name': device.get('name', ''),
            'current_version': device.get('device_version', 'V1.0'),
            'version_history': version_history
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<device_id>/compare_versions')
@login_required
def api_compare_versions(device_id):
    """对比两个版本的 Labels 差异"""
    try:
        device = db_get_device(device_id)
        if not device:
            return jsonify({'success': False, 'error': '设备不存在'}), 404
        
        version_a = request.args.get('version_a', '')
        version_b = request.args.get('version_b', '')
        
        if not version_a or not version_b:
            return jsonify({'success': False, 'error': '需要指定两个版本进行对比'}), 400
        
        current_ver = device.get('device_version', 'V1.0')
        
        # 获取版本 A 的 Labels
        if version_a == current_ver:
            labels_a = db_get_labels(device_id)
        else:
            labels_a = db_get_version_snapshot(device_id, version_a)
            if labels_a is None:
                return jsonify({'success': False, 'error': f'版本 {version_a} 不存在'}), 404
        
        # 获取版本 B 的 Labels
        if version_b == current_ver:
            labels_b = db_get_labels(device_id)
        else:
            labels_b = db_get_version_snapshot(device_id, version_b)
            if labels_b is None:
                return jsonify({'success': False, 'error': f'版本 {version_b} 不存在'}), 404
        
        # 计算差异
        diff = compute_labels_diff(labels_a, labels_b, version_a, version_b)
        
        return jsonify({
            'success': True,
            'device_id': device_id,
            'device_name': device.get('name', ''),
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
    """为指定设备生成代码"""
    username = get_current_user()['username']
    
    try:
        data = request.get_json() or {}
        lang = data.get('lang', 'python')
        protocol_version_id = data.get('protocol_version_id')
        
        # 从数据库获取设备信息
        device = db_get_device(device_id)
        
        if not device:
            return jsonify({'success': False, 'error': '设备不存在'}), 404
        
        if not device.get('is_device'):
            return jsonify({'success': False, 'error': '该节点不是设备节点'}), 400
        
        # 获取设备的 labels（从数据库）
        labels = db_get_labels(device_id, protocol_version_id)
        
        if not labels:
            return jsonify({'success': False, 'error': '该设备没有定义任何 Label，请先添加 Labels'}), 400
        
        # 获取用户配置中的协议元信息
        user_config = db_get_user_config(username)
        protocol_meta = user_config.get('protocol_meta', {}) if user_config else {}
        
        # 构建生成用的配置
        gen_config = {
            'protocol_meta': {
                'name': f"{protocol_meta.get('name', '')} - {device.get('name', '')}",
                'version': device.get('device_version', 'V1.0'),
                'description': f"设备: {device.get('name', '')}"
            },
            'labels': labels
        }
        
        # 验证配置 (跳过空 label_oct)
        errors = validate_config(gen_config, labels, skip_empty_labels=True)
        if errors:
            return jsonify({'success': False, 'errors': errors}), 400
        
        # 生成文件名
        device_name = device.get('name', 'device')
        safe_name = ''.join(c for c in device_name if c.isalnum() or c in '_ -').strip()
        if not safe_name:
            safe_name = 'device'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f'{safe_name}_parser_{timestamp}_{username}'
        
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
                'message': 'C 代码生成成功 (包含 .h 和 .c 文件)',
                'filename': zip_filename,
                'files': [f'{base_filename}.h', f'{base_filename}.c'],
                'code_preview': preview
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
                'filename': filename,
                'code_preview': code[:2000] + '...' if len(code) > 2000 else code
            })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


if __name__ == '__main__':
    import os
    
    # 检测是否在 Docker 中运行
    in_docker = os.path.exists('/.dockerenv')
    
    print('=' * 60)
    print('接口代码生成平台')
    print('=' * 60)
    print(f'输出目录: {OUTPUT_DIR}')
    print(f'默认管理员账户: admin / admin123')
    
    if in_docker:
        print('运行环境: Docker 容器')
        print('访问地址: http://localhost:5001')
        app.run(debug=False, host='0.0.0.0', port=5000)  # Docker 内部用 5000，映射到外部 5001
    else:
        print('运行环境: 本地')
        print('访问地址: http://127.0.0.1:5001')
        print('=' * 60)
        app.run(debug=True, host='127.0.0.1', port=5001)

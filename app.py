# -*- coding: utf-8 -*-
"""
ARINC429 协议代码生成平台 - Flask Web 应用
用户通过网页表单填写协议变量部分，自动生成 Python 解析脚本
"""

import os
import json
import sys
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response
from io import BytesIO
import zipfile

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generator_core import generate_parser_code, generate_c_parser_code, validate_config

app = Flask(__name__)
app.config['SECRET_KEY'] = 'arinc429-generator-secret-key'

# 存储目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 用户配置保存目录
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# 当前工作配置文件路径
CURRENT_CONFIG_PATH = os.path.join(DATA_DIR, 'current_config.json')


@app.route('/')
def index():
    """主页 - 协议配置表单"""
    return render_template('index.html')


@app.route('/api/validate', methods=['POST'])
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
        filename = f'{safe_name}_parser_{timestamp}.py'
        
        # 保存到输出目录
        output_path = os.path.join(OUTPUT_DIR, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # 同时保存配置文件
        config_filename = f'{safe_name}_config_{timestamp}.json'
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
def api_download(filename):
    """下载生成的文件"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': '文件不存在'}), 404


@app.route('/api/download_zip', methods=['POST'])
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
def api_load_example():
    """加载示例配置"""
    example_path = os.path.join(os.path.dirname(__file__), 'example_protocol_config.json')
    if os.path.exists(example_path):
        with open(example_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return jsonify(config)
    return jsonify({'error': '示例文件不存在'}), 404


@app.route('/api/save_config', methods=['POST'])
def api_save_config():
    """保存当前配置到服务器（持久化）"""
    try:
        config = request.get_json()
        
        # 保存到当前工作配置文件
        with open(CURRENT_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': '配置已保存',
            'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/load_config')
def api_load_config():
    """加载上次保存的配置"""
    if os.path.exists(CURRENT_CONFIG_PATH):
        try:
            with open(CURRENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
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
def api_list_saved_configs():
    """列出所有保存的配置文件"""
    configs = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
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
def api_save_config_as():
    """另存配置为指定名称"""
    try:
        data = request.get_json()
        config = data.get('config')
        name = data.get('name', 'unnamed')
        
        # 清理文件名
        safe_name = ''.join(c for c in name if c.isalnum() or c in '_ -中文').strip()
        if not safe_name:
            safe_name = 'config'
        
        filename = f'{safe_name}.json'
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
def api_load_saved_config(filename):
    """加载指定的配置文件"""
    filepath = os.path.join(DATA_DIR, filename)
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
def api_delete_saved_config(filename):
    """删除指定的配置文件"""
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            return jsonify({'success': True, 'message': f'已删除 {filename}'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': False, 'error': '配置文件不存在'}), 404


@app.route('/api/preview_code', methods=['POST'])
def api_preview_code():
    """实时预览生成的代码"""
    try:
        config = request.get_json()
        lang = request.args.get('lang', 'python')
        if lang == 'c':
            code = generate_c_parser_code(config)
        else:
            code = generate_parser_code(config)
        return jsonify({'success': True, 'code': code})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/generate_c', methods=['POST'])
def api_generate_c():
    """生成 C 语言解析代码"""
    try:
        config = request.get_json()
        
        # 验证配置
        errors = validate_config(config)
        if errors:
            return jsonify({'success': False, 'errors': errors}), 400
        
        # 生成 C 代码
        code = generate_c_parser_code(config)
        
        # 生成文件名
        protocol_name = config.get('protocol_meta', {}).get('name', 'protocol')
        safe_name = ''.join(c for c in protocol_name if c.isalnum() or c in '_ -').strip()
        if not safe_name:
            safe_name = 'protocol'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{safe_name}_parser_{timestamp}.c'
        
        # 保存到输出目录
        output_path = os.path.join(OUTPUT_DIR, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        return jsonify({
            'success': True,
            'message': 'C代码生成成功',
            'filename': filename,
            'code_preview': code[:2000] + '...' if len(code) > 2000 else code
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False, 
            'errors': [str(e)],
            'traceback': traceback.format_exc()
        }), 500


if __name__ == '__main__':
    import os
    
    # 检测是否在 Docker 中运行
    in_docker = os.path.exists('/.dockerenv')
    
    print('=' * 60)
    print('ARINC429 协议代码生成平台')
    print('=' * 60)
    print(f'输出目录: {OUTPUT_DIR}')
    
    if in_docker:
        print('运行环境: Docker 容器')
        print('访问地址: http://localhost:5000')
        app.run(debug=False, host='0.0.0.0', port=5000)
    else:
        print('运行环境: 本地')
        print('访问地址: http://127.0.0.1:5000')
        print('=' * 60)
        app.run(debug=True, host='127.0.0.1', port=5000)

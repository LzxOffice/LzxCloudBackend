# 导入需要的工具库
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
import os
from datetime import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

# 初始化 Flask 应用
app = Flask(__name__)
app.secret_key = 'LzxCloud_2026_very_secret_key'  # 可自定义

# 设置文件上传的根文件夹
BASE_UPLOAD_FOLDER = 'uploads'
app.config['BASE_UPLOAD_FOLDER'] = BASE_UPLOAD_FOLDER

# 初始化文件夹和数据库
def init_app():
    # 创建根上传文件夹
    if not os.path.exists(BASE_UPLOAD_FOLDER):
        os.makedirs(BASE_UPLOAD_FOLDER)
    # 初始化数据库
    init_db()

# 初始化数据库（创建用户表）
def init_db():
    conn = sqlite3.connect('lzxcloud.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# 登录验证装饰器
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# 注册页面
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if not username or not password:
            flash('用户名和密码不能为空！')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        try:
            conn = sqlite3.connect('lzxcloud.db')
            c = conn.cursor()
            c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            conn.close()
            flash('注册成功！请登录')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('用户名已存在！换一个试试')
            return redirect(url_for('register'))
    
    return render_template('register.html', title='LzxCloud - 注册')

# 登录页面
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('lzxcloud.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['username'] = username
            flash('登录成功！欢迎回来')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误！')
            return redirect(url_for('login'))
    
    return render_template('login.html', title='LzxCloud - 登录')

# 退出登录
@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('已退出登录')
    return redirect(url_for('login'))

# 主页：支持文件夹浏览（修复404，允许空路径）
@app.route('/')
@app.route('/folder/')
@app.route('/folder/<path:folder_path>')
@login_required
def index(folder_path=''):
    current_user = session.get('username')
    # 拼接当前文件夹的完整路径
    current_folder = os.path.join(BASE_UPLOAD_FOLDER, folder_path)
    
    # 确保文件夹存在
    if not os.path.exists(current_folder):
        os.makedirs(current_folder)
    
    # 获取当前文件夹下的所有文件和子文件夹
    items = []
    # 先获取文件夹
    for item in os.listdir(current_folder):
        item_path = os.path.join(current_folder, item)
        item_rel_path = os.path.join(folder_path, item) if folder_path else item
        
        if os.path.isdir(item_path):
            # 文件夹
            items.append({
                'type': 'folder',
                'name': item,
                'path': item_rel_path,
                'time': datetime.fromtimestamp(os.path.getctime(item_path)).strftime('%Y-%m-%d %H:%M')
            })
        else:
            # 文件
            file_size = os.path.getsize(item_path) / 1024
            items.append({
                'type': 'file',
                'name': item,
                'path': item_rel_path,
                'size': round(file_size, 2),
                'time': datetime.fromtimestamp(os.path.getctime(item_path)).strftime('%Y-%m-%d %H:%M')
            })
    
    # 按类型排序：文件夹在前，文件在后
    items.sort(key=lambda x: (x['type'] != 'folder', x['name']))
    
    # 面包屑导航（返回上级文件夹用）
    breadcrumbs = []
    if folder_path:
        parts = folder_path.split(os.sep)
        current_path = ''
        for part in parts:
            current_path = os.path.join(current_path, part) if current_path else part
            breadcrumbs.append({
                'name': part,
                'path': current_path
            })
    
    return render_template(
        'index.html', 
        items=items, 
        title='LzxCloud 个人网盘', 
        user=current_user,
        current_folder=folder_path,
        breadcrumbs=breadcrumbs
    )

# 上传文件（支持上传到指定文件夹）
@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    folder_path = request.form.get('folder_path', '')
    current_folder = os.path.join(BASE_UPLOAD_FOLDER, folder_path)
    
    if 'file' not in request.files:
        return redirect(url_for('index', folder_path=folder_path))
    
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index', folder_path=folder_path))
    
    if file:
        filepath = os.path.join(current_folder, file.filename)
        file.save(filepath)
        flash(f'文件「{file.filename}」上传成功！')
    
    return redirect(url_for('index', folder_path=folder_path))

# 创建文件夹（优化：创建后自动跳转新文件夹）
@app.route('/create_folder', methods=['POST'])
@login_required
def create_folder():
    folder_path = request.form.get('folder_path', '')
    folder_name = request.form.get('folder_name', '').strip()
    
    if not folder_name:
        flash('文件夹名称不能为空！')
        return redirect(url_for('index', folder_path=folder_path))
    
    # 拼接新文件夹路径
    new_folder = os.path.join(BASE_UPLOAD_FOLDER, folder_path, folder_name)
    # 拼接新文件夹的相对路径（用于跳转）
    new_folder_rel_path = os.path.join(folder_path, folder_name) if folder_path else folder_name
    
    if os.path.exists(new_folder):
        flash('文件夹已存在！')
        return redirect(url_for('index', folder_path=folder_path))
    
    os.makedirs(new_folder)
    flash(f'文件夹「{folder_name}」创建成功！')
    # 关键优化：跳转到新创建的文件夹页面
    return redirect(url_for('index', folder_path=new_folder_rel_path))

# 删除文件夹/文件
@app.route('/delete/<path:item_path>')
@login_required
def delete_item(item_path):
    # 获取当前文件夹路径（用于删除后返回）
    folder_path = os.path.dirname(item_path)
    # 拼接完整路径
    full_path = os.path.join(BASE_UPLOAD_FOLDER, item_path)
    item_name = os.path.basename(item_path)
    
    if os.path.exists(full_path):
        if os.path.isdir(full_path):
            # 删除文件夹（递归删除所有内容）
            import shutil
            shutil.rmtree(full_path)
            flash(f'文件夹「{item_name}」已删除！')
        else:
            # 删除文件
            os.remove(full_path)
            flash(f'文件「{item_name}」已删除！')
    
    return redirect(url_for('index', folder_path=folder_path))

# 重命名文件夹/文件（优化：重命名后停留在当前文件夹）
@app.route('/rename', methods=['POST'])
@login_required
def rename_item():
    item_path = request.form.get('item_path', '')
    new_name = request.form.get('new_name', '').strip()
    folder_path = os.path.dirname(item_path)
    old_name = os.path.basename(item_path)
    
    if not new_name:
        flash('新名称不能为空！')
        return redirect(url_for('index', folder_path=folder_path))
    
    # 拼接原路径和新路径
    old_path = os.path.join(BASE_UPLOAD_FOLDER, item_path)
    new_path = os.path.join(BASE_UPLOAD_FOLDER, folder_path, new_name)
    
    if os.path.exists(new_path):
        flash('名称已存在！')
        return redirect(url_for('index', folder_path=folder_path))
    
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        flash(f'已重命名为「{new_name}」！')
    
    # 重命名后仍停留在当前文件夹
    return redirect(url_for('index', folder_path=folder_path))

# 下载文件
@app.route('/download/<path:file_path>')
@login_required
def download_file(file_path):
    # 分离文件夹和文件名
    folder = os.path.dirname(os.path.join(BASE_UPLOAD_FOLDER, file_path))
    filename = os.path.basename(file_path)
    return send_from_directory(folder, filename, as_attachment=True)

# 初始化并运行
if __name__ == '__main__':
    init_app()
    app.run(debug=True, host='0.0.0.0')

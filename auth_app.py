import gradio as gr
import sqlite3
import hashlib
import random
import time
from datetime import datetime, timedelta
from service import Service

# 初始化数据库
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'user',
            status TEXT DEFAULT 'active',
            mfa_enabled INTEGER DEFAULT 0,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            code TEXT NOT NULL,
            code_type TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            success INTEGER NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            logout_time TIMESTAMP,
            session_duration INTEGER
        )
    ''')
    
    # 创建默认管理员账户（如果不存在）
    cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', ('admin',))
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO users (username, password, email, role, mfa_enabled)
            VALUES (?, ?, ?, ?, ?)
        ''', ('admin', hash_password('admin123'), 'admin@system.com', 'admin', 0))
        print("默认管理员账户已创建: username=admin, password=admin123")
    
    conn.commit()
    conn.close()

# 密码加密
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# 生成验证码
def generate_verification_code():
    return str(random.randint(100000, 999999))

# 发送验证码（模拟）
def send_verification_code(username, code_type='login'):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # 生成6位数字验证码
        code = generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=5)
        
        # 保存验证码
        cursor.execute('''
            INSERT INTO verification_codes (username, code, code_type, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (username, code, code_type, expires_at))
        conn.commit()
        conn.close()
        
        # 在终端显示验证码
        print(f"\n{'='*50}")
        print(f"[验证码] 用户: {username}")
        print(f"[验证码] 代码: {code}")
        print(f"[验证码] 有效期: 5分钟")
        print(f"{'='*50}\n")
        
        return True, "验证码已发送，请查看终端获取验证码"
    except Exception as e:
        return False, f"发送验证码失败：{str(e)}"

# 验证验证码
def verify_code(username, code, code_type='login'):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, expires_at FROM verification_codes
            WHERE username = ? AND code = ? AND code_type = ? AND used = 0
            ORDER BY created_at DESC LIMIT 1
        ''', (username, code, code_type))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False, "验证码错误或已使用"
        
        code_id, expires_at = result
        expires_time = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S.%f')
        
        if datetime.now() > expires_time:
            conn.close()
            return False, "验证码已过期"
        
        # 标记验证码为已使用
        cursor.execute('UPDATE verification_codes SET used = 1 WHERE id = ?', (code_id,))
        conn.commit()
        conn.close()
        
        return True, "验证成功"
    except Exception as e:
        return False, f"验证失败：{str(e)}"

# 检查登录尝试次数
def check_login_attempts(username, max_attempts=5, time_window=15):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        time_threshold = datetime.now() - timedelta(minutes=time_window)
        cursor.execute('''
            SELECT COUNT(*) FROM login_logs
            WHERE username = ? AND success = 0 AND login_time > ?
        ''', (username, time_threshold))
        
        failed_attempts = cursor.fetchone()[0]
        conn.close()
        
        if failed_attempts >= max_attempts:
            return False, f"登录失败次数过多，请{time_window}分钟后再试"
        return True, ""
    except Exception as e:
        return True, ""

# 记录登录日志
def log_login(username, success, ip_address='127.0.0.1', user_agent='Gradio App'):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO login_logs (username, success, ip_address, user_agent)
            VALUES (?, ?, ?, ?)
        ''', (username, 1 if success else 0, ip_address, user_agent))
        
        # 如果登录成功，更新用户的最后登录时间
        if success:
            cursor.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP
                WHERE username = ?
            ''', (username,))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"记录登录日志失败: {e}")

# 用户注册
def register_user(username, password, confirm_password, email=''):
    if not username or not password:
        return "用户名和密码不能为空", None
    
    if password != confirm_password:
        return "两次输入的密码不一致", None
    
    if len(password) < 6:
        return "密码长度至少为6位", None
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, password, email, mfa_enabled)
            VALUES (?, ?, ?, ?)
        ''', (username, hash_password(password), email, 1 if email else 0))
        conn.commit()
        conn.close()
        return "注册成功！请登录", None
    except sqlite3.IntegrityError:
        return "用户名已存在", None
    except Exception as e:
        return f"注册失败：{str(e)}", None

# 第一步：验证用户名和密码
def verify_credentials(username, password):
    if not username or not password:
        return "用户名和密码不能为空", None, False, None
    
    # 检查登录尝试次数
    can_attempt, msg = check_login_attempts(username)
    if not can_attempt:
        return msg, None, False, None
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT password, mfa_enabled, role, status FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            log_login(username, False)
            return "用户名或密码错误", None, False, None
        
        stored_password, mfa_enabled, role, status = result
        
        # 检查账户状态
        if status != 'active':
            return f"账户已被{status}，请联系管理员", None, False, None
        
        if stored_password == hash_password(password):
            log_login(username, True)
            
            if mfa_enabled:
                # 需要MFA验证
                return "密码验证成功，请进行二次验证", username, True, role
            else:
                # 不需要MFA，直接登录
                return f"欢迎回来，{username}！", username, False, role
        else:
            log_login(username, False)
            return "用户名或密码错误", None, False, None
    except Exception as e:
        return f"登录失败：{str(e)}", None, False, None

# 用户登录（完整流程）
def login_user(username, password):
    msg, user, needs_mfa, role = verify_credentials(username, password)
    if user and not needs_mfa:
        return msg, user, role
    return msg, None, None

# 获取所有用户列表
def get_all_users():
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT username, email, role, status, mfa_enabled, last_login, created_at
            FROM users ORDER BY created_at DESC
        ''')
        users = cursor.fetchall()
        conn.close()
        
        # 格式化为表格数据
        data = []
        for user in users:
            username, email, role, status, mfa_enabled, last_login, created_at = user
            data.append([
                username,
                email or '未设置',
                '管理员' if role == 'admin' else '普通用户',
                '正常' if status == 'active' else '禁用',
                '已启用' if mfa_enabled else '未启用',
                last_login or '从未登录',
                created_at
            ])
        return data
    except Exception as e:
        print(f"获取用户列表失败: {e}")
        return []

# 获取登录日志
def get_login_logs(limit=50):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT username, success, ip_address, user_agent, login_time
            FROM login_logs ORDER BY login_time DESC LIMIT ?
        ''', (limit,))
        logs = cursor.fetchall()
        conn.close()
        
        data = []
        for log in logs:
            username, success, ip_address, user_agent, login_time = log
            data.append([
                username,
                '成功' if success else '失败',
                ip_address,
                user_agent,
                login_time
            ])
        return data
    except Exception as e:
        print(f"获取登录日志失败: {e}")
        return []

# 更新用户状态
def update_user_status(username, new_status):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET status = ? WHERE username = ?', (new_status, username))
        conn.commit()
        conn.close()
        return f"用户 {username} 状态已更新为: {new_status}"
    except Exception as e:
        return f"更新失败: {str(e)}"

# 删除用户
def delete_user(username):
    if username == 'admin':
        return "不能删除管理员账户"
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE username = ?', (username,))
        conn.commit()
        conn.close()
        return f"用户 {username} 已删除"
    except Exception as e:
        return f"删除失败: {str(e)}"

# 医疗问答机器人
def doctor_bot(message, history):
    service = Service()
    return service.answer(message, history)

# 创建登录界面
def create_login_interface():
    with gr.Blocks(css="""
        .gradio-container { max-width: 500px !important; margin: 50px auto !important; }
        .title { text-align: center; font-size: 28px; font-weight: bold; margin-bottom: 30px; color: #2c3e50; }
        .tab-label { font-size: 16px; }
    """) as login_demo:
        gr.Markdown("<div class='title'>🏥 医疗问诊系统</div>")
        
        with gr.Tabs():
            # 登录标签页
            with gr.Tab("登录"):
                login_username = gr.Textbox(label="用户名", placeholder="请输入用户名")
                login_password = gr.Textbox(label="密码", type="password", placeholder="请输入密码")
                login_btn = gr.Button("登录", variant="primary", size="lg")
                login_msg = gr.Textbox(label="提示信息", interactive=False)
            
            # 注册标签页
            with gr.Tab("注册"):
                reg_username = gr.Textbox(label="用户名", placeholder="请输入用户名")
                reg_password = gr.Textbox(label="密码", type="password", placeholder="请输入密码（至少6位）")
                reg_confirm = gr.Textbox(label="确认密码", type="password", placeholder="请再次输入密码")
                reg_btn = gr.Button("注册", variant="primary", size="lg")
                reg_msg = gr.Textbox(label="提示信息", interactive=False)
        
        # 登录按钮事件
        login_btn.click(
            fn=login_user,
            inputs=[login_username, login_password],
            outputs=[login_msg, gr.State()]
        ).then(
            fn=lambda msg, state: create_chat_interface() if state else None,
            inputs=[login_msg, gr.State()],
            outputs=None
        )
        
        # 注册按钮事件
        reg_btn.click(
            fn=register_user,
            inputs=[reg_username, reg_password, reg_confirm],
            outputs=[reg_msg, gr.State()]
        )
    
    return login_demo

# 创建聊天界面
def create_chat_interface():
    css = """
    .gradio-container { max-width:850px !important; margin:20px auto !important; } 
    .message { padding: 10px !important; font-size: 14px !important; } 
    """
    
    chat_demo = gr.ChatInterface(
        css=css,
        fn=doctor_bot,
        title='医疗问诊机器人',
        chatbot=gr.Chatbot(height=400, bubble_full_width=False),
        theme=gr.themes.Default(spacing_size='sm', radius_size='sm'),
        textbox=gr.Textbox(placeholder='在此输入您的问题', container=False, scale=7),
        examples=[
            '你好，你叫什么名字？',
            '介绍一下寻医问药网',
            '感冒是一种什么病？',
            '吃什么药好得快？可以吃阿莫西林吗？'
        ],
        submit_btn=gr.Button('提交', variant='primary'),
        clear_btn=gr.Button('清空记录'),
        retry_btn=None,
        undo_btn=None,
    )
    
    return chat_demo

if __name__ == '__main__':
    # 初始化数据库
    init_db()
    
    # 创建主应用
    css = """
    .gradio-container { max-width: 850px !important; margin: 20px auto !important; }
    """
    
    with gr.Blocks(css=css) as app:
        # 用户状态
        user_state = gr.State(None)
        
        # 登录界面
        with gr.Column(visible=True) as login_page:
            gr.Markdown("<div style='text-align: center; font-size: 28px; font-weight: bold; margin: 30px 0; color: #2c3e50;'>🏥 医疗问诊系统</div>")
            
            with gr.Tabs():
                with gr.Tab("登录"):
                    login_username = gr.Textbox(label="用户名", placeholder="请输入用户名")
                    login_password = gr.Textbox(label="密码", type="password", placeholder="请输入密码")
                    login_btn = gr.Button("登录", variant="primary", size="lg")
                    login_msg = gr.Textbox(label="提示信息", interactive=False)
                
                with gr.Tab("注册"):
                    reg_username = gr.Textbox(label="用户名", placeholder="请输入用户名")
                    reg_email = gr.Textbox(label="邮箱（可选，用于多因素认证）", placeholder="example@email.com")
                    reg_password = gr.Textbox(label="密码", type="password", placeholder="至少6位")
                    reg_confirm = gr.Textbox(label="确认密码", type="password", placeholder="请再次输入密码")
                    gr.Markdown("💡 提示：填写邮箱将自动启用多因素认证，增强账户安全性")
                    reg_btn = gr.Button("注册", variant="primary", size="lg")
                    reg_msg = gr.Textbox(label="提示信息", interactive=False)
        
        # MFA验证界面
        with gr.Column(visible=False) as mfa_page:
            gr.Markdown("<div style='text-align: center; font-size: 28px; font-weight: bold; margin: 30px 0; color: #2c3e50;'>🔐 二次验证</div>")
            gr.Markdown("<div style='text-align: center; color: #7f8c8d;'>为了保护您的账户安全，请完成二次验证</div>")
            
            mfa_username_display = gr.Textbox(label="用户名", interactive=False)
            
            with gr.Row():
                send_code_btn = gr.Button("发送验证码到邮箱", variant="secondary")
                mfa_code_msg = gr.Textbox(label="", interactive=False, show_label=False, scale=2)
            
            gr.Markdown("<div style='color: #e67e22; font-size: 14px;'>💡 验证码将显示在运行程序的终端窗口中</div>")
            
            mfa_code_input = gr.Textbox(label="请输入6位验证码", placeholder="000000")
            
            with gr.Row():
                verify_btn = gr.Button("验证", variant="primary", size="lg")
                back_btn = gr.Button("返回登录", size="lg")
            
            mfa_msg = gr.Textbox(label="提示信息", interactive=False)
        
        # 聊天界面
        with gr.Column(visible=False) as chat_page:
            with gr.Row():
                gr.Markdown("<div style='text-align: center; font-size: 24px; font-weight: bold; margin: 20px 0; color: #2c3e50; flex-grow: 1;'>医疗问诊机器人</div>")
                user_role_display = gr.Textbox(value="", visible=False)
                admin_panel_btn = gr.Button("管理面板", size="sm", scale=0, visible=False)
                logout_btn = gr.Button("退出登录", size="sm", scale=0)
            
            chatbot = gr.Chatbot(height=450, bubble_full_width=False)
            msg_input = gr.Textbox(
                placeholder='在此输入您的问题',
                container=False,
                show_label=False
            )
            
            with gr.Row():
                submit_btn = gr.Button('提交', variant='primary')
                clear_btn = gr.Button('清空记录')
            
            gr.Examples(
                examples=[
                    '你好，你叫什么名字？',
                    '介绍一下寻医问药网',
                    '感冒是一种什么病？',
                    '吃什么药好得快？可以吃阿莫西林吗？'
                ],
                inputs=msg_input
            )
        
        # 管理员面板
        with gr.Column(visible=False) as admin_page:
            gr.Markdown("<div style='text-align: center; font-size: 28px; font-weight: bold; margin: 30px 0; color: #2c3e50;'>👨‍💼 管理员面板</div>")
            
            with gr.Tabs():
                with gr.Tab("用户管理"):
                    refresh_users_btn = gr.Button("刷新用户列表", variant="secondary")
                    users_table = gr.Dataframe(
                        headers=["用户名", "邮箱", "角色", "状态", "MFA", "最后登录", "注册时间"],
                        label="用户列表",
                        interactive=False
                    )
                    
                    with gr.Row():
                        manage_username = gr.Textbox(label="用户名", placeholder="输入要管理的用户名")
                        manage_action = gr.Radio(
                            choices=["禁用", "激活", "删除"],
                            label="操作",
                            value="禁用"
                        )
                    
                    manage_btn = gr.Button("执行操作", variant="primary")
                    manage_msg = gr.Textbox(label="操作结果", interactive=False)
                
                with gr.Tab("登录日志"):
                    refresh_logs_btn = gr.Button("刷新日志", variant="secondary")
                    logs_table = gr.Dataframe(
                        headers=["用户名", "状态", "IP地址", "User Agent", "登录时间"],
                        label="登录日志（最近50条）",
                        interactive=False
                    )
            
            back_to_chat_btn = gr.Button("返回聊天", size="lg")
        
        # 临时存储待验证的用户名和角色
        pending_username = gr.State(None)
        pending_role = gr.State(None)
        
        # 登录逻辑
        def handle_login(username, password):
            msg, user, needs_mfa, role = verify_credentials(username, password)
            
            if needs_mfa:
                # 需要MFA验证，跳转到MFA页面
                return (msg, None, 
                       gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
                       username, role, username, "", gr.update(visible=False))
            elif user:
                # 直接登录成功
                is_admin = (role == 'admin')
                return (msg, user,
                       gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), gr.update(visible=False),
                       None, role, "", role, gr.update(visible=is_admin))
            else:
                # 登录失败
                return (msg, None,
                       gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                       None, None, "", "", gr.update(visible=False))
        
        login_btn.click(
            fn=handle_login,
            inputs=[login_username, login_password],
            outputs=[login_msg, user_state, login_page, mfa_page, chat_page, admin_page,
                    pending_username, pending_role, mfa_username_display, user_role_display, admin_panel_btn]
        )
        
        # 发送验证码
        def handle_send_code(username):
            if not username:
                return "请先登录"
            success, msg = send_verification_code(username, 'login')
            return msg
        
        send_code_btn.click(
            fn=handle_send_code,
            inputs=[pending_username],
            outputs=[mfa_code_msg]
        )
        
        # 验证MFA
        def handle_mfa_verify(username, code, role):
            if not username or not code:
                return "请输入验证码", None, gr.update(), gr.update(), gr.update(), gr.update(), "", gr.update(visible=False)
            
            success, msg = verify_code(username, code, 'login')
            if success:
                is_admin = (role == 'admin')
                return f"验证成功！欢迎回来，{username}！", username, \
                       gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), \
                       role, gr.update(visible=is_admin)
            else:
                return msg, None, gr.update(), gr.update(), gr.update(), gr.update(), "", gr.update(visible=False)
        
        verify_btn.click(
            fn=handle_mfa_verify,
            inputs=[pending_username, mfa_code_input, pending_role],
            outputs=[mfa_msg, user_state, login_page, mfa_page, chat_page, admin_page, user_role_display, admin_panel_btn]
        )
        
        # 返回登录
        def handle_back():
            return gr.update(visible=True), gr.update(visible=False), None, ""
        
        back_btn.click(
            fn=handle_back,
            outputs=[login_page, mfa_page, pending_username, mfa_code_input]
        )
        
        # 注册逻辑
        def handle_register(username, email, password, confirm):
            msg, _ = register_user(username, password, confirm, email)
            return msg
        
        reg_btn.click(
            fn=handle_register,
            inputs=[reg_username, reg_email, reg_password, reg_confirm],
            outputs=[reg_msg]
        )
        
        # 管理员面板相关
        def show_admin_panel():
            users_data = get_all_users()
            logs_data = get_login_logs()
            return gr.update(visible=False), gr.update(visible=True), users_data, logs_data
        
        admin_panel_btn.click(
            fn=show_admin_panel,
            outputs=[chat_page, admin_page, users_table, logs_table]
        )
        
        def back_to_chat():
            return gr.update(visible=True), gr.update(visible=False)
        
        back_to_chat_btn.click(
            fn=back_to_chat,
            outputs=[chat_page, admin_page]
        )
        
        def refresh_users():
            return get_all_users()
        
        refresh_users_btn.click(
            fn=refresh_users,
            outputs=[users_table]
        )
        
        def refresh_logs():
            return get_login_logs()
        
        refresh_logs_btn.click(
            fn=refresh_logs,
            outputs=[logs_table]
        )
        
        def manage_user(username, action):
            if not username:
                return "请输入用户名", get_all_users()
            
            if action == "删除":
                msg = delete_user(username)
            elif action == "禁用":
                msg = update_user_status(username, 'disabled')
            elif action == "激活":
                msg = update_user_status(username, 'active')
            else:
                msg = "未知操作"
            
            return msg, get_all_users()
        
        manage_btn.click(
            fn=manage_user,
            inputs=[manage_username, manage_action],
            outputs=[manage_msg, users_table]
        )
        
        # 退出登录
        def handle_logout():
            return None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), []
        
        logout_btn.click(
            fn=handle_logout,
            outputs=[user_state, login_page, mfa_page, chat_page, admin_page, chatbot]
        )
        
        # 聊天逻辑
        def respond(message, chat_history):
            if not message.strip():
                return chat_history, ""
            # 先显示用户消息
            chat_history.append((message, None))
            return chat_history, ""
        
        def generate_response(chat_history):
            if not chat_history or chat_history[-1][1] is not None:
                return chat_history
            
            message = chat_history[-1][0]
            # 获取历史记录（不包括当前这条）
            history = chat_history[:-1]
            bot_message = doctor_bot(message, history)
            chat_history[-1] = (message, bot_message)
            return chat_history
        
        submit_btn.click(
            fn=respond,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, msg_input]
        ).then(
            fn=generate_response,
            inputs=[chatbot],
            outputs=[chatbot]
        )
        
        msg_input.submit(
            fn=respond,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, msg_input]
        ).then(
            fn=generate_response,
            inputs=[chatbot],
            outputs=[chatbot]
        )
        
        clear_btn.click(
            fn=lambda: [],
            outputs=chatbot
        )
    
    app.launch()

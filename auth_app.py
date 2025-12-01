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
                   CREATE TABLE IF NOT EXISTS users
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       username
                       TEXT
                       UNIQUE
                       NOT
                       NULL,
                       password
                       TEXT
                       NOT
                       NULL,
                       email
                       TEXT,
                       role
                       TEXT
                       DEFAULT
                       'user',
                       status
                       TEXT
                       DEFAULT
                       'active',
                       mfa_enabled
                       INTEGER
                       DEFAULT
                       0,
                       warning_count
                       INTEGER
                       DEFAULT
                       0,
                       last_login
                       TIMESTAMP,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   ''')
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS verification_codes
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       username
                       TEXT
                       NOT
                       NULL,
                       code
                       TEXT
                       NOT
                       NULL,
                       code_type
                       TEXT
                       NOT
                       NULL,
                       expires_at
                       TIMESTAMP
                       NOT
                       NULL,
                       used
                       INTEGER
                       DEFAULT
                       0,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   ''')
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS login_logs
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       username
                       TEXT
                       NOT
                       NULL,
                       success
                       INTEGER
                       NOT
                       NULL,
                       ip_address
                       TEXT,
                       user_agent
                       TEXT,
                       login_time
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP,
                       logout_time
                       TIMESTAMP,
                       session_duration
                       INTEGER
                   )
                   ''')
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS qa_records
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       username
                       TEXT
                       NOT
                       NULL,
                       question
                       TEXT
                       NOT
                       NULL,
                       answer
                       TEXT
                       NOT
                       NULL,
                       tool_used
                       TEXT,
                       confidence_score
                       REAL,
                       source_info
                       TEXT,
                       review_status
                       TEXT
                       DEFAULT
                       'pending',
                       reviewer
                       TEXT,
                       review_comment
                       TEXT,
                       review_time
                       TIMESTAMP,
                       is_visible
                       INTEGER
                       DEFAULT
                       1,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   ''')
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS user_warnings
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       username
                       TEXT
                       NOT
                       NULL,
                       qa_record_id
                       INTEGER,
                       warning_reason
                       TEXT,
                       warning_time
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP,
                       is_read
                       INTEGER
                       DEFAULT
                       0
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

    # 创建默认审核员账户（如果不存在）
    cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', ('reviewer',))
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
                       INSERT INTO users (username, password, email, role, mfa_enabled)
                       VALUES (?, ?, ?, ?, ?)
                       ''', ('reviewer', hash_password('reviewer123'), 'reviewer@system.com', 'reviewer', 0))
        print("默认审核员账户已创建: username=reviewer, password=reviewer123")

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
        print(f"\n{'=' * 50}")
        print(f"[验证码] 用户: {username}")
        print(f"[验证码] 代码: {code}")
        print(f"[验证码] 有效期: 5分钟")
        print(f"{'=' * 50}\n")

        return True, "验证码已发送，请查看终端获取验证码"
    except Exception as e:
        return False, f"发送验证码失败：{str(e)}"


# 验证验证码
def verify_code(username, code, code_type='login'):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT id, expires_at
                       FROM verification_codes
                       WHERE username = ?
                         AND code = ?
                         AND code_type = ?
                         AND used = 0
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
                       SELECT COUNT(*)
                       FROM login_logs
                       WHERE username = ?
                         AND success = 0
                         AND login_time > ?
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
                           UPDATE users
                           SET last_login = CURRENT_TIMESTAMP
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


# 获取所有用户列表
def get_all_users():
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
                       SELECT username,
                              email,
                              role,
                              status,
                              mfa_enabled,
                              warning_count,
                              last_login,
                              created_at
                       FROM users
                       ORDER BY created_at DESC
                       ''')
        users = cursor.fetchall()
        conn.close()

        # 格式化为表格数据
        data = []
        for user in users:
            username, email, role, status, mfa_enabled, warning_count, last_login, created_at = user
            role_text = '管理员' if role == 'admin' else ('审核员' if role == 'reviewer' else '普通用户')
            data.append([
                username,
                email or '未设置',
                role_text,
                '正常' if status == 'active' else '禁用',
                '已启用' if mfa_enabled else '未启用',
                f"{warning_count or 0} 次",
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
                       FROM login_logs
                       ORDER BY login_time DESC LIMIT ?
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

        # 如果是激活操作，同时清零警告次数
        if new_status == 'active':
            cursor.execute('''
                           UPDATE users
                           SET status        = ?,
                               warning_count = 0
                           WHERE username = ?
                           ''', (new_status, username))
            conn.commit()
            conn.close()
            return f"用户 {username} 已激活，警告次数已清零"
        else:
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


# 保存问答记录
def save_qa_record(username, question, answer, tool_used='', confidence_score=0.0, source_info=''):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
                       INSERT INTO qa_records (username, question, answer, tool_used, confidence_score, source_info)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ''', (username, question, answer, tool_used, confidence_score, source_info))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"保存问答记录失败: {e}")


# 医疗问答机器人（带记录）
def doctor_bot(message, history, username='anonymous'):
    service = Service()
    answer = service.answer(message, history)

    # 简单的可信度评分（基于答案长度和关键词）
    confidence_score = min(0.95, 0.5 + len(answer) / 500)

    # 判断使用的工具
    tool_used = "未知"
    if "graph_func" in str(answer):
        tool_used = "知识图谱"
    elif "retrival_func" in str(answer):
        tool_used = "向量检索"
    elif "search_func" in str(answer):
        tool_used = "网络搜索"
    else:
        tool_used = "通用对话"

    source_info = f"工具: {tool_used}, 模型: LLM"

    # 保存问答记录
    save_qa_record(username, message, answer, tool_used, confidence_score, source_info)

    return answer


# 获取待审核的问答列表
def get_pending_qa_records():
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
                       SELECT id,
                              username,
                              question,
                              answer,
                              tool_used,
                              confidence_score,
                              source_info,
                              created_at
                       FROM qa_records
                       WHERE review_status = 'pending'
                       ORDER BY created_at DESC
                       ''')
        records = cursor.fetchall()
        conn.close()

        data = []
        for record in records:
            record_id, username, question, answer, tool_used, confidence, source, created_at = record
            # 截断过长的文本
            question_short = question[:50] + '...' if len(question) > 50 else question
            answer_short = answer[:80] + '...' if len(answer) > 80 else answer

            data.append([
                record_id,
                username,
                question_short,
                answer_short,
                tool_used,
                f"{confidence:.2f}",
                created_at
            ])
        return data
    except Exception as e:
        print(f"获取待审核记录失败: {e}")
        return []


# 获取问答详情
def get_qa_detail(record_id):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
                       SELECT username,
                              question,
                              answer,
                              tool_used,
                              confidence_score,
                              source_info,
                              review_status,
                              created_at
                       FROM qa_records
                       WHERE id = ?
                       ''', (record_id,))
        record = cursor.fetchone()
        conn.close()

        if record:
            username, question, answer, tool_used, confidence, source, status, created_at = record
            detail = f"""
【记录ID】{record_id}
【用户】{username}
【提问时间】{created_at}
【审核状态】{status}

【问题】
{question}

【答案】
{answer}

【生成过程】
- 使用工具: {tool_used}
- 可信度评分: {confidence:.2f}
- 来源信息: {source}
            """
            return detail, question, answer, tool_used, f"{confidence:.2f}", source
        return "未找到记录", "", "", "", "", ""
    except Exception as e:
        return f"获取详情失败: {str(e)}", "", "", "", "", ""


# 审核问答记录
def review_qa_record(record_id, reviewer, action, comment=''):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        # 获取问答记录信息
        cursor.execute('SELECT username, question FROM qa_records WHERE id = ?', (record_id,))
        record = cursor.fetchone()

        if not record:
            conn.close()
            return "记录不存在"

        username, question = record

        # 更新审核状态
        cursor.execute('''
                       UPDATE qa_records
                       SET review_status  = ?,
                           reviewer       = ?,
                           review_comment = ?,
                           review_time    = CURRENT_TIMESTAMP,
                           is_visible     = ?
                       WHERE id = ?
                       ''', (action, reviewer, comment, 0 if action == 'rejected' else 1, record_id))

        # 如果是拒绝，给用户发送警告
        if action == 'rejected':
            # 增加用户警告次数
            cursor.execute('''
                           UPDATE users
                           SET warning_count = warning_count + 1
                           WHERE username = ?
                           ''', (username,))

            # 记录警告
            warning_reason = comment if comment else "您的问题不符合使用规范"
            cursor.execute('''
                           INSERT INTO user_warnings (username, qa_record_id, warning_reason)
                           VALUES (?, ?, ?)
                           ''', (username, record_id, warning_reason))

            # 检查警告次数，如果超过3次自动禁用账户
            cursor.execute('SELECT warning_count FROM users WHERE username = ?', (username,))
            warning_count = cursor.fetchone()[0]

            if warning_count >= 3:
                cursor.execute('UPDATE users SET status = ? WHERE username = ?', ('disabled', username))
                conn.commit()
                conn.close()
                return f"记录 {record_id} 已拒绝，用户 {username} 已被警告（第{warning_count}次），账户已被禁用"

            conn.commit()
            conn.close()
            return f"记录 {record_id} 已拒绝，用户 {username} 已被警告（第{warning_count}次）"

        conn.commit()
        conn.close()
        return f"记录 {record_id} 已{action}"
    except Exception as e:
        return f"审核失败: {str(e)}"


# 获取用户警告
def get_user_warnings(username, only_unread=False):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        if only_unread:
            cursor.execute('''
                           SELECT id, qa_record_id, warning_reason, warning_time
                           FROM user_warnings
                           WHERE username = ?
                             AND is_read = 0
                           ORDER BY warning_time DESC
                           ''', (username,))
        else:
            # 获取所有警告（最近10条）
            cursor.execute('''
                           SELECT id, qa_record_id, warning_reason, warning_time
                           FROM user_warnings
                           WHERE username = ?
                           ORDER BY warning_time DESC LIMIT 10
                           ''', (username,))

        warnings = cursor.fetchall()
        conn.close()
        return warnings
    except Exception as e:
        print(f"获取警告失败: {e}")
        return []


# 标记警告为已读
def mark_warnings_as_read(username):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
                       UPDATE user_warnings
                       SET is_read = 1
                       WHERE username = ?
                         AND is_read = 0
                       ''', (username,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"标记警告失败: {e}")


# 获取用户警告次数
def get_user_warning_count(username):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT warning_count FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        return 0


# 获取已审核记录
def get_reviewed_records():
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
                       SELECT id, username, question, answer, review_status, reviewer, review_time
                       FROM qa_records
                       WHERE review_status != 'pending'
                       ORDER BY review_time DESC
                           LIMIT 100
                       ''')
        records = cursor.fetchall()
        conn.close()

        data = []
        for record in records:
            record_id, username, question, answer, status, reviewer, review_time = record
            question_short = question[:50] + '...' if len(question) > 50 else question
            answer_short = answer[:80] + '...' if len(answer) > 80 else answer

            data.append([
                record_id,
                username,
                question_short,
                answer_short,
                status,
                reviewer or '未审核',
                review_time or '未审核'
            ])
        return data
    except Exception as e:
        print(f"获取已审核记录失败: {e}")
        return []


# ================ 公告栏相关函数（已修复） ================

def generate_notice(username, mark_read=True, show_all=False):
    """
    生成公告栏内容
    Args:
        username: 用户名
        mark_read: 是否标记未读为已读
        show_all: True=显示所有警告，False=只显示未读警告
    """
    if not username:
        return gr.update(visible=False)

    # 根据show_all参数获取警告
    warnings = get_user_warnings(username, only_unread=not show_all)
    warning_count = get_user_warning_count(username)

    # 如果是自动刷新且没有未读警告，不显示公告栏
    if not show_all and not warnings:
        return gr.update(visible=False)

    # 构建通知内容
    gradient_color = "#667eea, #764ba2"  # 默认蓝色渐变
    title_icon = "📢"

    # 根据警告次数调整颜色
    if warning_count >= 2:
        gradient_color = "#f093fb, #f5576c"  # 红色渐变（高风险）
        title_icon = "⚠️"
    elif warning_count >= 1:
        gradient_color = "#f6d365, #fda085"  # 橙色渐变（警告）
        title_icon = "⚠️"

    notice_html = f"""
<div style='background: linear-gradient(135deg, {gradient_color}); 
            padding: 15px; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
    <div style='display: flex; align-items: center; margin-bottom: 10px;'>
        <span style='font-size: 24px; margin-right: 10px;'>{title_icon}</span>
        <span style='color: white; font-size: 18px; font-weight: bold;'>系统公告</span>
        <span style='margin-left: auto; background: rgba(255,255,255,0.3); padding: 5px 15px; border-radius: 20px; color: white; font-size: 14px;'>
            警告 {warning_count}/3
        </span>
    </div>
"""

    if warnings:
        # 显示警告记录
        display_count = 0
        for warning in warnings:
            warning_id, qa_id, reason, warning_time = warning
            display_count += 1
            if display_count > 5:  # 最多显示5条
                notice_html += f"""
    <div style='background: white; padding: 10px; margin: 8px 0; border-radius: 8px; text-align: center; color: #666;'>
        ... 还有 {len(warnings) - 5} 条历史警告
    </div>
"""
                break

            notice_html += f"""
    <div style='background: white; padding: 12px; margin: 8px 0; border-radius: 8px; border-left: 4px solid #f5576c;'>
        <div style='color: #d9534f; font-weight: bold; font-size: 15px; margin-bottom: 5px;'>
            ⚠️ {reason}
        </div>
        <div style='color: #666; font-size: 12px;'>
            {warning_time}
        </div>
    </div>
"""
    else:
        # 没有警告记录
        notice_html += """
    <div style='background: white; padding: 15px; margin: 8px 0; border-radius: 8px; text-align: center;'>
        <div style='color: #27ae60; font-size: 16px; font-weight: bold;'>
            ✅ 您的账户状态良好
        </div>
        <div style='color: #7f8c8d; font-size: 14px; margin-top: 5px;'>
            没有未处理的警告信息
        </div>
    </div>
"""

    # 警告次数提醒
    if warning_count >= 3:
        notice_html += f"""
    <div style='background: rgba(255,255,255,0.95); padding: 10px; margin-top: 10px; border-radius: 8px; border: 2px solid #d9534f;'>
        <div style='color: #721c24; font-weight: bold; text-align: center; font-size: 14px;'>
            ⚠️ 账户已被禁用！请联系管理员处理
        </div>
    </div>
"""
    elif warning_count >= 2:
        notice_html += f"""
    <div style='background: rgba(255,255,255,0.95); padding: 10px; margin-top: 10px; border-radius: 8px; border: 2px solid #f0ad4e;'>
        <div style='color: #8a6d3b; font-weight: bold; text-align: center; font-size: 14px;'>
            ⚠️ 累计警告 {warning_count} 次，再次违规将导致账户被禁用！
        </div>
    </div>
"""
    elif warning_count >= 1:
        notice_html += f"""
    <div style='background: rgba(255,255,255,0.95); padding: 10px; margin-top: 10px; border-radius: 8px; border: 1px solid #f0ad4e;'>
        <div style='color: #8a6d3b; text-align: center; font-size: 13px;'>
            ⚠️ 累计警告 {warning_count} 次，请注意遵守使用规范
        </div>
    </div>
"""

    notice_html += "</div>"

    # 标记未读警告为已读
    if mark_read:
        mark_warnings_as_read(username)

    return gr.update(value=notice_html, visible=True)


# 手动刷新公告栏
def refresh_notice(username):
    """
    手动刷新公告栏（点击🔔按钮时调用）
    显示所有警告记录（包括已读的）
    """
    return generate_notice(username, mark_read=True, show_all=True)


# 自动刷新公告栏
def auto_refresh_notice(trigger, username):
    """
    自动刷新公告栏（定时器调用）
    只显示未读警告
    """
    if not username:
        return gr.update(visible=False), str(int(trigger) + 1)

    # 自动刷新时：只显示未读警告
    notice = generate_notice(username, mark_read=False, show_all=False)
    return notice, str(int(trigger) + 1)


# ================ 主应用 ================

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
            gr.Markdown(
                "<div style='text-align: center; font-size: 28px; font-weight: bold; margin: 30px 0; color: #2c3e50;'>🏥 医疗问诊系统</div>")

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
            gr.Markdown(
                "<div style='text-align: center; font-size: 28px; font-weight: bold; margin: 30px 0; color: #2c3e50;'>🔐 二次验证</div>")
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
                gr.Markdown(
                    "<div style='text-align: center; font-size: 24px; font-weight: bold; margin: 20px 0; color: #2c3e50; flex-grow: 1;'>医疗问诊机器人</div>")
                user_role_display = gr.Textbox(value="", visible=False)
                admin_panel_btn = gr.Button("管理面板", size="sm", scale=0, visible=False)
                reviewer_panel_btn = gr.Button("审核面板", size="sm", scale=0, visible=False)
                refresh_notice_btn = gr.Button("🔔", size="sm", scale=0)
                logout_btn = gr.Button("退出登录", size="sm", scale=0)

            # 公告栏
            notice_board = gr.Markdown(visible=False)

            # 隐藏的定时器触发器
            auto_refresh_trigger = gr.Textbox(visible=False, value="0")

            chatbot = gr.Chatbot(height=400, bubble_full_width=False)
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
            gr.Markdown(
                "<div style='text-align: center; font-size: 28px; font-weight: bold; margin: 30px 0; color: #2c3e50;'>👨‍💼 管理员面板</div>")

            with gr.Tabs():
                with gr.Tab("用户管理"):
                    refresh_users_btn = gr.Button("刷新用户列表", variant="secondary")
                    users_table = gr.Dataframe(
                        headers=["用户名", "邮箱", "角色", "状态", "MFA", "警告次数", "最后登录", "注册时间"],
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

        # 审核员面板
        with gr.Column(visible=False) as reviewer_page:
            gr.Markdown(
                "<div style='text-align: center; font-size: 28px; font-weight: bold; margin: 30px 0; color: #2c3e50;'>📋 内容审核面板</div>")

            with gr.Tabs():
                with gr.Tab("待审核列表"):
                    refresh_pending_btn = gr.Button("刷新列表", variant="secondary")
                    pending_qa_table = gr.Dataframe(
                        headers=["ID", "用户", "问题", "答案", "工具", "可信度", "时间"],
                        label="待审核问答列表",
                        interactive=False
                    )

                    gr.Markdown("### 查看详情")
                    with gr.Row():
                        detail_record_id = gr.Number(label="记录ID", precision=0)
                        view_detail_btn = gr.Button("查看详情", variant="secondary")

                    qa_detail_display = gr.Textbox(
                        label="问答详情",
                        lines=15,
                        interactive=False
                    )

                    gr.Markdown("### 审核操作")
                    with gr.Row():
                        review_action = gr.Radio(
                            choices=["approved", "rejected", "flagged"],
                            label="审核结果",
                            value="approved"
                        )
                        review_comment_input = gr.Textbox(
                            label="审核意见（可选）",
                            placeholder="输入审核意见..."
                        )

                    submit_review_btn = gr.Button("提交审核", variant="primary")
                    review_msg = gr.Textbox(label="操作结果", interactive=False)

                with gr.Tab("已审核记录"):
                    refresh_reviewed_btn = gr.Button("刷新列表", variant="secondary")
                    reviewed_qa_table = gr.Dataframe(
                        headers=["ID", "用户", "问题", "答案", "状态", "审核员", "审核时间"],
                        label="已审核记录",
                        interactive=False
                    )

                with gr.Tab("详细信息"):
                    gr.Markdown("### 生成过程分析")
                    detail_question = gr.Textbox(label="问题", interactive=False)
                    detail_answer = gr.Textbox(label="答案", lines=5, interactive=False)

                    with gr.Row():
                        detail_tool = gr.Textbox(label="使用工具", interactive=False)
                        detail_confidence = gr.Textbox(label="可信度评分", interactive=False)

                    detail_source = gr.Textbox(label="来源信息", interactive=False)

            back_to_chat_from_review_btn = gr.Button("返回聊天", size="lg")

        # 临时存储待验证的用户名和角色
        pending_username = gr.State(None)
        pending_role = gr.State(None)


        # ================ 事件处理 ================

        # 登录逻辑
        def handle_login(username, password):
            msg, user, needs_mfa, role = verify_credentials(username, password)

            if needs_mfa:
                # 需要MFA验证，跳转到MFA页面
                return (msg, None,
                        gr.update(visible=False), gr.update(visible=True), gr.update(visible=False),
                        gr.update(visible=False), gr.update(visible=False),
                        username, role, username, "", gr.update(visible=False), gr.update(visible=False),
                        gr.update(visible=False))
            elif user:
                # 直接登录成功
                is_admin = (role == 'admin')
                is_reviewer = (role == 'reviewer' or role == 'admin')

                # 登录时显示未读警告
                notice = generate_notice(user, mark_read=True, show_all=False)

                return (msg, user,
                        gr.update(visible=False), gr.update(visible=False), gr.update(visible=True),
                        gr.update(visible=False), gr.update(visible=False),
                        None, role, "", role, gr.update(visible=is_admin), gr.update(visible=is_reviewer),
                        notice)
            else:
                # 登录失败
                return (msg, None,
                        gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
                        gr.update(visible=False), gr.update(visible=False),
                        None, None, "", "", gr.update(visible=False), gr.update(visible=False),
                        gr.update(visible=False))


        login_btn.click(
            fn=handle_login,
            inputs=[login_username, login_password],
            outputs=[login_msg, user_state, login_page, mfa_page, chat_page, admin_page, reviewer_page,
                     pending_username, pending_role, mfa_username_display, user_role_display,
                     admin_panel_btn, reviewer_panel_btn, notice_board]
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
                return "请输入验证码", None, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), "", gr.update(
                    visible=False), gr.update(visible=False), gr.update(visible=False)

            success, msg = verify_code(username, code, 'login')
            if success:
                is_admin = (role == 'admin')
                is_reviewer = (role == 'reviewer' or role == 'admin')

                # MFA验证后显示未读警告
                notice = generate_notice(username, mark_read=True, show_all=False)

                return f"验证成功！欢迎回来，{username}！", username, \
                    gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), \
                    gr.update(visible=False), gr.update(visible=False), \
                    role, gr.update(visible=is_admin), gr.update(visible=is_reviewer), notice
            else:
                return msg, None, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), "", gr.update(
                    visible=False), gr.update(visible=False), gr.update(visible=False)


        verify_btn.click(
            fn=handle_mfa_verify,
            inputs=[pending_username, mfa_code_input, pending_role],
            outputs=[mfa_msg, user_state, login_page, mfa_page, chat_page, admin_page, reviewer_page,
                     user_role_display, admin_panel_btn, reviewer_panel_btn, notice_board]
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

        # 手动刷新公告栏（点击🔔按钮）
        refresh_notice_btn.click(
            fn=refresh_notice,
            inputs=[user_state],
            outputs=[notice_board]
        )

        # 定时自动刷新（每3秒检查一次未读警告）
        auto_refresh_trigger.change(
            fn=auto_refresh_notice,
            inputs=[auto_refresh_trigger, user_state],
            outputs=[notice_board, auto_refresh_trigger],
            every=3  # 每3秒刷新一次
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


        # 审核员面板相关
        def show_reviewer_panel():
            pending_data = get_pending_qa_records()
            reviewed_data = get_reviewed_records()
            return gr.update(visible=False), gr.update(visible=False), gr.update(
                visible=True), pending_data, reviewed_data


        reviewer_panel_btn.click(
            fn=show_reviewer_panel,
            outputs=[chat_page, admin_page, reviewer_page, pending_qa_table, reviewed_qa_table]
        )


        def back_to_chat_from_review():
            return gr.update(visible=True), gr.update(visible=False)


        back_to_chat_from_review_btn.click(
            fn=back_to_chat_from_review,
            outputs=[chat_page, reviewer_page]
        )


        def refresh_pending():
            return get_pending_qa_records()


        refresh_pending_btn.click(
            fn=refresh_pending,
            outputs=[pending_qa_table]
        )


        def refresh_reviewed():
            return get_reviewed_records()


        refresh_reviewed_btn.click(
            fn=refresh_reviewed,
            outputs=[reviewed_qa_table]
        )


        def view_qa_detail(record_id):
            if not record_id:
                return "请输入记录ID", "", "", "", "", ""
            detail, question, answer, tool, confidence, source = get_qa_detail(int(record_id))
            return detail, question, answer, tool, confidence, source


        view_detail_btn.click(
            fn=view_qa_detail,
            inputs=[detail_record_id],
            outputs=[qa_detail_display, detail_question, detail_answer, detail_tool, detail_confidence, detail_source]
        )


        def submit_review(record_id, action, comment, reviewer):
            if not record_id:
                return "请输入记录ID", get_pending_qa_records(), ""
            msg = review_qa_record(int(record_id), reviewer, action, comment)
            # 审核完成后，清空输入框
            return msg, get_pending_qa_records(), ""


        submit_review_btn.click(
            fn=submit_review,
            inputs=[detail_record_id, review_action, review_comment_input, user_state],
            outputs=[review_msg, pending_qa_table, review_comment_input]
        )


        # 退出登录
        def handle_logout():
            return None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(
                visible=False), gr.update(visible=False), gr.update(visible=False), []


        logout_btn.click(
            fn=handle_logout,
            outputs=[user_state, login_page, mfa_page, chat_page, admin_page, reviewer_page, notice_board, chatbot]
        )


        # 聊天逻辑
        def respond(message, chat_history):
            if not message.strip():
                return chat_history, ""
            # 先显示用户消息
            chat_history.append((message, None))
            return chat_history, ""


        def generate_response(chat_history, username):
            if not chat_history or chat_history[-1][1] is not None:
                return chat_history

            message = chat_history[-1][0]
            # 获取历史记录（不包括当前这条）
            history = chat_history[:-1]
            bot_message = doctor_bot(message, history, username or 'anonymous')
            chat_history[-1] = (message, bot_message)
            return chat_history


        submit_btn.click(
            fn=respond,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, msg_input]
        ).then(
            fn=generate_response,
            inputs=[chatbot, user_state],
            outputs=[chatbot]
        )

        msg_input.submit(
            fn=respond,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, msg_input]
        ).then(
            fn=generate_response,
            inputs=[chatbot, user_state],
            outputs=[chatbot]
        )

        clear_btn.click(
            fn=lambda: [],
            outputs=chatbot
        )

    app.launch()
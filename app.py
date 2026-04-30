
import os
import yaml
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from loguru import logger
import threading
import time

# 配置日志
logger.remove()
logger.add("logs/app_{time:YYYY-MM-DD}.log", rotation="500 MB", level="INFO")
logger.add(lambda msg: print(msg, end=''), level="INFO")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# 配置文件路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_INFO_FILE = os.path.join(BASE_DIR, 'user_info.txt')
PORT_FILE = os.path.join(BASE_DIR, 'port.txt')
CONFIG_DIR = os.path.join(BASE_DIR, 'configs')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
DATASETS_DIR = os.path.join(BASE_DIR, 'datasets')

# 确保必要的目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# 全局变量
tasks = {}
task_lock = threading.Lock()

# 读取端口号
def get_port():
    try:
        with open(PORT_FILE, 'r') as f:
            return int(f.read().strip())
    except:
        return 5000

# 读取用户信息
def get_user_info():
    try:
        with open(USER_INFO_FILE, 'r') as f:
            content = f.read()
            # 解析用户名和密码
            username = content.split("username: '")[1].split("'")[0]
            password = content.split("password: '")[1].split("'")[0]
            return {'username': username, 'password': password}
    except Exception as e:
        logger.error(f"读取用户信息失败: {e}")
        return None

# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 首页路由
@app.route('/')
@login_required
def index():
    user_id = session.get('user_id', 'Unknown')
    task_names = ['digging_1step', 'digging_2step', 'digging_3step', 'backtest', 'simulation']
    return render_template('index.html', user_id=user_id, task_names=task_names)

# 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        # 直接使用 user_info.txt 文件中的内容
        user_info = get_user_info()
        if not user_info:
            error = '无法获取用户信息'
            return render_template('login.html', error=error)
        
        user_id = user_info['username']
        password = user_info['password']
        remember = request.form.get('remember_me')

        # 尝试登录 WorldQuant Brain
        try:
            import asyncio
            from src import WorldQuantClient
            
            async def verify_login():
                client = WorldQuantClient(user_id, password)
                success = await client.login()
                await client.close()
                return success
            
            # 在同步上下文中运行异步函数
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            login_success = loop.run_until_complete(verify_login())
            loop.close()
            
            logger.info(f"登录结果: {login_success}, 用户: {user_id}")

            if login_success:
                session['user_id'] = user_id
                session['logged_in'] = True
                if remember:
                    session.permanent = True
                logger.info(f"用户 {user_id} 登录成功，重定向到首页")
                return redirect(url_for('index'))
            else:
                error = 'WorldQuant Brain 登录失败，请检查用户名和密码'
                logger.error(f"用户 {user_id} 登录失败")
        except Exception as e:
            logger.error(f"登录验证失败: {str(e)}", exc_info=True)
            error = f'登录验证失败: {str(e)}'

    return render_template('login.html', error=error)

# 登出路由
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 高级配置路由
@app.route('/config')
@login_required
def config():
    return render_template('advanced_config.html')

# API: 获取任务列表
@app.route('/api/tasks', methods=['GET'])
@login_required
def get_tasks():
    with task_lock:
        task_list = []
        for task_id, task_info in tasks.items():
            task_list.append({
                'id': task_id,
                'name': task_info['name'],
                'status': task_info['status'],
                'start_time': task_info['start_time'].isoformat() if task_info.get('start_time') else None,
                'progress': task_info.get('progress', 0),
                'log': task_info.get('log', '')
            })
        return jsonify({'tasks': task_list})

# API: 启动任务
@app.route('/api/tasks/start', methods=['POST'])
@login_required
def start_task():
    data = request.json
    task_name = data.get('task_name')
    params = data.get('params', {})

    if not task_name:
        return jsonify({'error': '任务名称不能为空'}), 400

    # 生成任务ID
    task_id = f"{task_name}_{int(time.time())}"

    # 创建任务
    with task_lock:
        tasks[task_id] = {
            'name': task_name,
            'status': 'running',
            'start_time': datetime.now(),
            'progress': 0,
            'log': '',
            'params': params
        }

    # 在后台线程中运行任务
    thread = threading.Thread(target=run_task, args=(task_id,))
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'started'})

# API: 停止任务
@app.route('/api/tasks/<task_id>/stop', methods=['POST'])
@login_required
def stop_task(task_id):
    with task_lock:
        if task_id in tasks:
            tasks[task_id]['status'] = 'stopped'
            return jsonify({'status': 'stopped'})
        else:
            return jsonify({'error': '任务不存在'}), 404

# API: 暂停任务
@app.route('/api/tasks/<task_id>/pause', methods=['POST'])
@login_required
def pause_task(task_id):
    with task_lock:
        if task_id in tasks:
            tasks[task_id]['status'] = 'paused'
            return jsonify({'status': 'paused'})
        else:
            return jsonify({'error': '任务不存在'}), 404

# API: 恢复任务
@app.route('/api/tasks/<task_id>/resume', methods=['POST'])
@login_required
def resume_task(task_id):
    with task_lock:
        if task_id in tasks:
            tasks[task_id]['status'] = 'running'
            # 在后台线程中恢复任务
            thread = threading.Thread(target=run_task, args=(task_id,))
            thread.daemon = True
            thread.start()
            return jsonify({'status': 'resumed'})
        else:
            return jsonify({'error': '任务不存在'}), 404

# API: 删除任务
@app.route('/api/tasks/<task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    with task_lock:
        if task_id in tasks:
            # 只能删除非运行中的任务
            if tasks[task_id]['status'] in ['running', 'paused', 'pending']:
                return jsonify({'error': '无法删除运行中的任务'}), 400
            del tasks[task_id]
            return jsonify({'status': 'deleted'})
        else:
            return jsonify({'error': '任务不存在'}), 404

# API: 获取任务日志
@app.route('/api/tasks/<task_id>/logs', methods=['GET'])
@login_required
def get_task_logs(task_id):
    with task_lock:
        if task_id in tasks:
            return jsonify({'logs': tasks[task_id].get('log', '')})
        else:
            return jsonify({'error': '任务不存在'}), 404

# API: 获取完整任务日志
@app.route('/api/tasks/<task_id>/logs/full', methods=['GET'])
@login_required
def get_full_task_logs(task_id):
    with task_lock:
        if task_id in tasks:
            return jsonify({'logs': tasks[task_id].get('log', '')})
        else:
            return jsonify({'error': '任务不存在'}), 404

# API: 保存配置
@app.route('/api/config/save', methods=['POST'])
@login_required
def save_config():
    data = request.json
    config_name = data.get('config_name')
    config_data = data.get('config_data')

    if not config_name or not config_data:
        return jsonify({'error': '配置名称和内容不能为空'}), 400

    try:
        config_file = os.path.join(CONFIG_DIR, f"{config_name}.yaml")
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        return jsonify({'status': 'saved'})
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return jsonify({'error': str(e)}), 500

# API: 加载配置
@app.route('/api/config/load', methods=['GET'])
@login_required
def load_config():
    configs = []
    try:
        for filename in os.listdir(CONFIG_DIR):
            if filename.endswith('.yaml'):
                config_name = filename[:-5]
                config_file = os.path.join(CONFIG_DIR, filename)
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                configs.append({
                    'name': config_name,
                    'data': config_data,
                    'modified_time': datetime.fromtimestamp(os.path.getmtime(config_file)).isoformat()
                })
        return jsonify({'configs': configs})
    except Exception as e:
        logger.error(f"加载配置失败: {e}")
        return jsonify({'error': str(e)}), 500

# API: 刷新 WorldQuant 会话
@app.route('/api/refresh_wq_session', methods=['POST'])
@login_required
def refresh_wq_session():
    user_info = get_user_info()
    if not user_info:
        return jsonify({'error': '无法获取用户信息'}), 500
    
    # 尝试重新登录 WorldQuant Brain
    try:
        import asyncio
        from src import WorldQuantClient
        
        async def refresh_session():
            client = WorldQuantClient(user_info['username'], user_info['password'])
            success = await client.login()
            await client.close()
            return success
        
        # 在同步上下文中运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        login_success = loop.run_until_complete(refresh_session())
        loop.close()
        
        if login_success:
            logger.info(f"刷新 WorldQuant 会话成功: {user_info['username']}")
            return jsonify({'status': 'success', 'message': '会话已刷新'})
        else:
            logger.error(f"刷新 WorldQuant 会话失败: {user_info['username']}")
            return jsonify({'status': 'error', 'message': '会话刷新失败'}), 500
    except Exception as e:
        logger.error(f"刷新 WorldQuant 会话异常: {str(e)}")
        return jsonify({'status': 'error', 'message': f'会话刷新异常: {str(e)}'}), 500

# 运行任务
def run_task(task_id):
    try:
        task_info = tasks.get(task_id)
        if not task_info:
            return

        task_name = task_info['name']
        params = task_info.get('params', {})

        logger.info(f"开始执行任务: {task_id}, 名称: {task_name}")
        update_task_log(task_id, f"开始执行任务: {task_name}\n")

        # 根据任务类型执行不同的逻辑
        if task_name == 'digging_1step':
            execute_digging_1step(task_id, params)
        elif task_name == 'digging_2step':
            execute_digging_2step(task_id, params)
        elif task_name == 'digging_3step':
            execute_digging_3step(task_id, params)
        elif task_name == 'backtest':
            execute_backtest(task_id, params)
        elif task_name == 'simulation':
            execute_simulation(task_id, params)
        else:
            update_task_log(task_id, f"未知任务类型: {task_name}\n")
            update_task_status(task_id, 'failed')
            return

        update_task_status(task_id, 'completed')
        logger.info(f"任务完成: {task_id}")

    except Exception as e:
        logger.error(f"任务执行失败: {task_id}, 错误: {e}")
        update_task_log(task_id, f"任务执行失败: {str(e)}\n")
        update_task_status(task_id, 'failed')

# 更新任务日志
def update_task_log(task_id, message):
    with task_lock:
        if task_id in tasks:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            tasks[task_id]['log'] += f"[{timestamp}] {message}"

# 更新任务状态
def update_task_status(task_id, status):
    with task_lock:
        if task_id in tasks:
            tasks[task_id]['status'] = status

# 更新任务进度
def update_task_progress(task_id, progress):
    with task_lock:
        if task_id in tasks:
            tasks[task_id]['progress'] = progress

# 执行一阶段挖掘任务
def execute_digging_1step(task_id, params):
    update_task_log(task_id, "执行一阶段挖掘任务\n")

    dataset_id = params.get('datasetId_1', 'analyst4')
    region = params.get('region_1', 'USA')
    delay = params.get('delay_1', 1)
    universe = params.get('universe_1', 'TOP3000')
    instrument_type = params.get('instrumentType_1', 'EQUITY')
    neutralization = params.get('neutralization_1', 'SUBINDUSTRY')
    n_jobs = params.get('nJobs_1', 3)
    max_run = params.get('maxRun', 0)

    update_task_log(task_id, f"参数: dataset_id={dataset_id}, region={region}, delay={delay}, universe={universe}\n")
    update_task_log(task_id, f"参数: instrument_type={instrument_type}, neutralization={neutralization}, n_jobs={n_jobs}, max_run={max_run}\n")

    # 加载数据集
    try:
        dataset_file = os.path.join(DATASETS_DIR, f"{dataset_id}_datafields.csv")
        if os.path.exists(dataset_file):
            df = pd.read_csv(dataset_file)
            update_task_log(task_id, f"成功加载数据集 {dataset_file}, 共 {len(df)} 条记录\n")

            # 模拟处理过程
            total = min(len(df), 100)  # 限制处理数量
            for i in range(total):
                if tasks[task_id]['status'] != 'running':
                    update_task_log(task_id, "任务被中断\n")
                    return

                progress = int((i + 1) / total * 100)
                update_task_progress(task_id, progress)

                if (i + 1) % 10 == 0:
                    update_task_log(task_id, f"处理进度: {i + 1}/{total} ({progress}%)\n")

                # 模拟处理时间
                time.sleep(0.1)

                # 如果设置了最大运行次数，达到后停止
                if max_run > 0 and (i + 1) >= max_run:
                    update_task_log(task_id, f"达到最大运行次数 {max_run}，停止任务\n")
                    break

            update_task_log(task_id, "一阶段挖掘任务完成\n")
        else:
            update_task_log(task_id, f"数据集文件不存在: {dataset_file}\n")
            update_task_status(task_id, 'failed')
    except Exception as e:
        update_task_log(task_id, f"处理数据集时出错: {str(e)}\n")
        update_task_status(task_id, 'failed')

# 执行二阶段挖掘任务
def execute_digging_2step(task_id, params):
    update_task_log(task_id, "执行二阶段挖掘任务\n")

    dataset_id = params.get('datasetId_2', 'analyst4')
    region = params.get('region_2', 'USA')
    delay = params.get('delay_2', 1)
    universe = params.get('universe_2', 'TOP3000')
    instrument_type = params.get('instrumentType_2', 'EQUITY')
    neutralization = params.get('neutralization_2', 'SUBINDUSTRY')
    n_jobs = params.get('nJobs_2', 3)
    max_run = params.get('max_run_step2', 0)

    update_task_log(task_id, f"参数: dataset_id={dataset_id}, region={region}, delay={delay}, universe={universe}\n")
    update_task_log(task_id, f"参数: instrument_type={instrument_type}, neutralization={neutralization}, n_jobs={n_jobs}, max_run={max_run}\n")

    # 加载数据集
    try:
        dataset_file = os.path.join(DATASETS_DIR, f"{dataset_id}_datafields.csv")
        if os.path.exists(dataset_file):
            df = pd.read_csv(dataset_file)
            update_task_log(task_id, f"成功加载数据集 {dataset_file}, 共 {len(df)} 条记录\n")

            # 模拟处理过程
            total = min(len(df), 100)  # 限制处理数量
            for i in range(total):
                if tasks[task_id]['status'] != 'running':
                    update_task_log(task_id, "任务被中断\n")
                    return

                progress = int((i + 1) / total * 100)
                update_task_progress(task_id, progress)

                if (i + 1) % 10 == 0:
                    update_task_log(task_id, f"处理进度: {i + 1}/{total} ({progress}%)\n")

                # 模拟处理时间
                time.sleep(0.1)

                # 如果设置了最大运行次数，达到后停止
                if max_run > 0 and (i + 1) >= max_run:
                    update_task_log(task_id, f"达到最大运行次数 {max_run}，停止任务\n")
                    break

            update_task_log(task_id, "二阶段挖掘任务完成\n")
        else:
            update_task_log(task_id, f"数据集文件不存在: {dataset_file}\n")
            update_task_status(task_id, 'failed')
    except Exception as e:
        update_task_log(task_id, f"处理数据集时出错: {str(e)}\n")
        update_task_status(task_id, 'failed')

# 执行三阶段挖掘任务
def execute_digging_3step(task_id, params):
    update_task_log(task_id, "执行三阶段挖掘任务\n")

    dataset_id = params.get('datasetId_3', 'analyst4')
    region = params.get('region_3', 'USA')
    delay = params.get('delay_3', 1)
    universe = params.get('universe_3', 'TOP3000')
    instrument_type = params.get('instrumentType_3', 'EQUITY')
    neutralization = params.get('neutralization_3', 'SUBINDUSTRY')
    n_jobs = params.get('nJobs_3', 3)
    max_run = params.get('max_run_step3', 0)

    update_task_log(task_id, f"参数: dataset_id={dataset_id}, region={region}, delay={delay}, universe={universe}\n")
    update_task_log(task_id, f"参数: instrument_type={instrument_type}, neutralization={neutralization}, n_jobs={n_jobs}, max_run={max_run}\n")

    # 加载数据集
    try:
        dataset_file = os.path.join(DATASETS_DIR, f"{dataset_id}_datafields.csv")
        if os.path.exists(dataset_file):
            df = pd.read_csv(dataset_file)
            update_task_log(task_id, f"成功加载数据集 {dataset_file}, 共 {len(df)} 条记录\n")

            # 模拟处理过程
            total = min(len(df), 100)  # 限制处理数量
            for i in range(total):
                if tasks[task_id]['status'] != 'running':
                    update_task_log(task_id, "任务被中断\n")
                    return

                progress = int((i + 1) / total * 100)
                update_task_progress(task_id, progress)

                if (i + 1) % 10 == 0:
                    update_task_log(task_id, f"处理进度: {i + 1}/{total} ({progress}%)\n")

                # 模拟处理时间
                time.sleep(0.1)

                # 如果设置了最大运行次数，达到后停止
                if max_run > 0 and (i + 1) >= max_run:
                    update_task_log(task_id, f"达到最大运行次数 {max_run}，停止任务\n")
                    break

            update_task_log(task_id, "三阶段挖掘任务完成\n")
        else:
            update_task_log(task_id, f"数据集文件不存在: {dataset_file}\n")
            update_task_status(task_id, 'failed')
    except Exception as e:
        update_task_log(task_id, f"处理数据集时出错: {str(e)}\n")
        update_task_status(task_id, 'failed')

# 执行回测任务
def execute_backtest(task_id, params):
    update_task_log(task_id, "执行回测任务\n")

    # 获取回测参数
    alpha_expression = params.get('alpha_expression', '')
    region = params.get('region', 'USA')
    delay = params.get('delay', 1)
    universe = params.get('universe', 'TOP3000')
    instrument_type = params.get('instrument_type', 'EQUITY')
    neutralization = params.get('neutralization', 'SUBINDUSTRY')
    decay = params.get('decay', 5)

    update_task_log(task_id, f"参数: alpha={alpha_expression}, region={region}, delay={delay}, universe={universe}\n")
    update_task_log(task_id, f"参数: instrument_type={instrument_type}, neutralization={neutralization}, decay={decay}\n")

    # 模拟回测过程
    try:
        total = 10  # 模拟10个步骤
        for i in range(total):
            if tasks[task_id]['status'] != 'running':
                update_task_log(task_id, "任务被中断\n")
                return

            progress = int((i + 1) / total * 100)
            update_task_progress(task_id, progress)

            update_task_log(task_id, f"回测步骤 {i + 1}/{total} ({progress}%)\n")

            # 模拟处理时间
            time.sleep(0.5)

        update_task_log(task_id, "回测任务完成\n")
    except Exception as e:
        update_task_log(task_id, f"回测过程中出错: {str(e)}\n")
        update_task_status(task_id, 'failed')

# 执行模拟交易任务
def execute_simulation(task_id, params):
    update_task_log(task_id, "执行模拟交易任务\n")

    # 获取模拟交易参数
    alpha_expression = params.get('alpha_expression', '')
    region = params.get('region', 'USA')
    universe = params.get('universe', 'TOP3000')
    start_date = params.get('start_date', '2020-01-01')
    end_date = params.get('end_date', '2023-12-31')

    update_task_log(task_id, f"参数: alpha={alpha_expression}, region={region}, universe={universe}\n")
    update_task_log(task_id, f"参数: start_date={start_date}, end_date={end_date}\n")

    # 模拟交易过程
    try:
        total = 10  # 模拟10个步骤
        for i in range(total):
            if tasks[task_id]['status'] != 'running':
                update_task_log(task_id, "任务被中断\n")
                return

            progress = int((i + 1) / total * 100)
            update_task_progress(task_id, progress)

            update_task_log(task_id, f"模拟交易步骤 {i + 1}/{total} ({progress}%)\n")

            # 模拟处理时间
            time.sleep(0.5)

        update_task_log(task_id, "模拟交易任务完成\n")
    except Exception as e:
        update_task_log(task_id, f"模拟交易过程中出错: {str(e)}\n")
        update_task_status(task_id, 'failed')

if __name__ == '__main__':
    port = get_port()
    logger.info(f"启动 WorldQuant 策略工具，端口: {port}")
    app.run(host='0.0.0.0', port=port, debug=True)


# WorldQuant 策略工具

一个用于 WorldQuant Brain 平台的策略挖掘、回测和分析工具。

## 功能特性

- 策略自动挖掘：基于预定义模板和数据字段自动生成策略
- 多阶段挖掘：支持一阶段、二阶段和三阶段挖掘流程
- 策略回测：对生成的策略进行回测分析
- 性能分析：分析策略表现，包括夏普比率、适应度等指标
- Web 界面：提供友好的 Web 界面进行操作和监控

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/world-quant-monitor.git
cd world-quant-monitor
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 配置

1. 在 `user_info.txt` 中配置你的 WorldQuant Brain 账号信息：
```
username: 'your_username@example.com'
password: 'your_password'
```

2. 在 `port.txt` 中设置应用运行端口（默认为 5000）：
```
5000
```

## 使用方法

### 启动应用

```bash
python app.py
```

然后在浏览器中访问 `http://localhost:5000`

### 使用 Web 界面

1. 登录系统：使用你的 WorldQuant Brain 用户名和激活码
2. 选择任务类型：一阶段挖掘、二阶段挖掘、三阶段挖掘、回测或模拟
3. 配置参数：根据任务类型配置相应参数
4. 启动任务：点击"启动"按钮开始执行任务
5. 监控进度：在日志区域查看任务执行进度和结果

### 使用 Python API

```python
from src import WorldQuantClient, StrategyMiner, BacktestEngine
import asyncio

async def main():
    # 初始化客户端
    client = WorldQuantClient(username='your_username@example.com', password='your_password')

    # 登录
    await client.login()

    # 初始化策略挖掘器
    miner = StrategyMiner(client, datasets_dir='datasets')

    # 生成策略
    strategy = miner.generate_strategy(dataset_id='analyst4')
    print(f"生成的策略: {strategy}")

    # 初始化回测引擎
    engine = BacktestEngine(client)

    # 运行回测
    result = await engine.run_backtest(code=strategy)
    print(f"回测结果: {result}")

    # 关闭客户端
    await client.close()

# 运行主函数
asyncio.run(main())
```

## 项目结构

```
world-quant-monitor/
├── app.py                      # Flask Web 应用
├── datasets/                   # 数据集目录
│   ├── analyst4_datafields.csv
│   ├── fundamental6_datafields.csv
│   └── model77_datafields.csv
├── src/                        # 源代码目录
│   ├── __init__.py
│   ├── worldquant_client.py    # WorldQuant API 客户端
│   ├── strategy_miner.py       # 策略挖掘器
│   └── backtest.py             # 回测引擎
├── templates/                  # HTML 模板目录
│   ├── index.html
│   ├── login.html
│   └── advanced_config.html
├── configs/                    # 配置文件目录
├── logs/                       # 日志文件目录
├── requirements.txt            # Python 依赖
├── user_info.txt              # 用户信息
├── port.txt                   # 端口配置
└── README.md                  # 项目说明
```

## 策略挖掘流程

### 一阶段挖掘

1. 从数据集中随机选择字段
2. 使用预定义模板生成策略
3. 对生成的策略进行回测
4. 筛选符合基本条件的策略

### 二阶段挖掘

1. 基于一阶段筛选出的策略
2. 进一步优化和组合
3. 应用更严格的筛选条件

### 三阶段挖掘

1. 基于二阶段筛选出的策略
2. 进行最终优化
3. 应用最严格的筛选条件

## 回测指标说明

- **Sharpe Ratio**: 夏普比率，衡量策略风险调整后的收益
- **Fitness**: 适应度，综合评估策略表现
- **Returns**: 收益率
- **Long Count**: 多头持仓数量
- **Short Count**: 空头持仓数量
- **Turnover**: 换手率

## 注意事项

1. 请妥善保管你的 WorldQuant Brain 账号信息
2. 策略挖掘和回测会消耗 API 调用次数，请注意使用频率
3. 本工具仅供学习和研究使用，不构成投资建议

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请通过以下方式联系：
- 提交 Issue
- 发送邮件至 your_email@example.com

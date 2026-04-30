
"""
WorldQuant 策略回测模块
用于对策略进行回测分析
"""

import pandas as pd
import numpy as np
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from loguru import logger
from datetime import datetime, timedelta

from .worldquant_client import WorldQuantClient


class BacktestEngine:
    """WorldQuant 回测引擎"""

    def __init__(self, client: WorldQuantClient):
        """
        初始化回测引擎

        Args:
            client: WorldQuant 客户端
        """
        self.client = client
        self.backtest_results = {}  # 回测结果缓存

    async def run_backtest(
        self,
        code: str,
        region: str = "USA",
        delay: int = 1,
        universe: str = "TOP3000",
        neutralization: str = "SUBINDUSTRY",
        decay: int = 5,
        instrument_type: str = "EQUITY",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        运行回测

        Args:
            code: 策略代码
            region: 区域
            delay: 延迟
            universe: 股票池
            neutralization: 中性化方式
            decay: 衰减
            instrument_type: 资产类型
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            回测结果
        """
        try:
            # 调用模拟接口
            result = await self.client.simulate(
                code=code,
                region=region,
                delay=delay,
                universe=universe,
                neutralization=neutralization,
                decay=decay,
                instrument_type=instrument_type
            )

            if not result.get('success'):
                logger.error(f"回测失败: {result.get('error')}")
                return {'success': False, 'error': result.get('error')}

            simulation_id = result['data'].get('id')
            if not simulation_id:
                logger.error("模拟ID不存在")
                return {'success': False, 'error': '模拟ID不存在'}

            # 获取模拟结果
            sim_result = await self.client.get_simulation_result(simulation_id)
            if not sim_result.get('success'):
                logger.error(f"获取模拟结果失败: {sim_result.get('error')}")
                return {'success': False, 'error': sim_result.get('error')}

            # 解析回测结果
            performance = sim_result['data'].get('performance', {})
            is_data = sim_result['data'].get('is', {})

            # 提取关键指标
            sharpe = performance.get('sharpe', 0)
            fitness = performance.get('fitness', 0)
            returns = performance.get('returns', 0)
            long_count = is_data.get('longCount', 0)
            short_count = is_data.get('shortCount', 0)
            turnover = is_data.get('turnover', 0)

            # 构建回测结果
            backtest_result = {
                'success': True,
                'code': code,
                'simulation_id': simulation_id,
                'performance': performance,
                'is_data': is_data,
                'metrics': {
                    'sharpe': sharpe,
                    'fitness': fitness,
                    'returns': returns,
                    'long_count': long_count,
                    'short_count': short_count,
                    'turnover': turnover
                },
                'timestamp': datetime.now().isoformat()
            }

            # 缓存回测结果
            self.backtest_results[simulation_id] = backtest_result

            logger.info(f"回测完成: sharpe={sharpe:.4f}, fitness={fitness:.4f}")
            return backtest_result

        except Exception as e:
            logger.error(f"回测异常: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def batch_backtest(
        self,
        codes: List[str],
        region: str = "USA",
        delay: int = 1,
        universe: str = "TOP3000",
        neutralization: str = "SUBINDUSTRY",
        decay: int = 5,
        instrument_type: str = "EQUITY",
        n_jobs: int = 3,
        callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        批量回测

        Args:
            codes: 策略代码列表
            region: 区域
            delay: 延迟
            universe: 股票池
            neutralization: 中性化方式
            decay: 衰减
            instrument_type: 资产类型
            n_jobs: 并发数
            callback: 回调函数

        Returns:
            回测结果列表
        """
        results = []
        semaphore = asyncio.Semaphore(n_jobs)

        async def backtest_single(code: str, index: int) -> Dict[str, Any]:
            """回测单个策略"""
            async with semaphore:
                try:
                    # 调用回调函数
                    if callback:
                        callback({
                            'status': 'backtesting',
                            'index': index,
                            'total': len(codes),
                            'code': code[:50] + "..." if len(code) > 50 else code
                        })

                    # 运行回测
                    result = await self.run_backtest(
                        code=code,
                        region=region,
                        delay=delay,
                        universe=universe,
                        neutralization=neutralization,
                        decay=decay,
                        instrument_type=instrument_type
                    )

                    # 调用回调函数
                    if callback:
                        callback({
                            'status': 'completed',
                            'index': index,
                            'total': len(codes),
                            'code': code[:50] + "..." if len(code) > 50 else code,
                            'result': result
                        })

                    return result

                except Exception as e:
                    logger.error(f"回测策略失败: {code[:50]}..., 错误: {str(e)}")

                    # 调用回调函数
                    if callback:
                        callback({
                            'status': 'failed',
                            'index': index,
                            'total': len(codes),
                            'code': code[:50] + "..." if len(code) > 50 else code,
                            'error': str(e)
                        })

                    return {
                        'success': False,
                        'code': code,
                        'error': str(e)
                    }

        # 创建并发任务
        tasks = [backtest_single(code, i) for i, code in enumerate(codes)]
        results = await asyncio.gather(*tasks)

        return results

    def analyze_results(
        self,
        results: List[Dict[str, Any]],
        sharpe_threshold: float = 0.75,
        fitness_threshold: float = 0.5,
        long_threshold: int = 100,
        short_threshold: int = 100
    ) -> Dict[str, Any]:
        """
        分析回测结果

        Args:
            results: 回测结果列表
            sharpe_threshold: 夏普比率阈值
            fitness_threshold: 适应度阈值
            long_threshold: 多头阈值
            short_threshold: 空头阈值

        Returns:
            分析结果
        """
        # 过滤成功的回测结果
        successful_results = [r for r in results if r.get('success')]

        if not successful_results:
            return {
                'total': len(results),
                'successful': 0,
                'failed': len(results),
                'passed': 0,
                'top_strategies': []
            }

        # 提取指标
        sharpe_values = [r['metrics']['sharpe'] for r in successful_results]
        fitness_values = [r['metrics']['fitness'] for r in successful_results]
        returns_values = [r['metrics']['returns'] for r in successful_results]

        # 计算统计信息
        stats = {
            'sharpe': {
                'mean': np.mean(sharpe_values),
                'std': np.std(sharpe_values),
                'min': np.min(sharpe_values),
                'max': np.max(sharpe_values),
                'median': np.median(sharpe_values)
            },
            'fitness': {
                'mean': np.mean(fitness_values),
                'std': np.std(fitness_values),
                'min': np.min(fitness_values),
                'max': np.max(fitness_values),
                'median': np.median(fitness_values)
            },
            'returns': {
                'mean': np.mean(returns_values),
                'std': np.std(returns_values),
                'min': np.min(returns_values),
                'max': np.max(returns_values),
                'median': np.median(returns_values)
            }
        }

        # 筛选符合条件的策略
        passed_strategies = []
        for result in successful_results:
            metrics = result['metrics']
            if (metrics['sharpe'] >= sharpe_threshold and
                metrics['fitness'] >= fitness_threshold and
                metrics['long_count'] >= long_threshold and
                metrics['short_count'] >= short_threshold):
                passed_strategies.append(result)

        # 按夏普比率排序
        passed_strategies.sort(key=lambda x: x['metrics']['sharpe'], reverse=True)

        # 获取前10个策略
        top_strategies = passed_strategies[:10]

        return {
            'total': len(results),
            'successful': len(successful_results),
            'failed': len(results) - len(successful_results),
            'passed': len(passed_strategies),
            'pass_rate': len(passed_strategies) / len(successful_results) if successful_results else 0,
            'stats': stats,
            'top_strategies': top_strategies
        }

    def compare_strategies(
        self,
        strategies: List[Dict[str, Any]],
        metrics: List[str] = ['sharpe', 'fitness', 'returns', 'turnover']
    ) -> pd.DataFrame:
        """
        比较多个策略

        Args:
            strategies: 策略列表
            metrics: 要比较的指标

        Returns:
            比较结果 DataFrame
        """
        # 提取指标数据
        data = []
        for strategy in strategies:
            if not strategy.get('success'):
                continue

            row = {
                'code': strategy['code'],
                'simulation_id': strategy['simulation_id']
            }

            for metric in metrics:
                row[metric] = strategy['metrics'].get(metric, 0)

            data.append(row)

        # 创建 DataFrame
        df = pd.DataFrame(data)

        return df

    def generate_report(
        self,
        results: List[Dict[str, Any]],
        output_file: Optional[str] = None
    ) -> str:
        """
        生成回测报告

        Args:
            results: 回测结果列表
            output_file: 输出文件路径（可选）

        Returns:
            报告内容
        """
        # 分析结果
        analysis = self.analyze_results(results)

        # 构建报告
        report = []
        report.append("# WorldQuant 策略回测报告")
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # 总体统计
        report.append("## 总体统计")
        report.append(f"总策略数: {analysis['total']}")
        report.append(f"成功回测: {analysis['successful']}")
        report.append(f"失败回测: {analysis['failed']}")
        report.append(f"通过筛选: {analysis['passed']}")
        report.append(f"通过率: {analysis['pass_rate']:.2%}")
        report.append("")

        # 指标统计
        report.append("## 指标统计")
        for metric, stats in analysis['stats'].items():
            report.append(f"### {metric.capitalize()}")
            report.append(f"平均值: {stats['mean']:.4f}")
            report.append(f"标准差: {stats['std']:.4f}")
            report.append(f"最小值: {stats['min']:.4f}")
            report.append(f"最大值: {stats['max']:.4f}")
            report.append(f"中位数: {stats['median']:.4f}")
            report.append("")

        # 顶级策略
        report.append("## 顶级策略 (Top 10)")
        for i, strategy in enumerate(analysis['top_strategies'], 1):
            metrics = strategy['metrics']
            report.append(f"{i}. {strategy['code'][:80]}...")
            report.append(f"   Sharpe: {metrics['sharpe']:.4f}, Fitness: {metrics['fitness']:.4f}")
            report.append(f"   Returns: {metrics['returns']:.4f}, Long: {metrics['long_count']}, Short: {metrics['short_count']}")
            report.append("")

        # 合并报告
        report_text = "".join(report)

        # 如果指定了输出文件，则保存
        if output_file:
            try:
                with open(output_file, 'w') as f:
                    f.write(report_text)
                logger.info(f"报告已保存到: {output_file}")
            except Exception as e:
                logger.error(f"保存报告失败: {str(e)}")

        return report_text

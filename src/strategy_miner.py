
"""
WorldQuant 策略挖掘模块
用于自动挖掘和优化 WorldQuant 策略
"""

import pandas as pd
import numpy as np
import random
import itertools
from typing import Dict, List, Tuple, Optional, Any
from loguru import logger
import os
import asyncio
import time
from datetime import datetime

from .worldquant_client import WorldQuantClient


class StrategyMiner:
    """WorldQuant 策略挖掘器"""

    def __init__(self, client: WorldQuantClient, datasets_dir: str):
        """
        初始化策略挖掘器

        Args:
            client: WorldQuant 客户端
            datasets_dir: 数据集目录
        """
        self.client = client
        self.datasets_dir = datasets_dir
        self.dataset_cache = {}  # 数据集缓存
        self.datafields_cache = {}  # 数据字段缓存

        # 加载数据集信息
        self._load_datasets_info()

        # 策略模板
        self.templates = [
            "rank({field})",
            "ts_rank({field}, {window})",
            "delta({field}, {window})",
            "ts_mean({field}, {window})",
            "ts_std_dev({field}, {window})",
            "ts_corr({field1}, {field2}, {window})",
            "ts_covariance({field1}, {field2}, {window})",
            "ts_sum({field}, {window})",
            "ts_product({field}, {window})",
            "ts_min({field}, {window})",
            "ts_max({field}, {window})",
            "ts_arg_min({field}, {window})",
            "ts_arg_max({field}, {window})",
            "ts_weighted_mean({field}, {weight_field}, {window})",
            "ts_linear_decay({field}, {window})",
            "ts_exponential_decay({field}, {window})",
            "ts_zscore({field}, {window})",
            "ts_returns({field}, {window})",
            "ts_delta_log({field}, {window})",
            "ts_rank_linear_decay({field}, {window})",
            "ts_rank_exponential_decay({field}, {window})",
            "neutralize({field}, {neutralization})",
            "zscore({field})",
            "rank({field}) - rank({field2})",
            "rank({field}) / rank({field2})",
            "rank({field}) * rank({field2})",
            "rank({field}) + rank({field2})",
            "rank({field}) > rank({field2})",
            "rank({field}) < rank({field2})",
            "rank({field}) >= rank({field2})",
            "rank({field}) <= rank({field2})",
            "rank({field}) != rank({field2})",
            "rank({field}) == rank({field2})",
            "rank({field}) && rank({field2})",
            "rank({field}) || rank({field2})",
            "rank({field}) ? rank({field2}) : rank({field3})",
            "rank({field}) * (rank({field2}) > rank({field3}))",
        ]

        # 窗口大小选项
        self.windows = [1, 2, 3, 5, 10, 20, 30, 60, 120]

        # 中性化选项
        self.neutralizations = ["SECTOR", "SUBINDUSTRY", "INDUSTRY"]

    def _load_datasets_info(self):
        """加载数据集信息"""
        try:
            for filename in os.listdir(self.datasets_dir):
                if filename.endswith('_datafields.csv'):
                    dataset_id = filename.replace('_datafields.csv', '')
                    dataset_file = os.path.join(self.datasets_dir, filename)
                    df = pd.read_csv(dataset_file)
                    self.dataset_cache[dataset_id] = df
                    logger.info(f"加载数据集: {dataset_id}, 共 {len(df)} 个字段")
        except Exception as e:
            logger.error(f"加载数据集信息失败: {str(e)}")

    def get_datafields(self, dataset_id: str, category: Optional[str] = None) -> List[str]:
        """
        获取指定数据集的数据字段

        Args:
            dataset_id: 数据集ID
            category: 字段类别（可选）

        Returns:
            数据字段列表
        """
        if dataset_id not in self.dataset_cache:
            logger.warning(f"数据集不存在: {dataset_id}")
            return []

        df = self.dataset_cache[dataset_id]

        # 如果指定了类别，则过滤
        if category:
            # 尝试解析 category 字段
            if 'category' in df.columns:
                try:
                    # category 字段可能是 JSON 字符串，需要解析
                    category_filter = df['category'].apply(
                        lambda x: isinstance(x, str) and category.lower() in x.lower()
                    )
                    df = df[category_filter]
                except Exception as e:
                    logger.warning(f"过滤类别失败: {str(e)}")

        # 返回字段 ID 列表
        if 'id' in df.columns:
            return df['id'].tolist()
        else:
            logger.warning(f"数据集 {dataset_id} 中没有 id 列")
            return []

    def generate_strategy(
        self, 
        dataset_id: str,
        template: Optional[str] = None,
        fields: Optional[List[str]] = None,
        max_complexity: int = 3
    ) -> str:
        """
        生成策略代码

        Args:
            dataset_id: 数据集ID
            template: 策略模板（可选）
            fields: 字段列表（可选）
            max_complexity: 最大复杂度

        Returns:
            策略代码
        """
        # 如果没有提供字段，则从数据集中随机选择
        if not fields:
            fields = self.get_datafields(dataset_id)
            if not fields:
                logger.error(f"无法从数据集 {dataset_id} 获取字段")
                return ""

        # 如果没有提供模板，则随机选择
        if not template:
            template = random.choice(self.templates)

        # 替换模板中的占位符
        strategy = template

        # 替换字段占位符
        field_count = template.count("{field}")
        field1_count = template.count("{field1}")
        field2_count = template.count("{field2}")
        field3_count = template.count("{field3}")
        weight_field_count = template.count("{weight_field}")

        # 随机选择字段
        if field_count > 0:
            selected_fields = random.sample(fields, min(field_count, len(fields)))
            for i, field in enumerate(selected_fields):
                strategy = strategy.replace("{field}", field, 1)

        if field1_count > 0:
            field1 = random.choice(fields)
            strategy = strategy.replace("{field1}", field1)

        if field2_count > 0:
            field2 = random.choice(fields)
            strategy = strategy.replace("{field2}", field2)

        if field3_count > 0:
            field3 = random.choice(fields)
            strategy = strategy.replace("{field3}", field3)

        if weight_field_count > 0:
            weight_field = random.choice(fields)
            strategy = strategy.replace("{weight_field}", weight_field)

        # 替换窗口占位符
        window_count = template.count("{window}")
        if window_count > 0:
            for _ in range(window_count):
                window = random.choice(self.windows)
                strategy = strategy.replace("{window}", str(window), 1)

        # 替换中性化占位符
        neutralization_count = template.count("{neutralization}")
        if neutralization_count > 0:
            for _ in range(neutralization_count):
                neutralization = random.choice(self.neutralizations)
                strategy = strategy.replace("{neutralization}", neutralization, 1)

        # 如果需要，增加复杂度
        if max_complexity > 1:
            complexity = random.randint(2, max_complexity)
            for _ in range(complexity - 1):
                sub_template = random.choice(self.templates)
                # 随机选择字段
                sub_fields = random.sample(fields, min(3, len(fields)))
                sub_strategy = sub_template

                # 替换子模板中的占位符
                sub_field_count = sub_template.count("{field}")
                sub_field1_count = sub_template.count("{field1}")
                sub_field2_count = sub_template.count("{field2}")
                sub_field3_count = sub_template.count("{field3}")

                if sub_field_count > 0:
                    selected_fields = random.sample(sub_fields, min(sub_field_count, len(sub_fields)))
                    for i, field in enumerate(selected_fields):
                        sub_strategy = sub_strategy.replace("{field}", field, 1)

                if sub_field1_count > 0:
                    sub_field1 = random.choice(sub_fields)
                    sub_strategy = sub_strategy.replace("{field1}", sub_field1)

                if sub_field2_count > 0:
                    sub_field2 = random.choice(sub_fields)
                    sub_strategy = sub_strategy.replace("{field2}", sub_field2)

                if sub_field3_count > 0:
                    sub_field3 = random.choice(sub_fields)
                    sub_strategy = sub_strategy.replace("{field3}", sub_field3)

                # 替换窗口占位符
                sub_window_count = sub_template.count("{window}")
                if sub_window_count > 0:
                    for _ in range(sub_window_count):
                        window = random.choice(self.windows)
                        sub_strategy = sub_strategy.replace("{window}", str(window), 1)

                # 将子策略添加到主策略中
                operator = random.choice(["+", "-", "*", "/", ">", "<", ">=", "<="])
                strategy = f"({strategy}) {operator} ({sub_strategy})"

        return strategy

    async def mine_strategies(
        self,
        dataset_id: str,
        region: str = "USA",
        delay: int = 1,
        universe: str = "TOP3000",
        neutralization: str = "SUBINDUSTRY",
        decay: int = 5,
        instrument_type: str = "EQUITY",
        max_strategies: int = 100,
        max_complexity: int = 3,
        sharpe_threshold: float = 0.75,
        fitness_threshold: float = 0.5,
        long_threshold: int = 100,
        short_threshold: int = 100,
        n_jobs: int = 3,
        callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        挖掘策略

        Args:
            dataset_id: 数据集ID
            region: 区域
            delay: 延迟
            universe: 股票池
            neutralization: 中性化方式
            decay: 衰减
            instrument_type: 资产类型
            max_strategies: 最大策略数量
            max_complexity: 最大复杂度
            sharpe_threshold: 夏普比率阈值
            fitness_threshold: 适应度阈值
            long_threshold: 多头阈值
            short_threshold: 空头阈值
            n_jobs: 并发数
            callback: 回调函数

        Returns:
            策略列表
        """
        results = []

        # 获取数据字段
        fields = self.get_datafields(dataset_id)
        if not fields:
            logger.error(f"无法从数据集 {dataset_id} 获取字段")
            return results

        # 限制字段数量，避免过多
        if len(fields) > 100:
            fields = random.sample(fields, 100)

        # 创建并发任务
        semaphore = asyncio.Semaphore(n_jobs)

        async def simulate_strategy(strategy: str, index: int) -> Optional[Dict[str, Any]]:
            """模拟单个策略"""
            async with semaphore:
                try:
                    # 调用回调函数
                    if callback:
                        callback({
                            'status': 'simulating',
                            'index': index,
                            'total': max_strategies,
                            'strategy': strategy[:50] + "..." if len(strategy) > 50 else strategy
                        })

                    # 模拟策略
                    result = await self.client.simulate(
                        code=strategy,
                        region=region,
                        delay=delay,
                        universe=universe,
                        neutralization=neutralization,
                        decay=decay,
                        instrument_type=instrument_type
                    )

                    if not result.get('success'):
                        return None

                    # 获取模拟结果
                    simulation_id = result['data'].get('id')
                    if not simulation_id:
                        return None

                    # 等待模拟完成
                    for _ in range(30):  # 最多等待30次
                        await asyncio.sleep(2)
                        sim_result = await self.client.get_simulation_result(simulation_id)
                        if sim_result.get('success'):
                            data = sim_result.get('data', {})
                            if data.get('isCompleted'):
                                # 检查是否满足阈值条件
                                sharpe = data.get('sharpe', 0)
                                fitness = data.get('fitness', 0)
                                long_count = data.get('longCount', 0)
                                short_count = data.get('shortCount', 0)

                                if (sharpe >= sharpe_threshold and 
                                    fitness >= fitness_threshold and 
                                    long_count >= long_threshold and 
                                    short_count >= short_threshold):
                                    return {
                                        'strategy': strategy,
                                        'sharpe': sharpe,
                                        'fitness': fitness,
                                        'longCount': long_count,
                                        'shortCount': short_count,
                                        'simulation_id': simulation_id,
                                        'metrics': data
                                    }
                                break

                    return None
                except Exception as e:
                    logger.error(f"模拟策略异常: {str(e)}")
                    return None

        # 生成并模拟策略
        tasks = []
        for i in range(max_strategies):
            strategy = self.generate_strategy(dataset_id, max_complexity=max_complexity)
            if strategy:
                tasks.append(simulate_strategy(strategy, i + 1))

        # 等待所有任务完成
        if tasks:
            results_list = await asyncio.gather(*tasks)
            results = [r for r in results_list if r is not None]

        # 按夏普比率排序
        results.sort(key=lambda x: x.get('sharpe', 0), reverse=True)

        return results

    async def optimize_strategy(
        self,
        base_strategy: str,
        dataset_id: str,
        region: str = "USA",
        delay: int = 1,
        universe: str = "TOP3000",
        neutralization: str = "SUBINDUSTRY",
        decay: int = 5,
        instrument_type: str = "EQUITY",
        max_iterations: int = 50,
        n_jobs: int = 3,
        callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        优化策略

        Args:
            base_strategy: 基础策略
            dataset_id: 数据集ID
            region: 区域
            delay: 延迟
            universe: 股票池
            neutralization: 中性化方式
            decay: 衰减
            instrument_type: 资产类型
            max_iterations: 最大迭代次数
            n_jobs: 并发数
            callback: 回调函数

        Returns:
            优化后的策略
        """
        # 获取基础策略的表现
        base_result = await self.client.simulate(
            code=base_strategy,
            region=region,
            delay=delay,
            universe=universe,
            neutralization=neutralization,
            decay=decay,
            instrument_type=instrument_type
        )

        if not base_result.get('success'):
            return {'success': False, 'error': '基础策略模拟失败'}

        # 获取模拟结果
        simulation_id = base_result['data'].get('id')
        if not simulation_id:
            return {'success': False, 'error': '无法获取模拟ID'}

        # 等待模拟完成
        base_metrics = None
        for _ in range(30):
            await asyncio.sleep(2)
            sim_result = await self.client.get_simulation_result(simulation_id)
            if sim_result.get('success'):
                data = sim_result.get('data', {})
                if data.get('isCompleted'):
                    base_metrics = data
                    break

        if not base_metrics:
            return {'success': False, 'error': '基础策略模拟未完成'}

        best_strategy = base_strategy
        best_sharpe = base_metrics.get('sharpe', 0)
        best_fitness = base_metrics.get('fitness', 0)

        # 获取数据字段
        fields = self.get_datafields(dataset_id)
        if not fields:
            return {'success': False, 'error': '无法获取数据字段'}

        # 限制字段数量，避免过多
        if len(fields) > 50:
            fields = random.sample(fields, 50)

        # 优化策略
        for iteration in range(max_iterations):
            # 调用回调函数
            if callback:
                callback({
                    'status': 'optimizing',
                    'iteration': iteration + 1,
                    'total': max_iterations,
                    'best_sharpe': best_sharpe,
                    'best_fitness': best_fitness
                })

            # 生成变体策略
            variant = self._generate_variant(best_strategy, fields)

            # 模拟变体策略
            variant_result = await self.client.simulate(
                code=variant,
                region=region,
                delay=delay,
                universe=universe,
                neutralization=neutralization,
                decay=decay,
                instrument_type=instrument_type
            )

            if not variant_result.get('success'):
                continue

            # 获取模拟结果
            variant_simulation_id = variant_result['data'].get('id')
            if not variant_simulation_id:
                continue

            # 等待模拟完成
            variant_metrics = None
            for _ in range(30):
                await asyncio.sleep(2)
                sim_result = await self.client.get_simulation_result(variant_simulation_id)
                if sim_result.get('success'):
                    data = sim_result.get('data', {})
                    if data.get('isCompleted'):
                        variant_metrics = data
                        break

            if not variant_metrics:
                continue

            # 比较表现
            variant_sharpe = variant_metrics.get('sharpe', 0)
            variant_fitness = variant_metrics.get('fitness', 0)

            # 如果变体策略更好，则更新最佳策略
            if (variant_sharpe > best_sharpe or 
                (variant_sharpe == best_sharpe and variant_fitness > best_fitness)):
                best_strategy = variant
                best_sharpe = variant_sharpe
                best_fitness = variant_fitness

        return {
            'success': True,
            'original_strategy': base_strategy,
            'optimized_strategy': best_strategy,
            'original_sharpe': base_metrics.get('sharpe', 0),
            'optimized_sharpe': best_sharpe,
            'original_fitness': base_metrics.get('fitness', 0),
            'optimized_fitness': best_fitness
        }

    def _generate_variant(self, strategy: str, fields: List[str]) -> str:
        """
        生成策略变体

        Args:
            strategy: 原始策略
            fields: 可用字段列表

        Returns:
            变体策略
        """
        # 随机选择一个变换
        transform = random.choice([
            'replace_field',
            'change_window',
            'add_neutralization',
            'change_operator',
            'add_complexity'
        ])

        if transform == 'replace_field':
            # 替换字段
            if '{field}' in strategy:
                new_field = random.choice(fields)
                variant = strategy.replace('{field}', new_field, 1)
            elif '{field1}' in strategy:
                new_field = random.choice(fields)
                variant = strategy.replace('{field1}', new_field)
            elif '{field2}' in strategy:
                new_field = random.choice(fields)
                variant = strategy.replace('{field2}', new_field)
            else:
                variant = strategy

        elif transform == 'change_window':
            # 改变窗口大小
            if '{window}' in strategy:
                new_window = random.choice(self.windows)
                variant = strategy.replace('{window}', str(new_window), 1)
            else:
                variant = strategy

        elif transform == 'add_neutralization':
            # 添加中性化
            if 'neutralize' not in strategy:
                neutralization = random.choice(self.neutralizations)
                variant = f"neutralize({strategy}, {neutralization})"
            else:
                variant = strategy

        elif transform == 'change_operator':
            # 改变运算符
            operators = ['+', '-', '*', '/', '>', '<', '>=', '<=']
            for op in operators:
                if op in strategy:
                    new_op = random.choice([o for o in operators if o != op])
                    variant = strategy.replace(op, new_op, 1)
                    break
            else:
                variant = strategy

        else:  # add_complexity
            # 增加复杂度
            sub_template = random.choice(self.templates)
            sub_fields = random.sample(fields, min(3, len(fields)))
            sub_strategy = sub_template

            # 替换子模板中的占位符
            sub_field_count = sub_template.count("{field}")
            sub_field1_count = sub_template.count("{field1}")
            sub_field2_count = sub_template.count("{field2}")

            if sub_field_count > 0:
                selected_fields = random.sample(sub_fields, min(sub_field_count, len(sub_fields)))
                for i, field in enumerate(selected_fields):
                    sub_strategy = sub_strategy.replace("{field}", field, 1)

            if sub_field1_count > 0:
                sub_field1 = random.choice(sub_fields)
                sub_strategy = sub_strategy.replace("{field1}", sub_field1)

            if sub_field2_count > 0:
                sub_field2 = random.choice(sub_fields)
                sub_strategy = sub_strategy.replace("{field2}", sub_field2)

            # 替换窗口占位符
            sub_window_count = sub_template.count("{window}")
            if sub_window_count > 0:
                for _ in range(sub_window_count):
                    window = random.choice(self.windows)
                    sub_strategy = sub_strategy.replace("{window}", str(window), 1)

            # 将子策略添加到主策略中
            operator = random.choice(["+", "-", "*", "/"])
            variant = f"({strategy}) {operator} ({sub_strategy})"

        return variant

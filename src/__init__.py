
"""
WorldQuant 策略工具包
"""

from .worldquant_client import WorldQuantClient
from .strategy_miner import StrategyMiner
from .backtest import BacktestEngine

__all__ = [
    'WorldQuantClient',
    'StrategyMiner',
    'BacktestEngine'
]

__version__ = '1.0.0'


"""
WorldQuant API 客户端模块
用于与 WorldQuant Brain 平台进行交互
"""

import requests
import json
from os.path import expanduser
from requests.auth import HTTPBasicAuth

import aiohttp
import asyncio
from typing import Dict, List, Optional, Any
from loguru import logger
import os



class WorldQuantClient:
    """WorldQuant Brain API 客户端"""

    def __init__(self, username: str, password: str):
        """
        初始化 WorldQuant 客户端

        Args:
            username: WorldQuant Brain 用户名
            password: WorldQuant Brain 密码
        """
        self.username = username
        self.password = password
        self.session = None
        self.base_url = "https://api.worldquantbrain.com"
        self.token = None
        self._is_logged_in = False

    async def login(self) -> bool:
        """
        登录 WorldQuant Brain

        Returns:
            登录是否成功
        """
        if self._is_logged_in:
            return True

        if not self.session:
            # 创建一个禁用 SSL 证书验证的连接器（仅用于开发环境）
            connector = aiohttp.TCPConnector(ssl=False)
            self.session = aiohttp.ClientSession(connector=connector)
            sess = requests.Session()    
            sess.auth = HTTPBasicAuth(self.username, self.password)
            response = sess.post(f"{self.base_url}/authentication")
            result = response.json()

            print(response.status_code)
            print('response.json()', response.json())

            self.token = result.get('token')
            self._is_logged_in = True
            logger.info(f"WorldQuant API 登录成功: {self.username}")
            return True

    async def logout(self) -> bool:
        """
        登出 WorldQuant Brain

        Returns:
            登出是否成功
        """
        try:
            if self.session and self._is_logged_in:
                headers = {"Authorization": f"Bearer {self.token}"}
                async with self.session.post(f"{self.base_url}/authentication/logout", headers=headers) as response:
                    if response.status in [200, 204]:
                        self._is_logged_in = False
                        self.token = None
                        logger.info("WorldQuant API 登出成功")
                        return True
                    else:
                        logger.error(f"WorldQuant API 登出失败: {response.status}")
                        return False
            return False
        except Exception as e:
            logger.error(f"WorldQuant API 登出异常: {str(e)}")
            return False

    async def close(self):
        """关闭会话"""
        if self.session:
            await self.session.close()
            self.session = None

    async def get_datasets(self) -> List[Dict[str, Any]]:
        """
        获取可用的数据集列表

        Returns:
            数据集列表
        """
        if not self._is_logged_in:
            if not await self.login():
                return []

        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            async with self.session.get(
                f"{self.base_url}/api/datasets",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('datasets', [])
                else:
                    logger.error(f"获取数据集失败: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"获取数据集异常: {str(e)}")
            return []

    async def get_datafields(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        获取指定数据集的数据字段

        Args:
            dataset_id: 数据集ID

        Returns:
            数据字段列表
        """
        if not self._is_logged_in:
            if not await self.login():
                return []

        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            async with self.session.get(
                f"{self.base_url}/data/{dataset_id}/datafields",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('datafields', [])
                else:
                    logger.error(f"获取数据字段失败: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"获取数据字段异常: {str(e)}")
            return []

    async def simulate(
        self,
        code: str,
        region: str = "USA",
        delay: int = 1,
        universe: str = "TOP3000",
        neutralization: str = "SUBINDUSTRY",
        decay: int = 5,
        instrument_type: str = "EQUITY"
    ) -> Dict[str, Any]:
        """
        模拟因子表现

        Args:
            code: 因子代码
            region: 区域
            delay: 延迟
            universe: 股票池
            neutralization: 中性化方式
            decay: 衰减
            instrument_type: 资产类型

        Returns:
            模拟结果
        """
        if not self._is_logged_in:
            if not await self.login():
                return {'success': False, 'error': '登录失败'}

        try:
            data = {
                "code": code,
                "settings": {
                    "region": region,
                    "delay": delay,
                    "universe": universe,
                    "neutralization": neutralization,
                    "decay": decay,
                    "instrumentType": instrument_type
                }
            }

            headers = {"Authorization": f"Bearer {self.token}"}
            async with self.session.post(
                f"{self.base_url}/simulations",
                json=data,
                headers=headers
            ) as response:
                if response.status == 201:
                    result = await response.json()
                    logger.info(f"因子模拟成功: {code[:20]}...")
                    return {'success': True, 'data': result}
                else:
                    error_text = await response.text()
                    logger.error(f"因子模拟失败: {response.status}, {error_text}")
                    return {'success': False, 'error': error_text}
        except Exception as e:
            logger.error(f"因子模拟异常: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def get_simulation_result(self, simulation_id: str) -> Dict[str, Any]:
        """
        获取模拟结果

        Args:
            simulation_id: 模拟ID

        Returns:
            模拟结果
        """
        if not self._is_logged_in:
            if not await self.login():
                return {'success': False, 'error': '登录失败'}

        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            async with self.session.get(
                f"{self.base_url}/simulations/{simulation_id}",
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {'success': True, 'data': result}
                else:
                    logger.error(f"获取模拟结果失败: {response.status}")
                    return {'success': False, 'error': f"HTTP {response.status}"}
        except Exception as e:
            logger.error(f"获取模拟结果异常: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def create_alpha(
        self,
        code: str,
        name: str,
        description: str = "",
        region: str = "USA",
        delay: int = 1,
        universe: str = "TOP3000",
        neutralization: str = "SUBINDUSTRY",
        decay: int = 5,
        instrument_type: str = "EQUITY"
    ) -> Dict[str, Any]:
        """
        创建 Alpha 因子

        Args:
            code: 因子代码
            name: 因子名称
            description: 因子描述
            region: 区域
            delay: 延迟
            universe: 股票池
            neutralization: 中性化方式
            decay: 衰减
            instrument_type: 资产类型

        Returns:
            创建结果
        """
        if not self._is_logged_in:
            if not await self.login():
                return {'success': False, 'error': '登录失败'}

        try:
            data = {
                "code": code,
                "name": name,
                "description": description,
                "settings": {
                    "region": region,
                    "delay": delay,
                    "universe": universe,
                    "neutralization": neutralization,
                    "decay": decay,
                    "instrumentType": instrument_type
                }
            }

            headers = {"Authorization": f"Bearer {self.token}"}
            async with self.session.post(
                f"{self.base_url}/alphas",
                json=data,
                headers=headers
            ) as response:
                if response.status == 201:
                    result = await response.json()
                    logger.info(f"Alpha 创建成功: {name}")
                    return {'success': True, 'data': result}
                else:
                    error_text = await response.text()
                    logger.error(f"Alpha 创建失败: {response.status}, {error_text}")
                    return {'success': False, 'error': error_text}
        except Exception as e:
            logger.error(f"Alpha 创建异常: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def get_alpha_performance(self, alpha_id: str) -> Dict[str, Any]:
        """
        获取 Alpha 因子表现

        Args:
            alpha_id: Alpha ID

        Returns:
            Alpha 表现数据
        """
        if not self._is_logged_in:
            if not await self.login():
                return {'success': False, 'error': '登录失败'}

        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            async with self.session.get(
                f"{self.base_url}/alphas/{alpha_id}/performance",
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {'success': True, 'data': result}
                else:
                    logger.error(f"获取 Alpha 表现失败: {response.status}")
                    return {'success': False, 'error': f"HTTP {response.status}"}
        except Exception as e:
            logger.error(f"获取 Alpha 表现异常: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def get_alpha_list(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        获取 Alpha 因子列表

        Args:
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            Alpha 列表
        """
        if not self._is_logged_in:
            if not await self.login():
                return {'success': False, 'error': '登录失败'}

        try:
            params = {
                "limit": limit,
                "offset": offset
            }

            headers = {"Authorization": f"Bearer {self.token}"}
            async with self.session.get(
                f"{self.base_url}/alphas",
                params=params,
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {'success': True, 'data': result}
                else:
                    logger.error(f"获取 Alpha 列表失败: {response.status}")
                    return {'success': False, 'error': f"HTTP {response.status}"}
        except Exception as e:
            logger.error(f"获取 Alpha 列表异常: {str(e)}")
            return {'success': False, 'error': str(e)}


async def create_client_from_file(user_info_file: str) -> Optional[WorldQuantClient]:
    """
    从用户信息文件创建 WorldQuant 客户端

    Args:
        user_info_file: 用户信息文件路径

    Returns:
        WorldQuant 客户端实例
    """
    try:
        with open(user_info_file, 'r') as f:
            content = f.read()
            # 解析用户名和密码
            username = content.split("username: '")[1].split("'")[0]
            password = content.split("password: '")[1].split("'")[0]

        client = WorldQuantClient(username, password)
        return client
    except Exception as e:
        logger.error(f"从文件创建客户端失败: {str(e)}")
        return None

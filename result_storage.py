"""
选股结果存储模块
用于保存和读取选股结果，避免重复执行
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from pydantic import BaseModel

logger = logging.getLogger("result_storage")


class StockSelectionResult(BaseModel):
    """单个策略的选股结果"""
    selector_name: str
    alias: str
    trade_date: str
    selected_stocks: List[str]
    scores: Optional[Dict[str, float]] = None
    count: int

    class Config:
        json_encoders = {
            # 确保日期和浮点数正确序列化
        }


class ResultStorage:
    """选股结果存储管理器"""
    
    def __init__(self, result_dir: Path = Path("./result")):
        """
        初始化结果存储管理器
        
        Args:
            result_dir: 结果存储目录，默认为 ./result
        """
        self.result_dir = Path(result_dir)
        self.result_dir.mkdir(parents=True, exist_ok=True)
        logger.info("结果存储目录: %s", self.result_dir.absolute())
    
    def get_result_path(self, trade_date: str, selector_name: str) -> Path:
        """
        获取指定日期和策略的结果文件路径
        
        Args:
            trade_date: 交易日，格式 YYYY-MM-DD
            selector_name: 策略类名
        
        Returns:
            结果文件路径
        """
        date_dir = self.result_dir / trade_date
        date_dir.mkdir(parents=True, exist_ok=True)
        return date_dir / f"{selector_name}.json"
    
    def save_result(self, result: StockSelectionResult) -> bool:
        """
        保存选股结果到文件
        
        Args:
            result: 选股结果
        
        Returns:
            是否保存成功
        """
        try:
            result_path = self.get_result_path(result.trade_date, result.selector_name)
            
            # 转换为字典并保存
            result_dict = result.dict()
            with result_path.open("w", encoding="utf-8") as f:
                json.dump(result_dict, f, ensure_ascii=False, indent=2)
            
            logger.info("已保存选股结果: %s -> %s", result.alias, result_path)
            return True
            
        except Exception as e:
            logger.error("保存选股结果失败: %s", e, exc_info=True)
            return False
    
    def load_result(self, trade_date: str, selector_name: str) -> Optional[StockSelectionResult]:
        """
        从文件加载选股结果
        
        Args:
            trade_date: 交易日，格式 YYYY-MM-DD
            selector_name: 策略类名
        
        Returns:
            选股结果，如果不存在则返回 None
        """
        try:
            result_path = self.get_result_path(trade_date, selector_name)
            
            if not result_path.exists():
                return None
            
            with result_path.open("r", encoding="utf-8") as f:
                result_dict = json.load(f)
            
            result = StockSelectionResult(**result_dict)
            logger.info("已加载选股结果: %s <- %s", result.alias, result_path)
            return result
            
        except Exception as e:
            logger.error("加载选股结果失败: %s", e, exc_info=True)
            return None
    
    def result_exists(self, trade_date: str, selector_name: str) -> bool:
        """
        检查指定日期和策略的结果是否存在
        
        Args:
            trade_date: 交易日，格式 YYYY-MM-DD
            selector_name: 策略类名
        
        Returns:
            结果是否存在
        """
        result_path = self.get_result_path(trade_date, selector_name)
        return result_path.exists()
    
    def save_all_results(self, results: List[StockSelectionResult]) -> Dict[str, bool]:
        """
        批量保存选股结果
        
        Args:
            results: 选股结果列表
        
        Returns:
            保存状态字典，key为策略名称，value为是否成功
        """
        status = {}
        for result in results:
            status[result.selector_name] = self.save_result(result)
        return status
    
    def load_all_results(self, trade_date: str, selector_names: Optional[List[str]] = None) -> Dict[str, StockSelectionResult]:
        """
        加载指定日期的所有选股结果
        
        Args:
            trade_date: 交易日，格式 YYYY-MM-DD
            selector_names: 策略名称列表，如果为None则加载所有
        
        Returns:
            结果字典，key为策略名称，value为选股结果
        """
        results = {}
        date_dir = self.result_dir / trade_date
        
        if not date_dir.exists():
            return results
        
        # 如果指定了策略列表，只加载这些策略
        if selector_names:
            for selector_name in selector_names:
                result = self.load_result(trade_date, selector_name)
                if result:
                    results[selector_name] = result
        else:
            # 加载所有策略的结果
            for result_file in date_dir.glob("*.json"):
                selector_name = result_file.stem
                result = self.load_result(trade_date, selector_name)
                if result:
                    results[selector_name] = result
        
        return results
    
    def list_available_dates(self) -> List[str]:
        """
        列出所有有结果的日期
        
        Returns:
            日期列表，格式 YYYY-MM-DD
        """
        dates = []
        if not self.result_dir.exists():
            return dates
        
        for date_dir in self.result_dir.iterdir():
            if date_dir.is_dir():
                try:
                    # 验证是否为有效日期格式
                    datetime.strptime(date_dir.name, "%Y-%m-%d")
                    dates.append(date_dir.name)
                except ValueError:
                    continue
        
        return sorted(dates, reverse=True)  # 最新的在前
    
    def list_available_selectors(self, trade_date: str) -> List[str]:
        """
        列出指定日期可用的策略结果
        
        Args:
            trade_date: 交易日，格式 YYYY-MM-DD
        
        Returns:
            策略名称列表
        """
        selectors = []
        date_dir = self.result_dir / trade_date
        
        if not date_dir.exists():
            return selectors
        
        for result_file in date_dir.glob("*.json"):
            selectors.append(result_file.stem)
        
        return sorted(selectors)


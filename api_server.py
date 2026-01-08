"""
选股服务 API 服务器
提供 RESTful API 接口来执行选股功能
"""

from __future__ import annotations

import importlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 导入选股相关函数
from select_stock import load_data, load_config, instantiate_selector
from result_storage import ResultStorage, StockSelectionResult as StorageResult

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("api")

# 创建 FastAPI 应用
app = FastAPI(
    title="选股服务 API",
    description="提供Z哥战法选股功能的RESTful API接口",
    version="1.0.0",
)

# 全局配置
DEFAULT_DATA_DIR = Path("./data")
DEFAULT_CONFIG_PATH = Path("./configs.json")
DEFAULT_RESULT_DIR = Path("./result")

# 初始化结果存储
result_storage = ResultStorage(DEFAULT_RESULT_DIR)


# ========== 请求/响应模型 ==========

class SelectorConfig(BaseModel):
    """选股策略配置"""
    class_name: str = Field(..., description="选择器类名")
    alias: Optional[str] = Field(None, description="策略别名")
    activate: bool = Field(True, description="是否激活")
    params: Dict[str, Any] = Field(default_factory=dict, description="策略参数")


class StockSelectionRequest(BaseModel):
    """选股请求"""
    date: Optional[str] = Field(None, description="交易日 YYYY-MM-DD，默认使用最新日期")
    data_dir: Optional[str] = Field(None, description="数据目录路径，默认 ./data")
    config_path: Optional[str] = Field(None, description="配置文件路径，默认 ./configs.json")
    tickers: Optional[List[str]] = Field(None, description="股票代码列表，默认使用所有股票")
    selector_configs: Optional[List[SelectorConfig]] = Field(
        None, 
        description="自定义选股策略配置，如果提供则覆盖配置文件"
    )
    use_cache: bool = Field(True, description="是否使用缓存结果，如果存在则直接返回")
    save_result: bool = Field(True, description="是否保存选股结果到文件")


class StockSelectionResult(BaseModel):
    """单个策略的选股结果"""
    selector_name: str = Field(..., description="策略名称")
    alias: str = Field(..., description="策略别名")
    trade_date: str = Field(..., description="交易日")
    selected_stocks: List[str] = Field(..., description="选中的股票代码列表")
    scores: Optional[Dict[str, float]] = Field(None, description="股票评分（如果有）")
    count: int = Field(..., description="选中股票数量")


class StockSelectionResponse(BaseModel):
    """选股响应"""
    success: bool = Field(..., description="是否成功")
    trade_date: str = Field(..., description="交易日")
    results: List[StockSelectionResult] = Field(..., description="各策略的选股结果")
    message: Optional[str] = Field(None, description="消息")


class SelectorInfo(BaseModel):
    """选股策略信息"""
    class_name: str = Field(..., description="类名")
    alias: str = Field(..., description="别名")
    description: Optional[str] = Field(None, description="描述")


# ========== 工具函数 ==========

def run_selection(
    trade_date: Optional[pd.Timestamp],
    data_dir: Path,
    config_path: Path,
    tickers: Optional[List[str]] = None,
    selector_configs: Optional[List[Dict[str, Any]]] = None,
    use_cache: bool = True,
    save_result: bool = True,
    storage: Optional[ResultStorage] = None,
) -> List[StockSelectionResult]:
    """
    执行选股逻辑
    
    Args:
        trade_date: 交易日，如果为None则使用数据最新日期
        data_dir: 数据目录
        config_path: 配置文件路径
        tickers: 股票代码列表，如果为None则使用所有股票
        selector_configs: 自定义选股策略配置
        use_cache: 是否使用缓存结果
        save_result: 是否保存结果到文件
        storage: 结果存储管理器，如果为None则使用全局实例
    
    Returns:
        选股结果列表
    """
    # 加载数据
    if not data_dir.exists():
        raise HTTPException(status_code=404, detail=f"数据目录 {data_dir} 不存在")
    
    codes = (
        [f.stem for f in data_dir.glob("*.csv")]
        if tickers is None
        else tickers
    )
    
    if not codes:
        raise HTTPException(status_code=400, detail="股票池为空")
    
    data = load_data(data_dir, codes)
    if not data:
        raise HTTPException(status_code=404, detail="未能加载任何行情数据")
    
    # 确定交易日
    if trade_date is None:
        trade_date = max(df["date"].max() for df in data.values())
        logger.info("未指定日期，使用最近日期 %s", trade_date.date())
    else:
        trade_date = pd.to_datetime(trade_date)
    
    trade_date_str = trade_date.strftime("%Y-%m-%d")
    
    # 使用指定的存储管理器或全局实例
    if storage is None:
        storage = result_storage
    
    # 加载或使用自定义配置
    if selector_configs is not None:
        cfgs = selector_configs
    else:
        cfgs = load_config(config_path)
    
    # 执行选股
    results = []
    for cfg in cfgs:
        if cfg.get("activate", True) is False:
            continue
        
        try:
            alias, selector = instantiate_selector(cfg)
        except Exception as e:
            logger.error("跳过配置 %s：%s", cfg, e)
            continue
        
        selector_name = cfg.get("class", "Unknown")
        
        # 检查缓存
        if use_cache:
            cached_result = storage.load_result(trade_date_str, selector_name)
            if cached_result is not None:
                logger.info("使用缓存结果: %s (%s)", alias, trade_date_str)
                # 转换为API响应格式
                result = StockSelectionResult(
                    selector_name=cached_result.selector_name,
                    alias=cached_result.alias,
                    trade_date=cached_result.trade_date,
                    selected_stocks=cached_result.selected_stocks,
                    scores=cached_result.scores,
                    count=cached_result.count,
                )
                results.append(result)
                continue
        
        # 执行选股
        try:
            picks = selector.select(trade_date, data)
            
            # 获取评分（如果有）
            scores = None
            if hasattr(selector, "last_scores") and isinstance(getattr(selector, "last_scores"), dict):
                scores = getattr(selector, "last_scores")
            
            result = StockSelectionResult(
                selector_name=selector_name,
                alias=alias,
                trade_date=trade_date_str,
                selected_stocks=picks,
                scores=scores,
                count=len(picks),
            )
            results.append(result)
            
            # 保存结果
            if save_result:
                storage_result = StorageResult(
                    selector_name=result.selector_name,
                    alias=result.alias,
                    trade_date=result.trade_date,
                    selected_stocks=result.selected_stocks,
                    scores=result.scores,
                    count=result.count,
                )
                storage.save_result(storage_result)
            
        except Exception as e:
            logger.error("执行选股策略 %s 时出错：%s", alias, e)
            continue
    
    return results


# ========== API 端点 ==========

@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "name": "选股服务 API",
        "version": "1.0.0",
        "description": "提供Z哥战法选股功能的RESTful API接口",
        "endpoints": {
            "GET /": "API信息",
            "GET /health": "健康检查",
            "GET /selectors": "获取所有可用的选股策略",
            "POST /select": "执行选股",
            "GET /select": "执行选股（GET方式，使用查询参数）",
        }
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "data_dir_exists": DEFAULT_DATA_DIR.exists(),
        "config_exists": DEFAULT_CONFIG_PATH.exists(),
    }


@app.get("/selectors", response_model=List[SelectorInfo])
async def get_selectors(
    config_path: Optional[str] = Query(None, description="配置文件路径")
):
    """获取所有可用的选股策略"""
    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    
    if not cfg_path.exists():
        raise HTTPException(status_code=404, detail=f"配置文件 {cfg_path} 不存在")
    
    try:
        cfgs = load_config(cfg_path)
        selectors = []
        for cfg in cfgs:
            selectors.append(SelectorInfo(
                class_name=cfg.get("class", "Unknown"),
                alias=cfg.get("alias", cfg.get("class", "Unknown")),
                description=f"策略: {cfg.get('alias', cfg.get('class', 'Unknown'))}"
            ))
        return selectors
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载配置失败: {str(e)}")


@app.post("/select", response_model=StockSelectionResponse)
async def select_stocks_post(request: StockSelectionRequest):
    """执行选股（POST方式）"""
    try:
        data_dir = Path(request.data_dir) if request.data_dir else DEFAULT_DATA_DIR
        config_path = Path(request.config_path) if request.config_path else DEFAULT_CONFIG_PATH
        
        # 转换自定义配置
        selector_configs = None
        if request.selector_configs:
            selector_configs = [
                {
                    "class": cfg.class_name,
                    "alias": cfg.alias or cfg.class_name,
                    "activate": cfg.activate,
                    "params": cfg.params,
                }
                for cfg in request.selector_configs
            ]
        
        results = run_selection(
            trade_date=pd.to_datetime(request.date) if request.date else None,
            data_dir=data_dir,
            config_path=config_path,
            tickers=request.tickers,
            selector_configs=selector_configs,
            use_cache=request.use_cache,
            save_result=request.save_result,
        )
        
        if not results:
            return StockSelectionResponse(
                success=True,
                trade_date=results[0].trade_date if results else datetime.now().strftime("%Y-%m-%d"),
                results=[],
                message="没有激活的选股策略或所有策略都执行失败"
            )
        
        return StockSelectionResponse(
            success=True,
            trade_date=results[0].trade_date,
            results=results,
            message=f"成功执行 {len(results)} 个选股策略"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("选股执行失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"选股执行失败: {str(e)}")


@app.get("/select", response_model=StockSelectionResponse)
async def select_stocks_get(
    date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD"),
    data_dir: Optional[str] = Query(None, description="数据目录路径"),
    config_path: Optional[str] = Query(None, description="配置文件路径"),
    tickers: Optional[str] = Query(None, description="股票代码列表，逗号分隔"),
    use_cache: bool = Query(True, description="是否使用缓存结果"),
    save_result: bool = Query(True, description="是否保存选股结果"),
):
    """执行选股（GET方式，使用查询参数）"""
    try:
        data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        
        ticker_list = None
        if tickers:
            ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
        
        results = run_selection(
            trade_date=pd.to_datetime(date) if date else None,
            data_dir=data_dir,
            config_path=config_path,
            tickers=ticker_list,
            selector_configs=None,
            use_cache=use_cache,
            save_result=save_result,
        )
        
        if not results:
            return StockSelectionResponse(
                success=True,
                trade_date=results[0].trade_date if results else datetime.now().strftime("%Y-%m-%d"),
                results=[],
                message="没有激活的选股策略或所有策略都执行失败"
            )
        
        return StockSelectionResponse(
            success=True,
            trade_date=results[0].trade_date,
            results=results,
            message=f"成功执行 {len(results)} 个选股策略"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("选股执行失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"选股执行失败: {str(e)}")


@app.get("/results/dates")
async def get_result_dates():
    """获取所有有结果的日期列表"""
    try:
        dates = result_storage.list_available_dates()
        return {
            "success": True,
            "dates": dates,
            "count": len(dates)
        }
    except Exception as e:
        logger.error("获取日期列表失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取日期列表失败: {str(e)}")


@app.get("/results/{date}", response_model=StockSelectionResponse)
async def get_results_by_date(date: str):
    """获取指定日期的所有选股结果"""
    try:
        results_dict = result_storage.load_all_results(date)
        
        if not results_dict:
            return StockSelectionResponse(
                success=True,
                trade_date=date,
                results=[],
                message=f"日期 {date} 没有找到选股结果"
            )
        
        # 转换为API响应格式
        results = [
            StockSelectionResult(
                selector_name=r.selector_name,
                alias=r.alias,
                trade_date=r.trade_date,
                selected_stocks=r.selected_stocks,
                scores=r.scores,
                count=r.count,
            )
            for r in results_dict.values()
        ]
        
        return StockSelectionResponse(
            success=True,
            trade_date=date,
            results=results,
            message=f"找到 {len(results)} 个策略的结果"
        )
    except Exception as e:
        logger.error("获取选股结果失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取选股结果失败: {str(e)}")


@app.get("/results/{date}/{selector}", response_model=StockSelectionResult)
async def get_result_by_date_and_selector(date: str, selector: str):
    """获取指定日期和策略的选股结果"""
    try:
        result = result_storage.load_result(date, selector)
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"未找到日期 {date} 策略 {selector} 的选股结果"
            )
        
        # 转换为API响应格式
        return StockSelectionResult(
            selector_name=result.selector_name,
            alias=result.alias,
            trade_date=result.trade_date,
            selected_stocks=result.selected_stocks,
            scores=result.scores,
            count=result.count,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取选股结果失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取选股结果失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


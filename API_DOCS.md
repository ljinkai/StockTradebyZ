# 选股服务 API 文档

## 概述

选股服务 API 提供了基于 FastAPI 的 RESTful 接口，用于执行 Z哥战法的选股功能。通过 HTTP 请求，您可以方便地调用选股策略，获取选股结果。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
# 方式1：直接运行
python api_server.py

# 方式2：使用 uvicorn 命令
uvicorn api_server:app --host 0.0.0.0 --port 8000

# 方式3：后台运行（生产环境推荐）
uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 4
```

服务启动后，默认运行在 `http://localhost:8000`

### 3. 访问 API 文档

启动服务后，可以通过以下地址访问自动生成的 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 结果存储功能

选股结果会自动保存到 `./result` 目录，按日期和策略类型组织：

```
result/
  ├── 2025-01-15/
  │   ├── BBIKDJSelector.json
  │   ├── SuperB1Selector.json
  │   └── ...
  ├── 2025-01-16/
  │   └── ...
```

**优势：**
- 避免重复执行选股，提高效率
- 支持查询历史选股结果
- 结果以 JSON 格式保存，便于后续分析

**缓存机制：**
- 默认启用缓存（`use_cache=true`）
- 如果某天的某个策略已经执行过，直接返回缓存结果
- 可通过 `use_cache=false` 强制重新执行

## API 端点

### 1. 根路径 - 获取 API 信息

**GET** `/`

返回 API 的基本信息和可用端点列表。

**示例请求：**
```bash
curl http://localhost:8000/
```

**响应示例：**
```json
{
  "name": "选股服务 API",
  "version": "1.0.0",
  "description": "提供Z哥战法选股功能的RESTful API接口",
  "endpoints": {
    "GET /": "API信息",
    "GET /health": "健康检查",
    "GET /selectors": "获取所有可用的选股策略",
    "POST /select": "执行选股",
    "GET /select": "执行选股（GET方式，使用查询参数）",
    "GET /results/dates": "获取所有有结果的日期",
    "GET /results/{date}": "获取指定日期的所有选股结果",
    "GET /results/{date}/{selector}": "获取指定日期和策略的选股结果"
  }
}
```

### 2. 健康检查

**GET** `/health`

检查服务状态和数据文件是否存在。

**示例请求：**
```bash
curl http://localhost:8000/health
```

**响应示例：**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00",
  "data_dir_exists": true,
  "config_exists": true
}
```

### 3. 获取所有选股策略

**GET** `/selectors`

获取配置文件中定义的所有选股策略信息。

**查询参数：**
- `config_path` (可选): 配置文件路径，默认使用 `./configs.json`

**示例请求：**
```bash
curl http://localhost:8000/selectors
```

**响应示例：**
```json
[
  {
    "class_name": "BBIKDJSelector",
    "alias": "少妇战法",
    "description": "策略: 少妇战法"
  },
  {
    "class_name": "SuperB1Selector",
    "alias": "SuperB1战法",
    "description": "策略: SuperB1战法"
  }
]
```

### 4. 执行选股（POST 方式）

**POST** `/select`

通过 POST 请求执行选股，支持自定义配置。

**请求体：**
```json
{
  "date": "2025-01-15",           // 可选，交易日 YYYY-MM-DD，默认使用最新日期
  "data_dir": "./data",           // 可选，数据目录路径，默认 ./data
  "config_path": "./configs.json", // 可选，配置文件路径，默认 ./configs.json
  "tickers": ["000001", "000002"], // 可选，股票代码列表，默认使用所有股票
  "selector_configs": [           // 可选，自定义选股策略配置
    {
      "class_name": "BBIKDJSelector",
      "alias": "少妇战法",
      "activate": true,
      "params": {
        "j_threshold": 15,
        "max_window": 120
      }
    }
  ]
}
```

**示例请求：**
```bash
curl -X POST http://localhost:8000/select \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-01-15",
    "tickers": ["000001", "000002"]
  }'
```

**响应示例：**
```json
{
  "success": true,
  "trade_date": "2025-01-15",
  "message": "成功执行 1 个选股策略",
  "results": [
    {
      "selector_name": "BBIKDJSelector",
      "alias": "少妇战法",
      "trade_date": "2025-01-15",
      "selected_stocks": ["000001"],
      "scores": {
        "000001": 0.85
      },
      "count": 1
    }
  ]
}
```

### 5. 执行选股（GET 方式）

**GET** `/select`

通过 GET 请求执行选股，使用查询参数。

**查询参数：**
- `date` (可选): 交易日 YYYY-MM-DD，默认使用最新日期
- `data_dir` (可选): 数据目录路径，默认 `./data`
- `config_path` (可选): 配置文件路径，默认 `./configs.json`
- `tickers` (可选): 股票代码列表，逗号分隔，默认使用所有股票
- `use_cache` (可选): 是否使用缓存结果，默认 `true`
- `save_result` (可选): 是否保存选股结果，默认 `true`

**示例请求：**
```bash
# 使用默认配置执行选股
curl "http://localhost:8000/select"

# 指定日期和股票代码
curl "http://localhost:8000/select?date=2025-01-15&tickers=000001,000002"

# 指定自定义配置文件
curl "http://localhost:8000/select?config_path=./custom_configs.json"
```

**响应格式：** 与 POST 方式相同

### 6. 获取所有有结果的日期

**GET** `/results/dates`

获取所有已保存选股结果的日期列表。

**示例请求：**
```bash
curl http://localhost:8000/results/dates
```

**响应示例：**
```json
{
  "success": true,
  "dates": ["2025-01-15", "2025-01-14", "2025-01-13"],
  "count": 3
}
```

### 7. 获取指定日期的所有选股结果

**GET** `/results/{date}`

获取指定日期的所有策略的选股结果。

**路径参数：**
- `date`: 交易日，格式 YYYY-MM-DD

**示例请求：**
```bash
curl http://localhost:8000/results/2025-01-15
```

**响应格式：** 与 `/select` 端点相同

### 8. 获取指定日期和策略的选股结果

**GET** `/results/{date}/{selector}`

获取指定日期和策略的选股结果。

**路径参数：**
- `date`: 交易日，格式 YYYY-MM-DD
- `selector`: 策略类名，如 `BBIKDJSelector`

**示例请求：**
```bash
curl http://localhost:8000/results/2025-01-15/BBIKDJSelector
```

**响应示例：**
```json
{
  "selector_name": "BBIKDJSelector",
  "alias": "少妇战法",
  "trade_date": "2025-01-15",
  "selected_stocks": ["000001", "000002"],
  "scores": {
    "000001": 0.85,
    "000002": 0.78
  },
  "count": 2
}
```

## 使用示例

### Python 示例

```python
import requests

# 基础选股请求
response = requests.post("http://localhost:8000/select", json={
    "date": "2025-01-15"
})

result = response.json()
print(f"交易日: {result['trade_date']}")
for r in result['results']:
    print(f"{r['alias']}: {r['selected_stocks']}")

# 自定义策略配置
response = requests.post("http://localhost:8000/select", json={
    "date": "2025-01-15",
    "selector_configs": [
        {
            "class_name": "BBIKDJSelector",
            "alias": "少妇战法",
            "activate": True,
            "params": {
                "j_threshold": 15,
                "max_window": 120,
                "price_range_pct": 1
            }
        }
    ]
})
```

### JavaScript/Node.js 示例

```javascript
const axios = require('axios');

// 执行选股
async function selectStocks() {
  try {
    const response = await axios.post('http://localhost:8000/select', {
      date: '2025-01-15',
      tickers: ['000001', '000002']
    });
    
    console.log('选股结果:', response.data);
    response.data.results.forEach(result => {
      console.log(`${result.alias}: ${result.selected_stocks.join(', ')}`);
    });
  } catch (error) {
    console.error('选股失败:', error.response?.data || error.message);
  }
}

selectStocks();
```

### cURL 示例

```bash
# 获取所有策略
curl http://localhost:8000/selectors

# 执行选股（使用最新日期）
curl http://localhost:8000/select

# 执行选股（指定日期）
curl "http://localhost:8000/select?date=2025-01-15"

# 执行选股（指定股票代码）
curl "http://localhost:8000/select?tickers=000001,000002,000003"

# 强制重新执行（不使用缓存）
curl "http://localhost:8000/select?date=2025-01-15&use_cache=false"

# 执行但不保存结果
curl "http://localhost:8000/select?date=2025-01-15&save_result=false"

# 查询历史结果
curl http://localhost:8000/results/dates
curl http://localhost:8000/results/2025-01-15
curl http://localhost:8000/results/2025-01-15/BBIKDJSelector

# POST 方式执行选股（自定义配置）
curl -X POST http://localhost:8000/select \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-01-15",
    "selector_configs": [
      {
        "class_name": "BBIKDJSelector",
        "activate": true,
        "params": {"j_threshold": 15}
      }
    ]
  }'
```

## 错误处理

API 使用标准的 HTTP 状态码：

- `200 OK`: 请求成功
- `400 Bad Request`: 请求参数错误（如股票池为空）
- `404 Not Found`: 资源不存在（如数据目录或配置文件不存在）
- `500 Internal Server Error`: 服务器内部错误

**错误响应格式：**
```json
{
  "detail": "错误描述信息"
}
```

## 注意事项

1. **数据准备**：确保 `./data` 目录中有股票数据的 CSV 文件
2. **配置文件**：确保 `./configs.json` 文件存在且格式正确
3. **日期格式**：日期必须使用 `YYYY-MM-DD` 格式
4. **股票代码**：股票代码格式应与数据文件名称一致（不含 `.csv` 扩展名）
5. **性能考虑**：选股操作可能需要一些时间，建议设置合适的请求超时时间
6. **结果存储**：选股结果自动保存到 `./result` 目录，按日期和策略组织
7. **缓存机制**：默认启用缓存，相同日期和策略的请求会直接返回缓存结果，提高效率

## 生产环境部署

### 使用 Gunicorn + Uvicorn Workers

```bash
pip install gunicorn
gunicorn api_server:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 使用 Docker

创建 `Dockerfile`：

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

构建和运行：

```bash
docker build -t stock-selector-api .
docker run -p 8000:8000 -v $(pwd)/data:/app/data stock-selector-api
```

### 使用 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 常见问题

**Q: 如何查看 API 文档？**  
A: 启动服务后访问 http://localhost:8000/docs

**Q: 如何指定特定的选股策略？**  
A: 可以通过 POST 请求的 `selector_configs` 参数自定义配置，或者修改 `configs.json` 文件中的 `activate` 字段

**Q: 如何只对特定股票执行选股？**  
A: 在请求中指定 `tickers` 参数，提供股票代码列表

**Q: 服务支持并发请求吗？**  
A: 支持，但建议在生产环境中使用多个 worker 进程以提高并发性能

## 更新日志

- **v1.0.0** (2025-01-15): 初始版本，提供基础的选股 API 功能


# blue-agentgame-2026

租房 AI Agent：基于自然语言与仿真服务 API 完成房源查询、筛选、租赁等操作。

## 环境

- Python 3.8+
- `pip install -r requirements.txt`

## 配置（环境变量）

- `SIMULATION_HOST`：租房仿真服务 IP（默认 127.0.0.1）
- `SIMULATION_PORT`：端口（默认 8080）
- `USER_ID`：用户工号（X-User-ID，比赛平台注册）
- `LLM_API_BASE`：可选，LLM 接口地址（OpenAI 兼容）；不设则使用内置 mock 意图/回复

## 使用

单轮调用：

```bash
python -m agent.main <session_id> "<user_input>"
```

返回 JSON：`{"session_id": "...", "message": "...", "houses": ["HF_xxx", ...]}`

判题器对接时，每轮请求调用 `agent.main.handle(session_id, user_input)` 即可。

## HTTP 服务

启动本地 HTTP 服务（默认端口 8000，可通过环境变量 `PORT` 修改）：

```bash
python -m agent.server
```

- **GET /** 或 **GET /health**：健康检查，返回 `{"status":"ok","service":"rental-agent"}`
- **POST /**：请求体 JSON `{"session_id": "...", "user_input": "..."}`，返回 `{"session_id", "message", "houses"}`

示例：

```bash
curl -X POST http://127.0.0.1:8000/ -H "Content-Type: application/json" -d "{\"session_id\":\"EV-45\",\"user_input\":\"海淀区离地铁近的两居有吗？\"}"
```

## 测试

- 单元 + 开放用例（Mock API，无需仿真服务）：
  ```bash
  pytest tests/ -v
  ```
- 开放用例（需仿真服务）：
  ```bash
  python tests/run_open_cases.py
  ```

## 结构

- `agent/main.py`：入口与主流程
- `agent/server.py`：HTTP 服务（POST / 调用 agent）
- `agent/session_manager.py`：Session 与 init
- `agent/intent_parser.py`：意图与槽位解析
- `agent/api_planner.py`：API 编排与指代消解
- `agent/api_client.py`：仿真服务 HTTP 客户端
- `agent/api_executor.py`：执行 API 调用链
- `agent/post_processor.py`：过滤、排序、截断
- `agent/response_generator.py`：自然语言回复生成
- `agent/llm_client.py`：LLM 调用（可接判题器接口）
- `agent/config.py`、`agent/models.py`：配置与数据模型

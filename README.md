# blue-agentgame-2026

租房 AI Agent：基于自然语言与仿真服务 API 完成房源查询、筛选、租赁等操作。

## 环境

- Python 3.8+
- `pip install -r requirements.txt`

## 配置

所有配置统一放在项目根目录的 **`config.json`** 中，环境变量可覆盖同名项。

| 字段 | 说明 | 默认 |
|------|------|------|
| `simulation_host` | 租房仿真服务 IP | 127.0.0.1 |
| `simulation_port` | 仿真服务端口 | 8080 |
| `user_id` | 用户工号（X-User-ID，比赛平台注册） | test_user |
| `api_timeout` | 单次 API 超时（秒） | 5 |
| `max_houses` | 最多返回房源数 | 5 |
| `max_history_turns` | 对话历史保留轮数 | 6 |
| `llm_api_base` | LLM 接口地址（OpenAI 兼容）；空则用内置 mock | "" |
| `llm_api_key` | LLM 鉴权 Key（可选） | "" |
| `llm_model` | 模型名 | qwen3-32b |
| `server_port` | HTTP 服务端口 | 8000 |

环境变量覆盖（与上表对应）：`SIMULATION_HOST`、`SIMULATION_PORT`、`USER_ID`、`LLM_API_BASE`、`LLM_API_KEY`、`LLM_MODEL`、`PORT`。

## 使用

单轮调用：

```bash
python -m agent.main <session_id> "<user_input>"
```

返回 JSON：`{"session_id": "...", "message": "...", "houses": ["HF_xxx", ...]}`

判题器对接时，每轮请求调用 `agent.main.handle(session_id, user_input)` 即可。

## HTTP 服务

启动本地 HTTP 服务（端口见 `config.json` 的 `server_port`，默认 8000）：

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
- 项目根目录 **`config.json`**：统一配置文件（仿真服务、LLM、HTTP 端口等）

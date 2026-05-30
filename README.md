# 小溯医生（本地RAG版）提交说明

本项目为基于 Streamlit 的可溯源临床辅助系统，支持：
- 本地RAG检索（默认）
- RAGFlow 接口模式（可选）
- 三层证据展示（指南级/文献级/病例级）

## 1. 运行环境

- Windows 10/11
- Python 3.9 及以上（建议 3.10/3.11）
- 可联网安装依赖

## 2. 提交包目录建议

请将以下内容放在同一个 ZIP 包中：

- `c4/`（本项目源码目录）
- `核心三库/`（三份知识库 txt）

建议目录结构：

```text
作品安装包/
  c4/
    web.py
    chat_page.py
    local_rag_client.py
    requirements.txt
    run.bat
    ...
  核心三库/
    临床指南.txt
    医学文献.txt
    脱敏病例.txt
```

## 3. 安装依赖

在 `c4` 目录下打开终端，执行：

```bash
pip install -r requirements.txt
```

## 4. 启动方式

方式 A（命令行）：

```bash
streamlit run web.py
```

方式 B（双击脚本）：

- 双击 `run.bat`

同一校园网访问：

- 双击 `启动局域网服务.bat`
- 在本机运行 `ipconfig` 查看 IPv4 地址
- 其他同校园网设备访问：
  - 前端：`http://你的IPv4地址:8501`
  - 后端：`http://你的IPv4地址:8000`
- 若无法访问，通常是 Windows 防火墙拦截 Python 或端口 `8000/8501`，需要允许入站连接。

后端接口（可选，用于单独调试/对接前端）：

```bash
python -m uvicorn backend:app --host 127.0.0.1 --port 8000
```

- 健康检查：`GET http://127.0.0.1:8000/health`
- 本地 RAG 分析：`POST http://127.0.0.1:8000/api/analyze`
- 知识库统计：`GET http://127.0.0.1:8000/api/knowledge/stats`
- 数据集统计：`GET http://127.0.0.1:8000/api/dataset/stats`
- 证据检索：`GET http://127.0.0.1:8000/api/search?q=咳嗽发热&top_k=5`
- 知识库预览：`GET http://127.0.0.1:8000/api/knowledge/preview`
- 症状路由配置：`GET http://127.0.0.1:8000/api/routes`
- 少样本/未标注样例：`GET http://127.0.0.1:8000/api/examples`
- 生成伪标签：`POST http://127.0.0.1:8000/api/pseudo-labels/generate`
- 重建扩展数据：`POST http://127.0.0.1:8000/api/admin/rebuild-demo-data`
- 备份数据库：`POST http://127.0.0.1:8000/api/admin/backup`
- 导出后端数据：`GET http://127.0.0.1:8000/api/export/all`
- 后端自检：`GET http://127.0.0.1:8000/api/self-test`
- 患者记录：`GET/POST http://127.0.0.1:8000/api/patients`
- 推理历史：`GET http://127.0.0.1:8000/api/inferences`
- 也可以双击 `启动后端.bat`

`/api/analyze` 最小请求示例：

```json
{
  "complaint": "咳嗽发热三天",
  "history": "咳黄痰，低热，活动后有点气短",
  "question": "可能是什么病，下一步怎么办"
}
```

后端默认走本地 RAG：先检索 `核心三库`，再尝试调用 OpenAI 兼容 LLM；如果本机未启动 Ollama/RAGFlow，也会基于检索证据和症状路由返回结构化兜底结果。

## 9. 当前后端与数据资产

- `backend.py`：HTTP API 服务，覆盖健康检查、分析、检索、数据统计、伪标签生成、患者记录、推理历史。
- `storage.py`：SQLite 持久化层，数据库文件自动生成到 `data/tracedoc_backend.sqlite3`。
- `tools/build_demo_knowledge_base.py`：根据 `data/symptom_routes.json` 扩展生成演示知识库和样本集。
- `tests/backend_smoke_test.py`：后端冒烟测试，覆盖健康检查、自检、统计、检索、分析、历史和备份。
- `核心三库/扩展临床指南库.txt`、`扩展医学文献摘要库.txt`、`扩展脱敏病例库.txt`：扩展后的本地 RAG 知识库。
- `data/dataset_samples.jsonl`：脱敏演示样本集。
- `data/pseudo_labeled_pairs.jsonl`：伪标签检索训练对，可用于后续对比学习脚本。

重新生成扩展数据：

```bash
python tools/build_demo_knowledge_base.py
python research/pseudo_label_generator.py
```

后端接口自检：

```bash
python tests/backend_smoke_test.py
```

说明：当前扩展数据用于工程演示和检索测试，不等同于真实临床指南或真实院内数据库；正式参赛/部署时应替换为公开数据集或合规脱敏数据。

## 5. 默认配置（本地RAG）

- 侧栏默认后端：`本地RAG（无RAGFlow）`
- 默认知识库目录：`e:\dinghuiyu\yuandaima\核心三库`

> 若评审机目录不同，请在左侧“知识库目录”手动修改为实际路径。

## 6. 登录说明

- 默认账号：`admin`
- 默认密码：`123456`

也可在注册页创建新账号后登录（账号信息在本次运行会话中有效）。

## 7. 可选：RAGFlow 模式

若要使用 RAGFlow，请在侧栏切换后端为 `RAGFlow`，并填写：
- Base URL
- Chat ID
- API Key

详见：`RAGFLOW_SETUP.txt`

## 8. 提交前清理建议

建议删除以下运行缓存后再打包：

- `__pycache__/`
- `*.pyc`
- `data/audit_log.jsonl`（若不需要提交运行日志）
- `核心三库/.local_rag_index.pkl`（索引缓存可自动重建）

同时请确认不包含任何真实密钥（API Key）。

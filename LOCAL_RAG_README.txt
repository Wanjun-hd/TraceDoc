本地RAG（不使用RAGFlow）快速说明
=================================

1) Streamlit 侧栏选择「本地RAG（无RAGFlow）」。

2) 知识库目录（local_kb_dir）
   - 当前项目默认目录：e:\dinghuiyu\yuandaima\核心三库
   - 放入你的指南/文献/病例文件，支持：
     txt / md / csv / json / pdf
   - 建议命名中包含关键词，便于自动分层：
     [指南]xxx.pdf、[文献]xxx.pdf、[病例]xxx.pdf

3) 本地模型接口（OpenAI兼容）
   - 默认示例：http://localhost:11434/v1 （Ollama）
   - 模型名示例：qwen2.5:7b
   - API Key：Ollama可留空；其他服务按实际填写。

4) 运行方式
   - 保持 streamlit run web.py 运行
   - 侧栏填好本地参数后，点击「开始分析」

5) 说明
   - 该方案是“简化版本地RAG”：
     本地文件切分 + 关键词相似度检索 + LLM结构化生成
   - 若本地模型未返回JSON，系统会自动给出检索兜底结果，页面不会空白。

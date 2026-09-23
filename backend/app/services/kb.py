"""知识库服务（里程碑 4）：文档解析 -> 分块 -> API 嵌入 -> ChromaDB 检索。

设计要点：
- 嵌入走智谱 embedding-3（OpenAI 兼容 /embeddings，复用 GLM_API_KEY），不再本地加载模型
  —— 免去 torch/sentence-transformers 依赖与 ~2GB 内存，Render 免费层 512MB 稳定运行
- 分批请求（智谱单请求上限 64 条）+ L2 归一化，返回顺序与输入一致
- ChromaDB 持久化在 backend/data/chroma，collection 按余弦距离建索引，
  名称带嵌入模型标识：换嵌入模型即换集合，新旧维度自动隔离不冲突
- 引用溯源：每个向量块带 doc_id 元数据，检索命中即可回溯到文档名与原文片段
"""
from ..config import get_settings
from ..models import KnowledgeDoc

# 解析后拼接段落时的分隔符
_PARA_SEP = "\n"

# 惰性单例的嵌入客户端（进程内复用 HTTP 连接池，避免并发重复创建）
_client = None


def _get_client():
    """懒加载智谱嵌入客户端（OpenAI 兼容协议）。"""
    global _client
    if _client is None:
        from openai import OpenAI

        s = get_settings()
        if not s.GLM_API_KEY:
            raise RuntimeError("未配置智谱 API Key（GLM_API_KEY），知识库嵌入不可用")
        _client = OpenAI(api_key=s.GLM_API_KEY, base_url=s.GLM_BASE_URL)
    return _client


def _get_collection():
    """获取 ChromaDB 集合（余弦距离，持久化）；名称带嵌入模型标识。"""
    import re

    import chromadb

    s = get_settings()
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", s.KB_EMBED_MODEL).strip("-") or "default"
    client = chromadb.PersistentClient(path=s.CHROMA_DIR)
    return client.get_or_create_collection(
        name=f"zhixue_kb_{safe}",
        metadata={"hnsw:space": "cosine"},
    )


# ---------- 文档解析 ----------

def _parse_pdf(raw: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(raw))
    return _PARA_SEP.join(page.extract_text() or "" for page in reader.pages)


def _parse_docx(raw: bytes) -> str:
    from io import BytesIO

    import docx

    d = docx.Document(BytesIO(raw))
    return _PARA_SEP.join(p.text for p in d.paragraphs if p.text.strip())


def _parse_pptx(raw: bytes) -> str:
    from io import BytesIO

    from pptx import Presentation

    prs = Presentation(BytesIO(raw))
    parts = []
    for slide in prs.slides:
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                t = shape.text_frame.text.strip()
                if t:
                    texts.append(t)
        if texts:
            parts.append(_PARA_SEP.join(texts))
    return _PARA_SEP.join(parts)


def parse_file(filename: str, raw: bytes) -> str:
    """按扩展名解析文件为纯文本。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return _parse_pdf(raw)
    if ext == "docx":
        return _parse_docx(raw)
    if ext == "pptx":
        return _parse_pptx(raw)
    if ext in ("md", "txt"):
        return raw.decode("utf-8", errors="replace")
    raise ValueError(f"暂不支持 .{ext} 格式，请上传 PDF/DOCX/PPTX/MD/TXT")


# ---------- 分块 ----------

def split_chunks(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    """按段落聚合切块：目标 size 字符，相邻块 overlap 重叠，尽量在句子边界切。

    中文文档按字符数即可；优先按换行分段，超长段落再按句号/问号切。
    """
    s = get_settings()
    size = size or s.KB_CHUNK_SIZE
    overlap = overlap or s.KB_CHUNK_OVERLAP
    text = text.strip()
    if not text:
        return []

    # 段落优先，超长段落降级为句子，最后按字符硬切
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    units: list[str] = []  # 最小不可切分单元
    for p in paras:
        if len(p) <= size:
            units.append(p)
            continue
        import re

        sentences = re.split(r"(?<=[。！？!?；;\n])", p)
        buf = ""
        for sent in sentences:
            if not sent:
                continue
            if len(buf) + len(sent) <= size:
                buf += sent
            else:
                if buf:
                    units.append(buf)
                # 单句仍超长则按字符硬切
                while len(sent) > size:
                    units.append(sent[:size])
                    sent = sent[size - overlap:]
                buf = sent
        if buf:
            units.append(buf)

    # 相邻单元聚合到 size 大小
    chunks: list[str] = []
    buf = ""
    for u in units:
        if len(buf) + len(u) + 1 <= size or not buf:
            buf = f"{buf}{_PARA_SEP}{u}" if buf else u
        else:
            chunks.append(buf)
            # 保留 overlap 尾部，保证跨块语义连续
            tail = buf[-overlap:] if overlap > 0 else ""
            buf = f"{tail}{_PARA_SEP}{u}" if tail else u
    if buf:
        chunks.append(buf)
    return [c.strip() for c in chunks if c.strip()]


# ---------- 入库 / 检索 / 删除 ----------

def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量嵌入：调智谱 embedding API，分批请求，返回 L2 归一化向量列表。

    请求按 KB_EMBED_BATCH 分批；兼容实现可能乱序返回，按 index 回填保证顺序一致。
    L2 归一化与旧本地模型行为对齐，保证 KB_MIN_SCORE 余弦阈值语义不变。
    """
    if not texts:
        return []
    s = get_settings()
    client = _get_client()
    vecs: list[list[float]] = []
    for i in range(0, len(texts), s.KB_EMBED_BATCH):
        batch = texts[i : i + s.KB_EMBED_BATCH]
        kwargs = {"model": s.KB_EMBED_MODEL, "input": batch}
        if s.KB_EMBED_DIMENSIONS > 0:
            kwargs["dimensions"] = s.KB_EMBED_DIMENSIONS
        resp = client.embeddings.create(**kwargs)
        batch_vecs: list[list[float] | None] = [None] * len(batch)
        for item in resp.data:
            batch_vecs[item.index] = item.embedding
        if any(v is None for v in batch_vecs):
            raise RuntimeError("嵌入接口返回数据不完整")
        vecs.extend(batch_vecs)
    return [_l2_normalize(v) for v in vecs]


def _l2_normalize(vec: list[float]) -> list[float]:
    """L2 归一化（纯 Python，避免为此引入 numpy）。"""
    norm = sum(x * x for x in vec) ** 0.5
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def add_document(doc: KnowledgeDoc, text: str) -> int:
    """对文档分块并向量化入库，返回块数。向量 id 带 doc_id 便于整篇删除。"""
    chunks = split_chunks(text)
    if not chunks:
        return 0
    vecs = embed_texts(chunks)
    col = _get_collection()
    col.add(
        ids=[f"doc{doc.id}-c{i}" for i in range(len(chunks))],
        embeddings=vecs,
        documents=chunks,
        # 元数据带分类（里程碑 6）：供定向检索 where 过滤
        metadatas=[
            {"doc_id": doc.id, "filename": doc.filename, "category": doc.category or "general"}
        ] * len(chunks),
    )
    return len(chunks)


def delete_document(doc_id: int) -> None:
    """按 doc_id 删除该文档的全部向量。"""
    col = _get_collection()
    col.delete(where={"doc_id": doc_id})


def get_document_content(doc_id: int) -> str:
    """按 doc_id 取回全部向量块并按序拼接，还原文档全文（里程碑 7 引用溯源）。

    向量 id 形如 doc{id}-c{i}，按块序号 i 排序保证原文顺序正确。
    """
    col = _get_collection()
    if col.count() == 0:
        return ""
    res = col.get(where={"doc_id": doc_id}, include=["documents"])
    if not res or not res.get("ids"):
        return ""
    items: list[tuple[int, str]] = []
    for rid, text in zip(res["ids"], res["documents"]):
        try:
            items.append((int(str(rid).rsplit("-c", 1)[-1]), text))
        except ValueError:  # 非常规 id 跳过，不影响其余块
            continue
    items.sort(key=lambda x: x[0])
    return "\n".join(t for _, t in items)


def get_chunks(doc_id: int) -> list[dict]:
    """按 doc_id 取回全部分块（按块序），供前端「分块可视化」展示。

    返回 [{index, text, chars}]；与 get_document_content 同样解析 doc{id}-c{i} 向量 id。
    """
    col = _get_collection()
    if col.count() == 0:
        return []
    res = col.get(where={"doc_id": doc_id}, include=["documents"])
    if not res or not res.get("ids"):
        return []
    items: list[tuple[int, str]] = []
    for rid, text in zip(res["ids"], res["documents"]):
        try:
            items.append((int(str(rid).rsplit("-c", 1)[-1]), text))
        except ValueError:
            continue
    items.sort(key=lambda x: x[0])
    return [{"index": i, "text": t, "chars": len(t)} for i, t in items]


def search(
    query: str, k: int | None = None, category: str | None = None,
    doc_ids: list[int] | None = None,
) -> list[dict]:
    """语义检索：返回 [{doc_id, doc, snippet, score}]，score 为归一化余弦相似度。

    category（里程碑 6）：传入分类时用 ChromaDB where 过滤，实现定向检索。
    doc_ids（2026-09-20）：传入文档 id 列表时只在这些文档的块中检索（用户在
    对话页知识库菜单里勾选资料）；None/空列表表示不过滤（检索全部）。
    """
    s = get_settings()
    col = _get_collection()
    if col.count() == 0:
        return []
    k = min(k or s.KB_TOP_K, col.count())
    qv = embed_texts([query])[0]
    query_kwargs = {}
    conds = []
    if category:
        conds.append({"category": category})
    if doc_ids:  # 文档范围过滤：$in 匹配用户勾选的 doc_id
        conds.append({"doc_id": {"$in": list(doc_ids)}})
    if len(conds) == 1:  # 单条件直接 where
        query_kwargs["where"] = conds[0]
    elif conds:  # 多条件必须显式 $and（ChromaDB 不接受多 key 平铺 dict）
        query_kwargs["where"] = {"$and": conds}
    res = col.query(
        query_embeddings=[qv], n_results=k,
        include=["documents", "metadatas", "distances"], **query_kwargs,
    )
    hits = []
    for doc_text, meta, dist in zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        score = round(1.0 - float(dist), 4)  # 余弦距离 -> 相似度
        if score < s.KB_MIN_SCORE:
            continue
        hits.append({
            "doc_id": meta.get("doc_id"),
            "doc": meta.get("filename", ""),
            "snippet": doc_text[:200],
            "score": score,
        })
    return hits

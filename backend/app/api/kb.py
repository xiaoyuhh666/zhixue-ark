"""知识库接口：上传 / 列表 / 检索试验台 / 删除，向量与元数据联动，按用户隔离。"""
from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import KnowledgeDoc
from ..services import kb
from .auth import get_current_user

router = APIRouter(prefix="/api/kb", tags=["kb"])

# 允许的扩展名与大小上限（10MB，毕设演示场景足够）
ALLOWED_EXTS = {"pdf", "docx", "pptx", "md", "txt"}
MAX_SIZE = 10 * 1024 * 1024
# 文档分类白名单（里程碑 6：定向检索用）
ALLOWED_CATEGORIES = {"study", "competition", "research", "career", "life", "general"}


@router.post("/upload")
async def upload(
    file: UploadFile,
    category: str = Form("general"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传文档：保存元数据 -> 解析分块 -> 向量入库（同步完成，演示文档体量小）。

    category 为文档分类（里程碑 6）：智能体检索时可按分类定向过滤。
    """
    filename = file.filename or "unnamed"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"暂不支持 .{ext} 格式（PDF/DOCX/PPTX/MD/TXT）")
    category = category if category in ALLOWED_CATEGORIES else "general"

    raw = await file.read()
    if len(raw) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="文件超过 10MB 上限")

    # 先落一条元数据记录，解析失败也能在列表里看到原因
    doc = KnowledgeDoc(user_id=user.id, filename=filename, ext=ext, category=category, status="processing")
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        text = kb.parse_file(filename, raw)
        doc.chunk_count = kb.add_document(doc, text)
        if doc.chunk_count == 0:
            doc.status, doc.note = "failed", "未解析出有效文本"
        else:
            doc.status = "ready"
    except Exception as e:  # 解析/嵌入失败不影响服务，记录原因
        doc.status, doc.note = "failed", str(e)[:200]
    db.commit()
    db.refresh(doc)
    return _serialize(doc)


@router.get("/documents")
def list_documents(user=Depends(get_current_user), db: Session = Depends(get_db)):
    docs = (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.user_id == user.id)
        .order_by(KnowledgeDoc.id.desc())
        .limit(200)
        .all()
    )
    return [_serialize(d) for d in docs]


@router.get("/documents/{doc_id}/content")
def get_document_content(doc_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """文档全文（引用溯源）：向量块按序拼接还原原文，供前端弹层高亮。"""
    doc = (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.id == doc_id, KnowledgeDoc.user_id == user.id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {
        "id": doc.id,
        "filename": doc.filename,
        "category": doc.category,
        "content": kb.get_document_content(doc_id),
    }


@router.get("/search")
def search_knowledge(
    q: str = Query(..., min_length=1, max_length=100),
    k: int = Query(3, ge=1, le=5),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """检索试验台（只读）：输入问题实时返回 Top-K 命中片段与相似度。

    检索范围限定当前用户自己的文档（doc_ids 传 None 表示无文档）。
    """
    qs = q.strip()
    if not qs:
        return {"query": qs, "items": []}
    own_ids = [
        r[0] for r in db.query(KnowledgeDoc.id).filter_by(user_id=user.id).all()
    ]
    if not own_ids:  # 本人无任何文档：向量库命中也可能来自他人文档，直接短路
        return {"query": qs, "items": []}
    hits = kb.search(qs, k=k, doc_ids=own_ids)
    return {"query": qs, "items": hits}


@router.get("/documents/{doc_id}/chunks")
def get_document_chunks(doc_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """分块可视化：取回该文档全部分块（按块序），展示解析->分块->向量化产物。"""
    doc = (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.id == doc_id, KnowledgeDoc.user_id == user.id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {
        "id": doc.id,
        "filename": doc.filename,
        "category": doc.category,
        "chunks": kb.get_chunks(doc_id),
    }


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    doc = (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.id == doc_id, KnowledgeDoc.user_id == user.id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    kb.delete_document(doc_id)  # 同步清掉向量块表里的向量
    db.delete(doc)
    db.commit()
    return {"ok": True}


def _serialize(d: KnowledgeDoc) -> dict:
    return {
        "id": d.id,
        "filename": d.filename,
        "ext": d.ext,
        "category": d.category,
        "status": d.status,
        "chunk_count": d.chunk_count,
        "note": d.note,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }

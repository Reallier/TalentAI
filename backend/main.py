from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional
import tempfile
import os

from database import get_db, init_db
from schemas import (
    MatchRequest, MatchResponse, SearchRequest, SearchResponse,
    CandidateResponse, CandidateDetail, ReindexRequest, ReindexResponse,
    IngestResponse
)
from models import Candidate
from services.matching_service import MatchingService
from services.ingest_service import IngestService
from services.indexing_service import IndexingService
from config import settings

# 创建 FastAPI 应用
app = FastAPI(
    title="TalentAI - 智能招聘匹配系统",
    description="基于 RAG 的人才匹配与简历管理系统",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """启动事件"""
    await init_db()
    print("✓ 数据库初始化完成")


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "TalentAI API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


# ============= 匹配相关 API =============

@app.post("/api/match", response_model=MatchResponse)
async def match_candidates(
    request: MatchRequest,
    db: Session = Depends(get_db)
):
    """
    JD 匹配候选人
    
    根据职位描述匹配最合适的候选人，返回排序结果和证据
    """
    try:
        matching_service = MatchingService(db)
        
        result = matching_service.match_candidates(
            jd_text=request.jd,
            filters=request.filters.dict() if request.filters else None,
            top_k=request.top_k,
            explain=request.explain
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"匹配失败: {str(e)}")


@app.get("/api/search", response_model=SearchResponse)
async def search_candidates(
    q: str,
    top_k: int = 20,
    db: Session = Depends(get_db)
):
    """
    关键词搜索候选人
    
    使用关键词进行全文搜索
    """
    try:
        matching_service = MatchingService(db)
        
        results = matching_service.search_candidates(
            query=q,
            top_k=top_k
        )
        
        return {
            "results": results,
            "total": len(results),
            "query": q
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


# ============= 简历入库 API =============

@app.post("/api/candidates/ingest", response_model=IngestResponse)
async def ingest_resume(
    file: UploadFile = File(...),
    source: str = Form("upload"),
    db: Session = Depends(get_db)
):
    """
    上传并入库简历
    
    支持 PDF 和 DOCX 格式，自动解析、判重、合并
    """
    # 检查文件类型
    if not file.filename.lower().endswith(('.pdf', '.docx', '.doc')):
        raise HTTPException(
            status_code=400,
            detail="不支持的文件格式，仅支持 PDF 和 DOCX"
        )
    
    # 检查文件大小
    file_size = 0
    chunk_size = 1024 * 1024  # 1MB
    temp_file = None
    
    try:
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp:
            temp_file = temp.name
            while chunk := await file.read(chunk_size):
                file_size += len(chunk)
                if file_size > settings.max_file_size_mb * 1024 * 1024:
                    raise HTTPException(
                        status_code=400,
                        detail=f"文件大小超过限制 ({settings.max_file_size_mb}MB)"
                    )
                temp.write(chunk)
        
        # 入库处理
        ingest_service = IngestService(db)
        result = ingest_service.ingest_resume(
            file_path=temp_file,
            source=source
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"入库失败: {str(e)}")
    
    finally:
        # 清理临时文件
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)


# ============= 候选人管理 API =============

@app.get("/api/candidates/{candidate_id}", response_model=CandidateDetail)
async def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db)
):
    """
    获取候选人详细信息
    
    包含基本信息、工作经历、项目经历、教育背景等
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")
    
    # 构建详细响应
    from schemas import (
        ResumeResponse, ExperienceResponse, 
        ProjectResponse, EducationResponse
    )
    
    detail = {
        "id": candidate.id,
        "name": candidate.name,
        "email": candidate.email,
        "phone": candidate.phone,
        "location": candidate.location,
        "years_experience": candidate.years_experience,
        "current_title": candidate.current_title,
        "current_company": candidate.current_company,
        "skills": candidate.skills or [],
        "education_level": candidate.education_level,
        "source": candidate.source,
        "status": candidate.status,
        "created_at": candidate.created_at,
        "updated_at": candidate.updated_at,
        "resumes": [
            ResumeResponse(
                id=r.id,
                candidate_id=r.candidate_id,
                file_uri=r.file_uri,
                file_type=r.file_type,
                text_hash=r.text_hash,
                created_at=r.created_at
            ) for r in candidate.resumes
        ],
        "experiences": [
            ExperienceResponse(
                id=e.id,
                candidate_id=e.candidate_id,
                company=e.company,
                title=e.title,
                start_date=e.start_date,
                end_date=e.end_date,
                skills=e.skills or [],
                description=e.description,
                created_at=e.created_at
            ) for e in candidate.experiences
        ],
        "projects": [
            ProjectResponse(
                id=p.id,
                candidate_id=p.candidate_id,
                project_name=p.project_name,
                role=p.role,
                start_date=p.start_date,
                end_date=p.end_date,
                skills=p.skills or [],
                description=p.description
            ) for p in candidate.projects
        ],
        "education": [
            EducationResponse(
                id=e.id,
                candidate_id=e.candidate_id,
                school=e.school,
                degree=e.degree,
                major=e.major,
                start_date=e.start_date,
                end_date=e.end_date
            ) for e in candidate.education
        ]
    }
    
    # 添加索引信息
    if candidate.index:
        detail["index_updated_at"] = candidate.index.index_updated_at
        detail["embedding_version"] = candidate.index.embedding_version
    
    return detail


@app.get("/api/candidates", response_model=list)
async def list_candidates(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    列出候选人
    
    支持分页和状态过滤
    """
    query = db.query(Candidate)
    
    if status:
        query = query.filter(Candidate.status == status)
    
    candidates = query.offset(skip).limit(limit).all()
    
    return [
        CandidateResponse(
            id=c.id,
            name=c.name,
            email=c.email,
            phone=c.phone,
            location=c.location,
            years_experience=c.years_experience,
            current_title=c.current_title,
            current_company=c.current_company,
            skills=c.skills or [],
            education_level=c.education_level,
            source=c.source,
            status=c.status,
            created_at=c.created_at,
            updated_at=c.updated_at
        )
        for c in candidates
    ]


# ============= 索引管理 API =============

@app.post("/api/reindex", response_model=ReindexResponse)
async def reindex_candidates(
    request: ReindexRequest,
    db: Session = Depends(get_db)
):
    """
    重建索引
    
    可以指定候选人ID列表或时间范围
    """
    try:
        indexing_service = IndexingService(db)
        
        result = indexing_service.reindex_all(
            candidate_ids=request.candidate_ids,
            updated_since=request.updated_since
        )
        
        return {
            "success": True,
            "reindexed_count": result['success'],
            "failed_count": result['failed'],
            "errors": []
        }
    
    except Exception as e:
        return {
            "success": False,
            "reindexed_count": 0,
            "failed_count": 0,
            "errors": [str(e)]
        }


@app.delete("/api/candidates/{candidate_id}")
async def delete_candidate(
    candidate_id: int,
    db: Session = Depends(get_db)
):
    """
    删除候选人
    
    会同时删除相关的简历、索引等数据，并记录审计日志
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")
    
    try:
        # 记录审计日志
        from models import AuditLog
        audit = AuditLog(
            entity_type='candidate',
            entity_id=candidate_id,
            action='delete',
            changes={'name': candidate.name},
            performed_by='api',
            performed_at=datetime.utcnow()
        )
        db.add(audit)
        
        # 删除候选人（级联删除相关数据）
        db.delete(candidate)
        db.commit()
        
        return {"success": True, "message": f"候选人 {candidate_id} 已删除"}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ============= 统计 API =============

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """获取系统统计信息"""
    from models import Resume, Experience
    from sqlalchemy import func
    
    total_candidates = db.query(func.count(Candidate.id)).scalar()
    total_resumes = db.query(func.count(Resume.id)).scalar()
    active_candidates = db.query(func.count(Candidate.id)).filter(
        Candidate.status == 'active'
    ).scalar()
    
    return {
        "total_candidates": total_candidates,
        "total_resumes": total_resumes,
        "active_candidates": active_candidates
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
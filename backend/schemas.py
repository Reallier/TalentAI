from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date


# ============= 候选人相关 Schema =============

class CandidateBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    years_experience: Optional[int] = None
    current_title: Optional[str] = None
    current_company: Optional[str] = None
    skills: Optional[List[str]] = []
    education_level: Optional[str] = None
    source: Optional[str] = None


class CandidateCreate(CandidateBase):
    pass


class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    years_experience: Optional[int] = None
    current_title: Optional[str] = None
    current_company: Optional[str] = None
    skills: Optional[List[str]] = None
    education_level: Optional[str] = None


class CandidateResponse(CandidateBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============= 简历相关 Schema =============

class ResumeUpload(BaseModel):
    source: str = Field(default="upload", description="简历来源")


class ResumeResponse(BaseModel):
    id: int
    candidate_id: int
    file_uri: str
    file_type: Optional[str]
    text_hash: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============= 工作经历相关 Schema =============

class ExperienceBase(BaseModel):
    company: str
    title: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    skills: Optional[List[str]] = []
    description: Optional[str] = None


class ExperienceResponse(ExperienceBase):
    id: int
    candidate_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============= 项目经历相关 Schema =============

class ProjectResponse(BaseModel):
    id: int
    candidate_id: int
    project_name: Optional[str]
    role: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    skills: Optional[List[str]]
    description: Optional[str]
    
    class Config:
        from_attributes = True


# ============= 教育经历相关 Schema =============

class EducationResponse(BaseModel):
    id: int
    candidate_id: int
    school: Optional[str]
    degree: Optional[str]
    major: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    
    class Config:
        from_attributes = True


# ============= JD 解析相关 Schema =============

class JDParsedResult(BaseModel):
    """JD 解析结果"""
    must_skills: List[str] = Field(description="必备技能")
    nice_skills: List[str] = Field(description="加分技能")
    filters: Dict[str, Any] = Field(default_factory=dict, description="过滤条件")
    notes: Optional[str] = Field(None, description="其他备注")


# ============= 匹配相关 Schema =============

class Evidence(BaseModel):
    """匹配证据"""
    skill: str = Field(description="命中的技能")
    snippet: str = Field(description="证据片段")
    period: Optional[str] = Field(None, description="时间段")
    source_uri: Optional[str] = Field(None, description="来源URI")
    offset: Optional[int] = Field(None, description="偏移量")


class MatchFilters(BaseModel):
    """匹配过滤条件"""
    location: Optional[str] = None
    min_years: Optional[int] = None
    max_years: Optional[int] = None
    education_level: Optional[str] = None
    must_have_all: bool = Field(default=True, description="是否必须全部满足必备技能")


class MatchRequest(BaseModel):
    """匹配请求"""
    jd: str = Field(description="职位描述")
    filters: Optional[MatchFilters] = None
    top_k: int = Field(default=20, ge=1, le=100)
    explain: bool = Field(default=True, description="是否生成解释")


class CandidateMatch(BaseModel):
    """候选人匹配结果"""
    candidate_id: int
    name: str
    current_title: Optional[str]
    current_company: Optional[str]
    location: Optional[str]
    years_experience: Optional[int]
    score: float = Field(description="综合匹配分数")
    score_breakdown: Dict[str, float] = Field(description="分数分解")
    evidence: List[Evidence] = Field(description="匹配证据")
    gaps: List[str] = Field(default_factory=list, description="缺口清单")
    matched_skills: List[str] = Field(description="匹配的技能")
    missing_skills: List[str] = Field(description="缺失的技能")


class MatchResponse(BaseModel):
    """匹配响应"""
    jd_parsed: JDParsedResult
    matches: List[CandidateMatch]
    total: int
    as_of: datetime = Field(default_factory=datetime.utcnow)


# ============= 搜索相关 Schema =============

class SearchRequest(BaseModel):
    """搜索请求"""
    q: str = Field(description="搜索关键词")
    filters: Optional[Dict[str, Any]] = None
    top_k: int = Field(default=20, ge=1, le=100)


class SearchResult(BaseModel):
    """搜索结果"""
    candidate_id: int
    name: str
    current_title: Optional[str]
    current_company: Optional[str]
    skills: List[str]
    score: float
    snippet: Optional[str] = Field(None, description="匹配片段")


class SearchResponse(BaseModel):
    """搜索响应"""
    results: List[SearchResult]
    total: int
    query: str


# ============= 候选人详情 Schema =============

class CandidateDetail(CandidateResponse):
    """候选人详细信息"""
    resumes: List[ResumeResponse] = []
    experiences: List[ExperienceResponse] = []
    projects: List[ProjectResponse] = []
    education: List[EducationResponse] = []
    index_updated_at: Optional[datetime] = None
    embedding_version: Optional[int] = None


# ============= 合并谱系 Schema =============

class MergeLineageResponse(BaseModel):
    """合并谱系响应"""
    id: int
    candidate_id: int
    from_resume_id: Optional[int]
    merge_rule: str
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    decided_by: str
    decided_at: datetime
    
    class Config:
        from_attributes = True


# ============= 重建索引相关 Schema =============

class ReindexRequest(BaseModel):
    """重建索引请求"""
    candidate_ids: Optional[List[int]] = Field(None, description="指定候选人ID列表")
    updated_since: Optional[datetime] = Field(None, description="仅重建此时间后更新的候选人")


class ReindexResponse(BaseModel):
    """重建索引响应"""
    success: bool
    reindexed_count: int
    failed_count: int
    errors: List[str] = []


# ============= 简历入库相关 Schema =============

class IngestResponse(BaseModel):
    """简历入库响应"""
    success: bool
    candidate_id: int
    resume_id: int
    is_new: bool = Field(description="是否新建候选人")
    merged_with: Optional[int] = Field(None, description="合并到的候选人ID")
    message: str
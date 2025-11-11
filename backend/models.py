from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, ARRAY, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from database import Base
from datetime import datetime


class Candidate(Base):
    """候选人模型"""
    __tablename__ = "candidates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), index=True)
    phone = Column(String(50), index=True)
    location = Column(String(100), index=True)
    years_experience = Column(Integer)
    current_title = Column(String(200))
    current_company = Column(String(200))
    skills = Column(ARRAY(Text))
    education_level = Column(String(50))
    source = Column(String(100))
    status = Column(String(50), default='active', index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    
    # 关系
    resumes = relationship("Resume", back_populates="candidate", cascade="all, delete-orphan")
    experiences = relationship("Experience", back_populates="candidate", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="candidate", cascade="all, delete-orphan")
    education = relationship("Education", back_populates="candidate", cascade="all, delete-orphan")
    index = relationship("CandidateIndex", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
    merge_lineage = relationship("MergeLineage", back_populates="candidate", cascade="all, delete-orphan")
    skill_recency = relationship("SkillRecency", back_populates="candidate", cascade="all, delete-orphan")


class Resume(Base):
    """简历模型"""
    __tablename__ = "resumes"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey('candidates.id', ondelete='CASCADE'), index=True)
    file_uri = Column(String(500), nullable=False)
    file_type = Column(String(20))
    text_content = Column(Text)
    text_hash = Column(String(64), unique=True, index=True)
    parsed_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    candidate = relationship("Candidate", back_populates="resumes")
    merge_lineage = relationship("MergeLineage", back_populates="from_resume")


class Experience(Base):
    """工作经历模型"""
    __tablename__ = "experiences"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey('candidates.id', ondelete='CASCADE'), index=True)
    company = Column(String(200), nullable=False)
    title = Column(String(200), nullable=False)
    start_date = Column(Date)
    end_date = Column(Date, index=True)
    skills = Column(ARRAY(Text))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    candidate = relationship("Candidate", back_populates="experiences")
    projects = relationship("Project", back_populates="experience")


class Project(Base):
    """项目经历模型"""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey('candidates.id', ondelete='CASCADE'), index=True)
    experience_id = Column(Integer, ForeignKey('experiences.id', ondelete='SET NULL'))
    project_name = Column(String(200))
    role = Column(String(100))
    start_date = Column(Date)
    end_date = Column(Date)
    skills = Column(ARRAY(Text))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    candidate = relationship("Candidate", back_populates="projects")
    experience = relationship("Experience", back_populates="projects")


class Education(Base):
    """教育经历模型"""
    __tablename__ = "education"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey('candidates.id', ondelete='CASCADE'), index=True)
    school = Column(String(200))
    degree = Column(String(100))
    major = Column(String(200))
    start_date = Column(Date)
    end_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    candidate = relationship("Candidate", back_populates="education")


class CandidateIndex(Base):
    """候选人索引模型（用于检索）"""
    __tablename__ = "candidate_index"
    
    candidate_id = Column(Integer, ForeignKey('candidates.id', ondelete='CASCADE'), primary_key=True)
    lexical_tsv = Column(Text)  # PostgreSQL tsvector 存储为文本
    embedding = Column(Vector(1536))  # OpenAI embedding 维度
    filters_json = Column(JSON)  # 过滤字段快照
    features_json = Column(JSON)  # 特征摘要
    embedding_version = Column(Integer, default=1)
    index_updated_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    candidate = relationship("Candidate", back_populates="index")


class MergeLineage(Base):
    """合并谱系模型"""
    __tablename__ = "merge_lineage"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey('candidates.id', ondelete='CASCADE'), index=True)
    from_resume_id = Column(Integer, ForeignKey('resumes.id', ondelete='SET NULL'), index=True)
    merge_rule = Column(String(100))
    field_name = Column(String(100))
    old_value = Column(Text)
    new_value = Column(Text)
    decided_by = Column(String(100), default='system')
    decided_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    candidate = relationship("Candidate", back_populates="merge_lineage")
    from_resume = relationship("Resume", back_populates="merge_lineage")


class AuditLog(Base):
    """审计日志模型"""
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), index=True)
    entity_id = Column(Integer, index=True)
    action = Column(String(50))
    changes = Column(JSON)
    performed_by = Column(String(100))
    performed_at = Column(DateTime, default=datetime.utcnow, index=True)


class SkillRecency(Base):
    """技能最后使用时间模型"""
    __tablename__ = "skill_recency"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey('candidates.id', ondelete='CASCADE'), index=True)
    skill = Column(String(200), index=True)
    last_used_date = Column(Date)
    source = Column(String(100))
    
    # 关系
    candidate = relationship("Candidate", back_populates="skill_recency")
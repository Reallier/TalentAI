from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, date
from models import Candidate, CandidateIndex, Experience, SkillRecency
from services.llm_service import LLMService
from config import settings
import asyncio


class IndexingService:
    """索引服务：负责全文索引和向量索引的创建与更新"""
    
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = LLMService()
        self.embedding_version = settings.embedding_version
    
    def index_candidate(
        self, 
        candidate_id: int,
        force: bool = False
    ) -> bool:
        """
        为候选人创建或更新索引
        
        Args:
            candidate_id: 候选人ID
            force: 是否强制重建索引
        
        Returns:
            是否成功
        """
        try:
            # 获取候选人完整信息
            candidate = self.db.query(Candidate).filter(
                Candidate.id == candidate_id
            ).first()
            
            if not candidate:
                return False
            
            # 检查是否需要更新索引
            existing_index = self.db.query(CandidateIndex).filter(
                CandidateIndex.candidate_id == candidate_id
            ).first()
            
            if existing_index and not force:
                # 如果索引最近更新过且版本一致，跳过
                if (existing_index.embedding_version == self.embedding_version and
                    existing_index.index_updated_at > candidate.updated_at):
                    return True
            
            # 1. 构建候选人数据
            candidate_data = self._build_candidate_data(candidate)
            
            # 2. 生成全文搜索向量
            lexical_text = self._build_lexical_text(candidate_data)
            
            # 3. 生成语义向量
            summary_text = self.llm_service.summarize_candidate(candidate_data)
            embedding = self.llm_service.generate_embedding(summary_text)
            
            if not embedding:
                print(f"为候选人 {candidate_id} 生成 embedding 失败")
                return False
            
            # 4. 构建过滤字段和特征
            filters_json = self._build_filters(candidate_data)
            features_json = self._build_features(candidate_data)
            
            # 5. 更新或创建索引
            if existing_index:
                # 更新现有索引
                # 使用原生 SQL 更新 tsvector 和 vector 字段
                self.db.execute(
                    text("""
                        UPDATE candidate_index 
                        SET lexical_tsv = to_tsvector('simple', :lexical_text),
                            embedding = :embedding::vector,
                            filters_json = :filters_json::jsonb,
                            features_json = :features_json::jsonb,
                            embedding_version = :version,
                            index_updated_at = :updated_at
                        WHERE candidate_id = :candidate_id
                    """),
                    {
                        'lexical_text': lexical_text,
                        'embedding': str(embedding),
                        'filters_json': filters_json,
                        'features_json': features_json,
                        'version': self.embedding_version,
                        'updated_at': datetime.utcnow(),
                        'candidate_id': candidate_id
                    }
                )
            else:
                # 创建新索引
                self.db.execute(
                    text("""
                        INSERT INTO candidate_index 
                        (candidate_id, lexical_tsv, embedding, filters_json, features_json, embedding_version, index_updated_at)
                        VALUES (:candidate_id, to_tsvector('simple', :lexical_text), :embedding::vector, 
                                :filters_json::jsonb, :features_json::jsonb, :version, :updated_at)
                    """),
                    {
                        'candidate_id': candidate_id,
                        'lexical_text': lexical_text,
                        'embedding': str(embedding),
                        'filters_json': filters_json,
                        'features_json': features_json,
                        'version': self.embedding_version,
                        'updated_at': datetime.utcnow()
                    }
                )
            
            # 6. 更新技能新鲜度
            self._update_skill_recency(candidate_id, candidate_data)
            
            # 提交
            self.db.commit()
            
            return True
        
        except Exception as e:
            print(f"索引候选人 {candidate_id} 失败: {str(e)}")
            self.db.rollback()
            return False
    
    def _build_candidate_data(self, candidate: Candidate) -> Dict[str, Any]:
        """构建候选人完整数据"""
        data = {
            'id': candidate.id,
            'name': candidate.name,
            'email': candidate.email,
            'phone': candidate.phone,
            'location': candidate.location,
            'years_experience': candidate.years_experience,
            'current_title': candidate.current_title,
            'current_company': candidate.current_company,
            'skills': candidate.skills or [],
            'education_level': candidate.education_level,
            'experiences': [],
            'projects': [],
            'education': []
        }
        
        # 加载关联数据
        for exp in candidate.experiences:
            data['experiences'].append({
                'company': exp.company,
                'title': exp.title,
                'start_date': exp.start_date,
                'end_date': exp.end_date,
                'skills': exp.skills or [],
                'description': exp.description
            })
        
        for proj in candidate.projects:
            data['projects'].append({
                'project_name': proj.project_name,
                'role': proj.role,
                'start_date': proj.start_date,
                'end_date': proj.end_date,
                'skills': proj.skills or [],
                'description': proj.description
            })
        
        for edu in candidate.education:
            data['education'].append({
                'school': edu.school,
                'degree': edu.degree,
                'major': edu.major,
                'start_date': edu.start_date,
                'end_date': edu.end_date
            })
        
        return data
    
    def _build_lexical_text(self, candidate_data: Dict[str, Any]) -> str:
        """构建用于全文搜索的文本"""
        parts = []
        
        # 基本信息
        if candidate_data.get('name'):
            parts.append(candidate_data['name'])
        if candidate_data.get('current_title'):
            parts.append(candidate_data['current_title'])
        if candidate_data.get('current_company'):
            parts.append(candidate_data['current_company'])
        if candidate_data.get('location'):
            parts.append(candidate_data['location'])
        
        # 技能
        if candidate_data.get('skills'):
            parts.extend(candidate_data['skills'])
        
        # 工作经历
        for exp in candidate_data.get('experiences', []):
            parts.append(exp.get('company', ''))
            parts.append(exp.get('title', ''))
            if exp.get('skills'):
                parts.extend(exp['skills'])
            if exp.get('description'):
                parts.append(exp['description'])
        
        # 项目经历
        for proj in candidate_data.get('projects', []):
            if proj.get('project_name'):
                parts.append(proj['project_name'])
            if proj.get('role'):
                parts.append(proj['role'])
            if proj.get('skills'):
                parts.extend(proj['skills'])
        
        # 教育背景
        for edu in candidate_data.get('education', []):
            parts.append(edu.get('school', ''))
            parts.append(edu.get('degree', ''))
            parts.append(edu.get('major', ''))
        
        # 过滤空值并拼接
        return ' '.join(filter(None, parts))
    
    def _build_filters(self, candidate_data: Dict[str, Any]) -> str:
        """构建过滤字段 JSON"""
        import json
        
        filters = {
            'location': candidate_data.get('location'),
            'years_experience': candidate_data.get('years_experience'),
            'education_level': candidate_data.get('education_level'),
            'current_company': candidate_data.get('current_company'),
            'status': 'active'
        }
        
        # 移除 None 值
        filters = {k: v for k, v in filters.items() if v is not None}
        
        return json.dumps(filters, ensure_ascii=False)
    
    def _build_features(self, candidate_data: Dict[str, Any]) -> str:
        """构建特征摘要 JSON"""
        import json
        
        # 提取关键特征
        features = {
            'key_skills': candidate_data.get('skills', [])[:10],  # 前10个技能
            'recent_companies': [],
            'recent_titles': [],
            'education_institutions': []
        }
        
        # 最近的公司和职位
        for exp in candidate_data.get('experiences', [])[:3]:
            if exp.get('company'):
                features['recent_companies'].append(exp['company'])
            if exp.get('title'):
                features['recent_titles'].append(exp['title'])
        
        # 教育机构
        for edu in candidate_data.get('education', []):
            if edu.get('school'):
                features['education_institutions'].append(edu['school'])
        
        return json.dumps(features, ensure_ascii=False)
    
    def _update_skill_recency(
        self, 
        candidate_id: int, 
        candidate_data: Dict[str, Any]
    ):
        """更新技能最后使用时间"""
        skill_dates = {}
        
        # 从工作经历中提取技能和日期
        for exp in candidate_data.get('experiences', []):
            if exp.get('skills') and exp.get('end_date'):
                end_date = exp['end_date']
                if isinstance(end_date, str):
                    try:
                        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                    except:
                        continue
                
                for skill in exp['skills']:
                    if skill not in skill_dates or end_date > skill_dates[skill]:
                        skill_dates[skill] = end_date
        
        # 从项目中提取
        for proj in candidate_data.get('projects', []):
            if proj.get('skills') and proj.get('end_date'):
                end_date = proj['end_date']
                if isinstance(end_date, str):
                    try:
                        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                    except:
                        continue
                
                for skill in proj['skills']:
                    if skill not in skill_dates or end_date > skill_dates[skill]:
                        skill_dates[skill] = end_date
        
        # 删除旧的技能新鲜度记录
        self.db.query(SkillRecency).filter(
            SkillRecency.candidate_id == candidate_id
        ).delete()
        
        # 插入新记录
        for skill, last_date in skill_dates.items():
            skill_rec = SkillRecency(
                candidate_id=candidate_id,
                skill=skill,
                last_used_date=last_date,
                source='experience'
            )
            self.db.add(skill_rec)
    
    def reindex_all(
        self, 
        candidate_ids: Optional[List[int]] = None,
        updated_since: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        重建索引
        
        Args:
            candidate_ids: 指定候选人ID列表，None 表示全部
            updated_since: 仅重建此时间后更新的候选人
        
        Returns:
            {'success': count, 'failed': count}
        """
        # 构建查询
        query = self.db.query(Candidate)
        
        if candidate_ids:
            query = query.filter(Candidate.id.in_(candidate_ids))
        
        if updated_since:
            query = query.filter(Candidate.updated_at >= updated_since)
        
        candidates = query.all()
        
        success_count = 0
        failed_count = 0
        
        for candidate in candidates:
            if self.index_candidate(candidate.id, force=True):
                success_count += 1
            else:
                failed_count += 1
        
        return {
            'success': success_count,
            'failed': failed_count
        }
    
    def delete_index(self, candidate_id: int) -> bool:
        """删除候选人索引"""
        try:
            self.db.query(CandidateIndex).filter(
                CandidateIndex.candidate_id == candidate_id
            ).delete()
            
            self.db.query(SkillRecency).filter(
                SkillRecency.candidate_id == candidate_id
            ).delete()
            
            self.db.commit()
            return True
        
        except Exception as e:
            print(f"删除索引失败: {str(e)}")
            self.db.rollback()
            return False
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
from datetime import datetime
from models import Candidate, Resume, Experience, Project, Education, AuditLog
from services.resume_parser import ResumeParser
from services.deduplication import DeduplicationService
from services.indexing_service import IndexingService
from config import settings
import os


class IngestService:
    """简历入库服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.parser = ResumeParser()
        self.dedup_service = DeduplicationService(db)
        self.indexing_service = IndexingService(db)
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    def ingest_resume(
        self,
        file_path: str,
        source: str = 'upload',
        merge_strategy: str = 'new_priority'
    ) -> Dict[str, Any]:
        """
        入库简历
        
        Args:
            file_path: 简历文件路径
            source: 来源标识
            merge_strategy: 合并策略
        
        Returns:
            {
                'success': bool,
                'candidate_id': int,
                'resume_id': int,
                'is_new': bool,
                'merged_with': Optional[int],
                'message': str
            }
        """
        try:
            # 1. 解析简历
            parsed_result = self.parser.parse_file(file_path)
            text_content = parsed_result['text_content']
            text_hash = parsed_result['text_hash']
            parsed_data = parsed_result['parsed_data']
            
            # 2. 提取关键信息用于判重
            personal_info = parsed_data.get('personal', {})
            email = personal_info.get('email')
            phone = personal_info.get('phone')
            name = personal_info.get('name')
            
            # 如果没有姓名，尝试从文本中提取
            if not name and parsed_data.get('experiences'):
                # 简单启发式：使用第一段经历之前的内容作为姓名候选
                name = text_content.split('\n')[0][:20]  # 取第一行前20字符
            
            # 3. 判重
            existing_candidate, match_type = self.dedup_service.find_duplicates(
                email=email,
                phone=phone,
                name=name,
                text_hash=text_hash,
                current_company=parsed_data.get('experiences', [{}])[0].get('company') if parsed_data.get('experiences') else None
            )
            
            # 4. 保存文件到永久存储
            file_uri = self._save_file(file_path, text_hash)
            
            # 5. 创建或更新候选人
            if existing_candidate:
                # 合并到现有候选人
                candidate_id = existing_candidate.id
                is_new = False
                
                # 创建新简历记录
                resume = Resume(
                    candidate_id=candidate_id,
                    file_uri=file_uri,
                    file_type=Path(file_path).suffix.lower(),
                    text_content=text_content,
                    text_hash=text_hash,
                    parsed_data=parsed_data
                )
                self.db.add(resume)
                self.db.flush()
                
                # 合并数据
                source_data = self._build_candidate_data(parsed_data)
                lineage_records = self.dedup_service.merge_candidates(
                    existing_candidate,
                    source_data,
                    resume.id,
                    merge_strategy
                )
                
                for record in lineage_records:
                    self.db.add(record)
                
                # 记录审计日志
                self._log_audit('candidate', candidate_id, 'merge', {
                    'from_resume_id': resume.id,
                    'match_type': match_type
                })
                
                message = f"简历已合并到现有候选人 (ID: {candidate_id})"
            
            else:
                # 创建新候选人
                candidate_data = self._build_candidate_data(parsed_data)
                candidate = Candidate(
                    name=name or '未知',
                    email=email,
                    phone=phone,
                    source=source,
                    **{k: v for k, v in candidate_data.items() 
                       if k in ['location', 'years_experience', 'current_title', 
                                'current_company', 'skills', 'education_level']}
                )
                self.db.add(candidate)
                self.db.flush()
                
                candidate_id = candidate.id
                is_new = True
                
                # 创建简历记录
                resume = Resume(
                    candidate_id=candidate_id,
                    file_uri=file_uri,
                    file_type=Path(file_path).suffix.lower(),
                    text_content=text_content,
                    text_hash=text_hash,
                    parsed_data=parsed_data
                )
                self.db.add(resume)
                self.db.flush()
                
                # 创建工作经历
                for exp_data in parsed_data.get('experiences', []):
                    experience = Experience(
                        candidate_id=candidate_id,
                        company=exp_data.get('company', ''),
                        title=exp_data.get('title', ''),
                        start_date=exp_data.get('start_date'),
                        end_date=exp_data.get('end_date'),
                        skills=exp_data.get('skills', []),
                        description=exp_data.get('description', '')
                    )
                    self.db.add(experience)
                
                # 创建项目经历
                for proj_data in parsed_data.get('projects', []):
                    project = Project(
                        candidate_id=candidate_id,
                        project_name=proj_data.get('project_name'),
                        role=proj_data.get('role'),
                        start_date=proj_data.get('start_date'),
                        end_date=proj_data.get('end_date'),
                        skills=proj_data.get('skills', []),
                        description=proj_data.get('description', '')
                    )
                    self.db.add(project)
                
                # 创建教育经历
                for edu_data in parsed_data.get('education', []):
                    education = Education(
                        candidate_id=candidate_id,
                        school=edu_data.get('school'),
                        degree=edu_data.get('degree'),
                        major=edu_data.get('major'),
                        start_date=edu_data.get('start_date'),
                        end_date=edu_data.get('end_date')
                    )
                    self.db.add(education)
                
                # 记录审计日志
                self._log_audit('candidate', candidate_id, 'create', {
                    'resume_id': resume.id,
                    'source': source
                })
                
                message = f"已创建新候选人 (ID: {candidate_id})"
            
            # 6. 提交事务
            self.db.commit()
            
            # 7. 异步建立索引（延迟几秒让数据稳定）
            # 这里简化为同步调用，实际应该用任务队列
            import time
            time.sleep(settings.index_delay_seconds)
            
            self.indexing_service.index_candidate(candidate_id, force=True)
            
            return {
                'success': True,
                'candidate_id': candidate_id,
                'resume_id': resume.id,
                'is_new': is_new,
                'merged_with': existing_candidate.id if existing_candidate else None,
                'message': message
            }
        
        except Exception as e:
            self.db.rollback()
            return {
                'success': False,
                'candidate_id': 0,
                'resume_id': 0,
                'is_new': False,
                'merged_with': None,
                'message': f'入库失败: {str(e)}'
            }
    
    def _build_candidate_data(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """从解析数据构建候选人数据"""
        personal = parsed_data.get('personal', {})
        experiences = parsed_data.get('experiences', [])
        education = parsed_data.get('education', [])
        skills = parsed_data.get('skills', [])
        
        # 提取当前职位和公司
        current_title = None
        current_company = None
        if experiences:
            latest_exp = experiences[0]
            current_title = latest_exp.get('title')
            current_company = latest_exp.get('company')
        
        # 计算工作年限
        years_experience = self._calculate_years_experience(experiences)
        
        # 提取教育水平
        education_level = self._extract_education_level(education)
        
        return {
            'email': personal.get('email'),
            'phone': personal.get('phone'),
            'location': personal.get('location'),
            'years_experience': years_experience,
            'current_title': current_title,
            'current_company': current_company,
            'skills': skills,
            'education_level': education_level
        }
    
    def _calculate_years_experience(self, experiences: list) -> Optional[int]:
        """计算工作年限"""
        if not experiences:
            return None
        
        # 简单计算：最早开始日期到现在
        earliest_date = None
        for exp in experiences:
            start_date = exp.get('start_date')
            if start_date:
                if earliest_date is None or start_date < earliest_date:
                    earliest_date = start_date
        
        if earliest_date:
            from datetime import date
            today = date.today()
            if isinstance(earliest_date, str):
                from datetime import datetime
                earliest_date = datetime.strptime(earliest_date, '%Y-%m-%d').date()
            
            years = (today - earliest_date).days / 365.25
            return int(years)
        
        return None
    
    def _extract_education_level(self, education: list) -> Optional[str]:
        """提取最高学历"""
        if not education:
            return None
        
        # 学历等级
        levels = {
            '博士': 5,
            'PhD': 5,
            'Doctor': 5,
            '硕士': 4,
            'Master': 4,
            'MBA': 4,
            '本科': 3,
            'Bachelor': 3,
            '学士': 3,
            '专科': 2,
            'Associate': 2
        }
        
        highest_level = 0
        highest_degree = None
        
        for edu in education:
            degree = edu.get('degree', '')
            for key, level in levels.items():
                if key in degree:
                    if level > highest_level:
                        highest_level = level
                        highest_degree = key
                        break
        
        return highest_degree
    
    def _save_file(self, source_path: str, text_hash: str) -> str:
        """保存文件到永久存储"""
        # 使用哈希作为文件名避免重复
        file_ext = Path(source_path).suffix
        dest_filename = f"{text_hash}{file_ext}"
        dest_path = self.upload_dir / dest_filename
        
        # 如果文件已存在，不重复保存
        if not dest_path.exists():
            shutil.copy2(source_path, dest_path)
        
        # 返回相对路径
        return str(dest_path.relative_to(self.upload_dir.parent))
    
    def _log_audit(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        changes: Dict[str, Any]
    ):
        """记录审计日志"""
        import json
        log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes=changes,
            performed_by='system',
            performed_at=datetime.utcnow()
        )
        self.db.add(log)
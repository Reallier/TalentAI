from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from models import Candidate, Resume, MergeLineage
from datetime import datetime
import difflib


class DeduplicationService:
    """候选人去重与合并服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.strong_match_threshold = 1.0  # 强匹配必须完全一致
        self.weak_similarity_threshold = 0.85  # 弱匹配相似度阈值
    
    def find_duplicates(
        self, 
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        text_hash: Optional[str] = None,
        current_company: Optional[str] = None
    ) -> Tuple[Optional[Candidate], str]:
        """
        查找重复候选人
        
        Returns:
            (candidate, match_type): 
                - candidate: 找到的重复候选人，None 表示未找到
                - match_type: 'strong' 或 'weak' 或 'none'
        """
        # 1. 强匹配：邮箱或电话完全一致
        if email or phone:
            strong_match = self._find_strong_match(email, phone)
            if strong_match:
                return strong_match, 'strong'
        
        # 2. 文本哈希完全一致（同一份简历）
        if text_hash:
            hash_match = self._find_by_text_hash(text_hash)
            if hash_match:
                return hash_match, 'strong'
        
        # 3. 弱匹配：姓名 + 公司 + 相似度
        if name:
            weak_match = self._find_weak_match(name, current_company)
            if weak_match:
                return weak_match, 'weak'
        
        return None, 'none'
    
    def _find_strong_match(
        self, 
        email: Optional[str], 
        phone: Optional[str]
    ) -> Optional[Candidate]:
        """强匹配：邮箱或电话一致"""
        conditions = []
        
        if email:
            conditions.append(Candidate.email == email)
        if phone:
            conditions.append(Candidate.phone == phone)
        
        if not conditions:
            return None
        
        return self.db.query(Candidate).filter(or_(*conditions)).first()
    
    def _find_by_text_hash(self, text_hash: str) -> Optional[Candidate]:
        """通过文本哈希查找候选人"""
        resume = self.db.query(Resume).filter(Resume.text_hash == text_hash).first()
        if resume:
            return self.db.query(Candidate).filter(Candidate.id == resume.candidate_id).first()
        return None
    
    def _find_weak_match(
        self, 
        name: str, 
        current_company: Optional[str]
    ) -> Optional[Candidate]:
        """弱匹配：姓名 + 公司相似度"""
        # 查找同名候选人
        candidates = self.db.query(Candidate).filter(Candidate.name == name).all()
        
        if not candidates:
            return None
        
        # 如果有公司信息，计算相似度
        if current_company:
            best_match = None
            best_score = 0.0
            
            for candidate in candidates:
                if candidate.current_company:
                    # 计算公司名称相似度
                    similarity = difflib.SequenceMatcher(
                        None, 
                        current_company.lower(), 
                        candidate.current_company.lower()
                    ).ratio()
                    
                    if similarity > best_score:
                        best_score = similarity
                        best_match = candidate
            
            # 如果相似度超过阈值，认为是弱匹配
            if best_score >= self.weak_similarity_threshold:
                return best_match
        
        # 只有姓名匹配但没有公司信息，或相似度不够高
        return None
    
    def merge_candidates(
        self,
        target_candidate: Candidate,
        source_data: Dict[str, Any],
        resume_id: int,
        merge_strategy: str = 'new_priority'
    ) -> List[MergeLineage]:
        """
        合并候选人信息
        
        Args:
            target_candidate: 目标候选人（已存在）
            source_data: 来源数据（新简历解析的数据）
            resume_id: 简历ID
            merge_strategy: 合并策略
                - new_priority: 新数据优先
                - source_priority: 依据来源优先级
                - non_empty_priority: 非空优先
        
        Returns:
            合并谱系记录列表
        """
        lineage_records = []
        
        # 定义需要合并的字段
        mergeable_fields = [
            'email', 'phone', 'location', 'years_experience',
            'current_title', 'current_company', 'skills', 'education_level'
        ]
        
        for field in mergeable_fields:
            old_value = getattr(target_candidate, field, None)
            new_value = source_data.get(field)
            
            # 根据策略决定是否更新
            should_update, final_value = self._decide_merge(
                field, old_value, new_value, merge_strategy
            )
            
            if should_update:
                # 记录合并谱系
                lineage = MergeLineage(
                    candidate_id=target_candidate.id,
                    from_resume_id=resume_id,
                    merge_rule=merge_strategy,
                    field_name=field,
                    old_value=str(old_value) if old_value else None,
                    new_value=str(final_value) if final_value else None,
                    decided_by='system',
                    decided_at=datetime.utcnow()
                )
                lineage_records.append(lineage)
                
                # 更新字段
                setattr(target_candidate, field, final_value)
        
        # 更新时间戳
        target_candidate.updated_at = datetime.utcnow()
        
        return lineage_records
    
    def _decide_merge(
        self,
        field_name: str,
        old_value: Any,
        new_value: Any,
        strategy: str
    ) -> Tuple[bool, Any]:
        """
        根据策略决定是否合并以及最终值
        
        Returns:
            (should_update, final_value)
        """
        # 如果新值为空，不更新
        if new_value is None or (isinstance(new_value, (list, str)) and not new_value):
            return False, old_value
        
        # 如果旧值为空，直接使用新值
        if old_value is None or (isinstance(old_value, (list, str)) and not old_value):
            return True, new_value
        
        # 根据策略决定
        if strategy == 'new_priority':
            # 新数据优先：总是使用新值
            return True, new_value
        
        elif strategy == 'non_empty_priority':
            # 非空优先：已经处理过了（上面的逻辑）
            return False, old_value
        
        elif strategy == 'source_priority':
            # 来源优先：可以根据来源可信度决定（这里简化为新优先）
            return True, new_value
        
        # 特殊处理：技能列表合并
        if field_name == 'skills' and isinstance(old_value, list) and isinstance(new_value, list):
            # 合并去重
            merged_skills = list(set(old_value + new_value))
            if merged_skills != old_value:
                return True, merged_skills
        
        return False, old_value
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度"""
        return difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def suggest_merge_candidates(
        self,
        candidate: Candidate,
        limit: int = 5
    ) -> List[Tuple[Candidate, float]]:
        """
        建议可能需要合并的候选人
        
        Returns:
            [(candidate, similarity_score), ...]
        """
        suggestions = []
        
        # 查找同名候选人
        if candidate.name:
            same_name = self.db.query(Candidate).filter(
                and_(
                    Candidate.name == candidate.name,
                    Candidate.id != candidate.id
                )
            ).all()
            
            for other in same_name:
                # 计算综合相似度
                score = self._calculate_candidate_similarity(candidate, other)
                if score >= self.weak_similarity_threshold:
                    suggestions.append((other, score))
        
        # 按相似度排序
        suggestions.sort(key=lambda x: x[1], reverse=True)
        
        return suggestions[:limit]
    
    def _calculate_candidate_similarity(
        self,
        candidate1: Candidate,
        candidate2: Candidate
    ) -> float:
        """计算两个候选人的综合相似度"""
        scores = []
        
        # 姓名相似度（已经是同名了，得分为1）
        scores.append(1.0)
        
        # 公司相似度
        if candidate1.current_company and candidate2.current_company:
            company_sim = self.calculate_similarity(
                candidate1.current_company,
                candidate2.current_company
            )
            scores.append(company_sim)
        
        # 职位相似度
        if candidate1.current_title and candidate2.current_title:
            title_sim = self.calculate_similarity(
                candidate1.current_title,
                candidate2.current_title
            )
            scores.append(title_sim)
        
        # 技能重叠度
        if candidate1.skills and candidate2.skills:
            skills1 = set(candidate1.skills)
            skills2 = set(candidate2.skills)
            if skills1 or skills2:
                skill_overlap = len(skills1 & skills2) / len(skills1 | skills2)
                scores.append(skill_overlap)
        
        # 计算加权平均
        if scores:
            return sum(scores) / len(scores)
        
        return 0.0
    
    def resolve_duplicate_manual(
        self,
        target_id: int,
        source_id: int,
        decided_by: str = 'user'
    ) -> bool:
        """
        手动解决重复：将 source 合并到 target
        
        Args:
            target_id: 保留的候选人ID
            source_id: 要合并的候选人D
            decided_by: 决策者
        
        Returns:
            是否成功
        """
        target = self.db.query(Candidate).filter(Candidate.id == target_id).first()
        source = self.db.query(Candidate).filter(Candidate.id == source_id).first()
        
        if not target or not source:
            return False
        
        # 收集 source 的数据
        source_data = {
            'email': source.email,
            'phone': source.phone,
            'location': source.location,
            'years_experience': source.years_experience,
            'current_title': source.current_title,
            'current_company': source.current_company,
            'skills': source.skills,
            'education_level': source.education_level
        }
        
        # 合并（使用非空优先策略）
        lineage_records = self.merge_candidates(
            target, 
            source_data, 
            resume_id=0,  # 手动合并没有特定简历
            merge_strategy='non_empty_priority'
        )
        
        # 标记决策者
        for record in lineage_records:
            record.decided_by = decided_by
        
        # 将 source 的简历转移到 target
        self.db.query(Resume).filter(Resume.candidate_id == source_id).update(
            {'candidate_id': target_id}
        )
        
        # 将 source 的经历转移到 target
        # 这里简化处理，实际可能需要更复杂的合并逻辑
        from models import Experience, Project, Education
        self.db.query(Experience).filter(Experience.candidate_id == source_id).update(
            {'candidate_id': target_id}
        )
        self.db.query(Project).filter(Project.candidate_id == source_id).update(
            {'candidate_id': target_id}
        )
        self.db.query(Education).filter(Education.candidate_id == source_id).update(
            {'candidate_id': target_id}
        )
        
        # 保存合并谱系
        for record in lineage_records:
            self.db.add(record)
        
        # 删除 source 候选人
        self.db.delete(source)
        
        # 提交事务
        self.db.commit()
        
        return True
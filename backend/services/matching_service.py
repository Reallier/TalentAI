from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_
from datetime import datetime, timedelta
from models import Candidate, CandidateIndex, SkillRecency
from services.llm_service import LLMService
from config import settings
import math


class MatchingService:
    """匹配服务：JD 匹配候选人"""
    
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = LLMService()
        
        # 排序权重
        self.weight_vector = settings.weight_vector_sim
        self.weight_lexical = settings.weight_lexical
        self.weight_skill_coverage = settings.weight_skill_coverage
        self.weight_recency = settings.weight_recency
        
        # 召回配置
        self.topk_lexical = settings.topk_lexical
        self.topk_vector = settings.topk_vector
        self.topk_final = settings.topk_final
    
    def match_candidates(
        self,
        jd_text: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        explain: bool = True
    ) -> Dict[str, Any]:
        """
        根据 JD 匹配候选人
        
        Args:
            jd_text: 职位描述
            filters: 过滤条件
            top_k: 返回Top K个结果
            explain: 是否生成解释
        
        Returns:
            {
                'jd_parsed': JD解析结果,
                'matches': 匹配的候选人列表,
                'total': 总数,
                'as_of': 时间戳
            }
        """
        top_k = top_k or self.topk_final
        
        # 1. 解析 JD
        jd_parsed = self.llm_service.parse_jd(jd_text)
        
        # 2. 双路召回
        lexical_candidates = self._lexical_recall(
            jd_parsed, 
            filters, 
            self.topk_lexical
        )
        
        vector_candidates = self._vector_recall(
            jd_text,
            filters,
            self.topk_vector
        )
        
        # 3. 合并去重
        all_candidates = self._merge_candidates(
            lexical_candidates, 
            vector_candidates
        )
        
        # 4. 融合排序
        ranked_candidates = self._rank_candidates(
            all_candidates,
            jd_parsed,
            jd_text
        )
        
        # 5. 截取 Top K
        top_candidates = ranked_candidates[:top_k]
        
        # 6. 生成证据和解释
        if explain:
            for candidate_match in top_candidates:
                self._add_evidence(candidate_match, jd_parsed, jd_text)
        
        return {
            'jd_parsed': jd_parsed,
            'matches': top_candidates,
            'total': len(top_candidates),
            'as_of': datetime.utcnow()
        }
    
    def _lexical_recall(
        self,
        jd_parsed: Dict[str, Any],
        filters: Optional[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """关键词召回"""
        try:
            # 构建搜索查询
            search_terms = []
            search_terms.extend(jd_parsed.get('must_skills', []))
            search_terms.extend(jd_parsed.get('nice_skills', []))
            
            if not search_terms:
                return []
            
            # 使用 PostgreSQL 全文搜索
            search_query = ' | '.join(search_terms)  # OR 查询
            
            # 构建 SQL
            sql = text("""
                SELECT 
                    c.id,
                    c.name,
                    c.current_title,
                    c.current_company,
                    c.location,
                    c.years_experience,
                    c.skills,
                    ci.embedding,
                    ts_rank(ci.lexical_tsv, to_tsquery('simple', :query)) as lexical_score
                FROM candidates c
                JOIN candidate_index ci ON c.id = ci.candidate_id
                WHERE ci.lexical_tsv @@ to_tsquery('simple', :query)
                    AND c.status = 'active'
                ORDER BY lexical_score DESC
                LIMIT :limit
            """)
            
            result = self.db.execute(
                sql,
                {'query': search_query, 'limit': top_k}
            )
            
            candidates = []
            for row in result:
                candidates.append({
                    'candidate_id': row[0],
                    'name': row[1],
                    'current_title': row[2],
                    'current_company': row[3],
                    'location': row[4],
                    'years_experience': row[5],
                    'skills': row[6] or [],
                    'embedding': row[7],
                    'lexical_score': float(row[8]) if row[8] else 0.0,
                    'vector_score': 0.0,  # 稍后计算
                    'source': 'lexical'
                })
            
            return candidates
        
        except Exception as e:
            print(f"关键词召回失败: {str(e)}")
            return []
    
    def _vector_recall(
        self,
        jd_text: str,
        filters: Optional[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """向量召回"""
        try:
            # 生成 JD 的 embedding
            jd_embedding = self.llm_service.generate_embedding(jd_text)
            
            if not jd_embedding:
                print("生成 JD embedding 失败，跳过向量召回")
                return []
            
            # 使用向量相似度搜索
            sql = text("""
                SELECT 
                    c.id,
                    c.name,
                    c.current_title,
                    c.current_company,
                    c.location,
                    c.years_experience,
                    c.skills,
                    ci.embedding,
                    1 - (ci.embedding <=> :query_embedding::vector) as vector_score
                FROM candidates c
                JOIN candidate_index ci ON c.id = ci.candidate_id
                WHERE c.status = 'active'
                ORDER BY ci.embedding <=> :query_embedding::vector
                LIMIT :limit
            """)
            
            result = self.db.execute(
                sql,
                {'query_embedding': str(jd_embedding), 'limit': top_k}
            )
            
            candidates = []
            for row in result:
                candidates.append({
                    'candidate_id': row[0],
                    'name': row[1],
                    'current_title': row[2],
                    'current_company': row[3],
                    'location': row[4],
                    'years_experience': row[5],
                    'skills': row[6] or [],
                    'embedding': row[7],
                    'lexical_score': 0.0,  # 稍后补充
                    'vector_score': float(row[8]) if row[8] else 0.0,
                    'source': 'vector'
                })
            
            return candidates
        
        except Exception as e:
            print(f"向量召回失败: {str(e)}")
            return []
    
    def _merge_candidates(
        self,
        lexical_candidates: List[Dict[str, Any]],
        vector_candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """合并两路召回结果"""
        # 使用字典去重
        merged = {}
        
        for candidate in lexical_candidates:
            cid = candidate['candidate_id']
            merged[cid] = candidate
        
        for candidate in vector_candidates:
            cid = candidate['candidate_id']
            if cid in merged:
                # 已存在，更新向量分数
                merged[cid]['vector_score'] = candidate['vector_score']
                merged[cid]['source'] = 'both'
            else:
                merged[cid] = candidate
        
        return list(merged.values())
    
    def _rank_candidates(
        self,
        candidates: List[Dict[str, Any]],
        jd_parsed: Dict[str, Any],
        jd_text: str
    ) -> List[Dict[str, Any]]:
        """融合排序"""
        must_skills = set(jd_parsed.get('must_skills', []))
        nice_skills = set(jd_parsed.get('nice_skills', []))
        
        for candidate in candidates:
            # 计算各维度分数
            candidate_skills = set(candidate.get('skills', []))
            
            # 1. 向量相似度分数（已有）
            vector_score = candidate.get('vector_score', 0.0)
            
            # 2. 关键词分数（已有）
            lexical_score = candidate.get('lexical_score', 0.0)
            # 归一化 lexical_score（ts_rank 通常在 0-1 之间，但可能更小）
            lexical_score = min(lexical_score / 0.1, 1.0)  # 简单归一化
            
            # 3. 技能覆盖度
            must_coverage = (
                len(must_skills & candidate_skills) / len(must_skills)
                if must_skills else 1.0
            )
            nice_coverage = (
                len(nice_skills & candidate_skills) / len(nice_skills)
                if nice_skills else 0.0
            )
            skill_coverage_score = 0.7 * must_coverage + 0.3 * nice_coverage
            
            # 4. 新鲜度分数
            recency_score = self._calculate_recency_score(
                candidate['candidate_id'],
                must_skills | nice_skills
            )
            
            # 综合分数
            final_score = (
                self.weight_vector * vector_score +
                self.weight_lexical * lexical_score +
                self.weight_skill_coverage * skill_coverage_score +
                self.weight_recency * recency_score
            )
            
            candidate['score'] = final_score
            candidate['score_breakdown'] = {
                'vector_sim': vector_score,
                'lexical': lexical_score,
                'skill_coverage': skill_coverage_score,
                'recency': recency_score
            }
            
            # 记录匹配和缺失的技能
            candidate['matched_skills'] = list(
                must_skills & candidate_skills | nice_skills & candidate_skills
            )
            candidate['missing_skills'] = list(must_skills - candidate_skills)
        
        # 按分数排序
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        return candidates
    
    def _calculate_recency_score(
        self,
        candidate_id: int,
        required_skills: set
    ) -> float:
        """计算技能新鲜度分数"""
        try:
            # 查询相关技能的最后使用时间
            skill_recency = self.db.query(SkillRecency).filter(
                and_(
                    SkillRecency.candidate_id == candidate_id,
                    SkillRecency.skill.in_(required_skills)
                )
            ).all()
            
            if not skill_recency:
                return 0.5  # 无数据时给中等分数
            
            # 计算平均新鲜度
            today = datetime.now().date()
            total_score = 0.0
            
            for rec in skill_recency:
                if rec.last_used_date:
                    days_ago = (today - rec.last_used_date).days
                    # 使用指数衰减：越近越高分
                    # 1年内：高分，2年：中分，3年以上：低分
                    decay_score = math.exp(-days_ago / 730)  # 730天 = 2年半衰期
                    total_score += decay_score
            
            avg_score = total_score / len(skill_recency)
            return min(avg_score, 1.0)
        
        except Exception as e:
            print(f"计算新鲜度失败: {str(e)}")
            return 0.5
    
    def _add_evidence(
        self,
        candidate_match: Dict[str, Any],
        jd_parsed: Dict[str, Any],
        jd_text: str
    ):
        """为匹配结果添加证据"""
        try:
            # 获取候选人完整信息
            candidate = self.db.query(Candidate).filter(
                Candidate.id == candidate_match['candidate_id']
            ).first()
            
            if not candidate:
                candidate_match['evidence'] = []
                candidate_match['gaps'] = candidate_match.get('missing_skills', [])
                return
            
            # 构建候选人文本
            candidate_text_parts = []
            if candidate.current_title and candidate.current_company:
                candidate_text_parts.append(
                    f"{candidate.current_title} @ {candidate.current_company}"
                )
            
            for exp in candidate.experiences[:3]:  # 最近3段经历
                exp_text = f"{exp.company} - {exp.title}"
                if exp.description:
                    exp_text += f": {exp.description[:200]}"
                candidate_text_parts.append(exp_text)
            
            candidate_text = "\n".join(candidate_text_parts)
            
            # 使用 LLM 生成证据
            matched_skills = candidate_match.get('matched_skills', [])[:5]  # 最多5个
            if matched_skills:
                evidences = self.llm_service.generate_evidence(
                    candidate_text,
                    matched_skills,
                    jd_text,
                    max_evidences=3
                )
                candidate_match['evidence'] = evidences
            else:
                candidate_match['evidence'] = []
            
            # 缺口清单
            candidate_match['gaps'] = candidate_match.get('missing_skills', [])
        
        except Exception as e:
            print(f"生成证据失败: {str(e)}")
            candidate_match['evidence'] = []
            candidate_match['gaps'] = []
    
    def search_candidates(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        关键词搜索候选人
        
        Args:
            query: 搜索关键词
            filters: 过滤条件
            top_k: 返回数量
        
        Returns:
            候选人列表
        """
        try:
            # 使用全文搜索
            sql = text("""
                SELECT 
                    c.id,
                    c.name,
                    c.current_title,
                    c.current_company,
                    c.skills,
                    ts_rank(ci.lexical_tsv, plainto_tsquery('simple', :query)) as score,
                    ts_headline('simple', c.current_title || ' ' || c.current_company, 
                                plainto_tsquery('simple', :query)) as snippet
                FROM candidates c
                JOIN candidate_index ci ON c.id = ci.candidate_id
                WHERE ci.lexical_tsv @@ plainto_tsquery('simple', :query)
                    AND c.status = 'active'
                ORDER BY score DESC
                LIMIT :limit
            """)
            
            result = self.db.execute(
                sql,
                {'query': query, 'limit': top_k}
            )
            
            candidates = []
            for row in result:
                candidates.append({
                    'candidate_id': row[0],
                    'name': row[1],
                    'current_title': row[2],
                    'current_company': row[3],
                    'skills': row[4] or [],
                    'score': float(row[5]) if row[5] else 0.0,
                    'snippet': row[6] if row[6] else ''
                })
            
            return candidates
        
        except Exception as e:
            print(f"搜索失败: {str(e)}")
            return []
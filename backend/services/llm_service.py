import openai
from typing import List, Dict, Any, Optional
from config import settings
import tiktoken
import json


class LLMService:
    """LLM 服务：用于 JD 解析、生成 embeddings 等"""
    
    def __init__(self):
        openai.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.embedding_model = settings.openai_embedding_model
        self.encoding = tiktoken.encoding_for_model("gpt-4")
    
    def parse_jd(self, jd_text: str) -> Dict[str, Any]:
        """
        解析 JD，提取必备技能、加分技能、过滤条件等
        
        Returns:
            {
                'must_skills': List[str],
                'nice_skills': List[str],
                'filters': Dict,
                'notes': str
            }
        """
        prompt = f"""请分析以下职位描述(JD)，提取关键信息：

职位描述：
{jd_text}

请以 JSON 格式返回以下信息：
1. must_skills: 必备技能列表（硬性要求）
2. nice_skills: 加分技能列表（优先但非必须）
3. filters: 过滤条件，包含：
   - location: 工作地点
   - min_years: 最少工作年限
   - max_years: 最多工作年限
   - education_level: 学历要求（如：本科、硕士、博士）
4. notes: 其他重要备注

请确保返回有效的 JSON 格式。"""

        try:
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的招聘分析助手，擅长从职位描述中提取结构化信息。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # 确保返回格式正确
            return {
                'must_skills': result.get('must_skills', []),
                'nice_skills': result.get('nice_skills', []),
                'filters': result.get('filters', {}),
                'notes': result.get('notes', '')
            }
        
        except Exception as e:
            # 降级：返回空结果
            print(f"JD 解析失败: {str(e)}")
            return {
                'must_skills': [],
                'nice_skills': [],
                'filters': {},
                'notes': f'解析失败: {str(e)}'
            }
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        生成文本的向量表示
        
        Args:
            text: 要向量化的文本
        
        Returns:
            embedding 向量（1536 维）
        """
        try:
            # 截断过长的文本（OpenAI 有 token 限制）
            text = self._truncate_text(text, max_tokens=8000)
            
            response = openai.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            return response.data[0].embedding
        
        except Exception as e:
            print(f"生成 embedding 失败: {str(e)}")
            return None
    
    def generate_embeddings_batch(
        self, 
        texts: List[str]
    ) -> List[Optional[List[float]]]:
        """
        批量生成 embeddings
        
        Args:
            texts: 文本列表
        
        Returns:
            embeddings 列表
        """
        embeddings = []
        
        # 批量处理（OpenAI API 支持批量）
        try:
            # 截断所有文本
            truncated_texts = [
                self._truncate_text(text, max_tokens=8000) 
                for text in texts
            ]
            
            response = openai.embeddings.create(
                model=self.embedding_model,
                input=truncated_texts
            )
            
            # 按顺序提取 embeddings
            for item in response.data:
                embeddings.append(item.embedding)
            
            return embeddings
        
        except Exception as e:
            print(f"批量生成 embeddings 失败: {str(e)}")
            # 降级：逐个生成
            for text in texts:
                emb = self.generate_embedding(text)
                embeddings.append(emb)
            
            return embeddings
    
    def generate_evidence(
        self,
        candidate_text: str,
        matched_skills: List[str],
        jd_text: str,
        max_evidences: int = 3
    ) -> List[Dict[str, Any]]:
        """
        生成匹配证据
        
        Args:
            candidate_text: 候选人简历文本
            matched_skills: 匹配的技能列表
            jd_text: 职位描述
            max_evidences: 最多返回几条证据
        
        Returns:
            证据列表，每条包含 skill, snippet, period 等
        """
        prompt = f"""请从以下候选人简历中，为匹配的技能找出具体的证据片段。

匹配的技能：{', '.join(matched_skills)}

候选人简历：
{candidate_text[:2000]}  # 截取前2000字符

请为每个技能找出：
1. 证据片段（snippet）：相关的句子或段落
2. 时间段（period）：该技能使用的时间范围

以 JSON 格式返回，格式如下：
{{
  "evidences": [
    {{
      "skill": "技能名称",
      "snippet": "证据片段",
      "period": "时间段"
    }}
  ]
}}

最多返回 {max_evidences} 条证据。"""

        try:
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的简历分析助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get('evidences', [])
        
        except Exception as e:
            print(f"生成证据失败: {str(e)}")
            # 降级：返回简单的匹配列表
            return [
                {
                    'skill': skill,
                    'snippet': f'候选人简历中提及了 {skill}',
                    'period': '未知'
                }
                for skill in matched_skills[:max_evidences]
            ]
    
    def summarize_candidate(self, candidate_data: Dict[str, Any]) -> str:
        """
        生成候选人摘要（用于向量化）
        
        Args:
            candidate_data: 候选人完整数据
        
        Returns:
            摘要文本
        """
        # 构建摘要文本
        parts = []
        
        # 基本信息
        if candidate_data.get('name'):
            parts.append(f"姓名：{candidate_data['name']}")
        
        if candidate_data.get('current_title'):
            parts.append(f"当前职位：{candidate_data['current_title']}")
        
        if candidate_data.get('current_company'):
            parts.append(f"当前公司：{candidate_data['current_company']}")
        
        if candidate_data.get('years_experience'):
            parts.append(f"工作年限：{candidate_data['years_experience']}年")
        
        # 技能
        if candidate_data.get('skills'):
            skills_text = ', '.join(candidate_data['skills'][:20])  # 最多20个技能
            parts.append(f"技能：{skills_text}")
        
        # 工作经历
        if candidate_data.get('experiences'):
            exp_texts = []
            for exp in candidate_data['experiences'][:3]:  # 最多3段经历
                exp_text = f"{exp.get('company', '')} - {exp.get('title', '')}"
                if exp.get('description'):
                    exp_text += f": {exp['description'][:100]}"  # 截取前100字符
                exp_texts.append(exp_text)
            if exp_texts:
                parts.append("工作经历：" + "; ".join(exp_texts))
        
        # 教育背景
        if candidate_data.get('education'):
            edu_texts = []
            for edu in candidate_data['education']:
                edu_text = f"{edu.get('school', '')} {edu.get('degree', '')} {edu.get('major', '')}"
                edu_texts.append(edu_text.strip())
            if edu_texts:
                parts.append("教育：" + "; ".join(edu_texts))
        
        return "\n".join(parts)
    
    def _truncate_text(self, text: str, max_tokens: int = 8000) -> str:
        """截断文本以符合 token 限制"""
        tokens = self.encoding.encode(text)
        if len(tokens) > max_tokens:
            tokens = tokens[:max_tokens]
            text = self.encoding.decode(tokens)
        return text
    
    def count_tokens(self, text: str) -> int:
        """计算文本的 token 数量"""
        return len(self.encoding.encode(text))
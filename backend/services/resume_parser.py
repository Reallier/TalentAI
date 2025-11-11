import re
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
import pypdf
import docx
import jieba
from pathlib import Path


class ResumeParser:
    """简历解析器 - 支持 PDF 和 DOCX"""
    
    def __init__(self):
        # 常见的章节标题关键词
        self.section_keywords = {
            'experience': ['工作经历', '工作经验', '项目经验', 'work experience', 'experience'],
            'education': ['教育背景', '教育经历', 'education'],
            'skills': ['技能', '专业技能', '技术栈', 'skills', 'technical skills'],
            'projects': ['项目经历', '项目经验', 'projects'],
            'personal': ['个人信息', '基本信息', 'personal information', 'contact'],
        }
        
        # 日期匹配模式
        self.date_patterns = [
            r'(\d{4})[年\-/.](\d{1,2})[月\-/.]?(\d{1,2})?',  # 2023年1月 或 2023-01
            r'(\d{4})[年\-/.](\d{1,2})',  # 2023年1月
            r'(\d{4})',  # 2023
        ]
    
    def parse_file(self, file_path: str) -> Dict:
        """
        解析简历文件
        
        Returns:
            {
                'text_content': str,
                'text_hash': str,
                'parsed_data': {
                    'personal': {...},
                    'experiences': [...],
                    'education': [...],
                    'skills': [...],
                    'projects': [...]
                }
            }
        """
        # 提取文本
        text_content = self._extract_text(file_path)
        
        # 计算哈希
        text_hash = self._compute_hash(text_content)
        
        # 解析结构化信息
        parsed_data = self._parse_structure(text_content)
        
        return {
            'text_content': text_content,
            'text_hash': text_hash,
            'parsed_data': parsed_data
        }
    
    def _extract_text(self, file_path: str) -> str:
        """从文件中提取文本"""
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            return self._extract_from_pdf(file_path)
        elif file_ext in ['.docx', '.doc']:
            return self._extract_from_docx(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {file_ext}")
    
    def _extract_from_pdf(self, file_path: str) -> str:
        """从 PDF 提取文本"""
        text_parts = []
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
        except Exception as e:
            raise ValueError(f"PDF 解析失败: {str(e)}")
        
        return '\n'.join(text_parts)
    
    def _extract_from_docx(self, file_path: str) -> str:
        """从 DOCX 提取文本"""
        text_parts = []
        try:
            doc = docx.Document(file_path)
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text.strip())
        except Exception as e:
            raise ValueError(f"DOCX 解析失败: {str(e)}")
        
        return '\n'.join(text_parts)
    
    def _compute_hash(self, text: str) -> str:
        """计算文本的 SHA256 哈希用于判重"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def _parse_structure(self, text: str) -> Dict:
        """解析简历结构"""
        lines = text.split('\n')
        sections = self._identify_sections(lines)
        
        return {
            'personal': self._extract_personal_info(sections.get('personal', [])),
            'experiences': self._extract_experiences(sections.get('experience', [])),
            'education': self._extract_education(sections.get('education', [])),
            'skills': self._extract_skills(sections.get('skills', []), text),
            'projects': self._extract_projects(sections.get('projects', []))
        }
    
    def _identify_sections(self, lines: List[str]) -> Dict[str, List[str]]:
        """识别简历各部分章节"""
        sections = {}
        current_section = None
        current_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是章节标题
            section_type = self._match_section_type(line)
            if section_type:
                # 保存上一个章节
                if current_section and current_lines:
                    sections[current_section] = current_lines
                
                # 开始新章节
                current_section = section_type
                current_lines = []
            elif current_section:
                current_lines.append(line)
        
        # 保存最后一个章节
        if current_section and current_lines:
            sections[current_section] = current_lines
        
        return sections
    
    def _match_section_type(self, line: str) -> Optional[str]:
        """匹配章节类型"""
        line_lower = line.lower()
        for section_type, keywords in self.section_keywords.items():
            for keyword in keywords:
                if keyword.lower() in line_lower:
                    return section_type
        return None
    
    def _extract_personal_info(self, lines: List[str]) -> Dict:
        """提取个人信息"""
        personal = {
            'name': None,
            'email': None,
            'phone': None,
            'location': None
        }
        
        text = '\n'.join(lines)
        
        # 提取邮箱
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        email_match = re.search(email_pattern, text)
        if email_match:
            personal['email'] = email_match.group()
        
        # 提取电话
        phone_pattern = r'1[3-9]\d{9}'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            personal['phone'] = phone_match.group()
        
        # 提取姓名（通常在第一行或靠前位置）
        if lines:
            # 简单启发式：第一行长度较短且不包含邮箱电话可能是姓名
            first_line = lines[0].strip()
            if len(first_line) <= 20 and '@' not in first_line and not phone_match:
                personal['name'] = first_line
        
        return personal
    
    def _extract_experiences(self, lines: List[str]) -> List[Dict]:
        """提取工作经历"""
        experiences = []
        current_exp = None
        
        for line in lines:
            # 检查是否包含日期（可能是新的经历）
            dates = self._extract_dates(line)
            if dates:
                # 保存上一个经历
                if current_exp:
                    experiences.append(current_exp)
                
                # 创建新经历
                current_exp = {
                    'company': self._extract_company(line),
                    'title': self._extract_title(line),
                    'start_date': dates[0] if len(dates) > 0 else None,
                    'end_date': dates[1] if len(dates) > 1 else None,
                    'description': [],
                    'skills': []
                }
            elif current_exp:
                # 添加到当前经历的描述中
                current_exp['description'].append(line)
                # 提取技能关键词
                skills = self._extract_skills_from_text(line)
                current_exp['skills'].extend(skills)
        
        # 保存最后一个经历
        if current_exp:
            current_exp['description'] = '\n'.join(current_exp['description'])
            current_exp['skills'] = list(set(current_exp['skills']))  # 去重
            experiences.append(current_exp)
        
        return experiences
    
    def _extract_projects(self, lines: List[str]) -> List[Dict]:
        """提取项目经历"""
        projects = []
        current_proj = None
        
        for line in lines:
            dates = self._extract_dates(line)
            if dates or (line.strip() and len(line) < 100 and '项目' in line):
                # 保存上一个项目
                if current_proj:
                    projects.append(current_proj)
                
                # 创建新项目
                current_proj = {
                    'project_name': self._extract_project_name(line),
                    'role': self._extract_role(line),
                    'start_date': dates[0] if dates and len(dates) > 0 else None,
                    'end_date': dates[1] if dates and len(dates) > 1 else None,
                    'description': [],
                    'skills': []
                }
            elif current_proj:
                current_proj['description'].append(line)
                skills = self._extract_skills_from_text(line)
                current_proj['skills'].extend(skills)
        
        # 保存最后一个项目
        if current_proj:
            current_proj['description'] = '\n'.join(current_proj['description'])
            current_proj['skills'] = list(set(current_proj['skills']))
            projects.append(current_proj)
        
        return projects
    
    def _extract_education(self, lines: List[str]) -> List[Dict]:
        """提取教育经历"""
        education = []
        
        for line in lines:
            dates = self._extract_dates(line)
            if dates or any(keyword in line for keyword in ['大学', '学院', 'University', 'College']):
                edu = {
                    'school': self._extract_school(line),
                    'degree': self._extract_degree(line),
                    'major': self._extract_major(line),
                    'start_date': dates[0] if dates and len(dates) > 0 else None,
                    'end_date': dates[1] if dates and len(dates) > 1 else None,
                }
                education.append(edu)
        
        return education
    
    def _extract_skills(self, lines: List[str], full_text: str) -> List[str]:
        """提取技能列表"""
        skills = set()
        
        # 从技能章节提取
        for line in lines:
            # 分词并提取技术关键词
            extracted = self._extract_skills_from_text(line)
            skills.update(extracted)
        
        # 从全文提取常见技术栈
        extracted = self._extract_skills_from_text(full_text)
        skills.update(extracted)
        
        return list(skills)
    
    def _extract_skills_from_text(self, text: str) -> List[str]:
        """从文本中提取技能关键词"""
        # 常见技术栈关键词
        tech_keywords = [
            # 编程语言
            'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Go', 'Rust', 'PHP', 'Ruby',
            'Swift', 'Kotlin', 'Scala', 'R', 'MATLAB',
            # 前端
            'React', 'Vue', 'Angular', 'HTML', 'CSS', 'jQuery', 'Bootstrap', 'Webpack', 'Vite',
            # 后端
            'Spring', 'Django', 'Flask', 'FastAPI', 'Express', 'Node.js', 'Nginx', 'Tomcat',
            # 数据库
            'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Oracle', 'SQL Server', 'SQLite',
            # 云计算
            'AWS', 'Azure', 'GCP', 'Kubernetes', 'Docker', 'Linux',
            # 大数据
            'Hadoop', 'Spark', 'Flink', 'Kafka', 'Hive', 'HBase',
            # AI/ML
            'TensorFlow', 'PyTorch', 'Scikit-learn', 'NLP', 'CV', 'LLM', 'RAG',
            # 其他
            'Git', 'Jenkins', 'CI/CD', 'Agile', 'Scrum', 'RESTful', 'GraphQL', 'gRPC',
            'Elasticsearch', 'RabbitMQ', 'Microservices'
        ]
        
        skills = []
        text_lower = text.lower()
        
        for keyword in tech_keywords:
            if keyword.lower() in text_lower:
                skills.append(keyword)
        
        return skills
    
    def _extract_dates(self, text: str) -> List[Optional[date]]:
        """提取日期"""
        dates = []
        
        for pattern in self.date_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    if isinstance(match, tuple):
                        year = int(match[0])
                        month = int(match[1]) if len(match) > 1 and match[1] else 1
                        day = int(match[2]) if len(match) > 2 and match[2] else 1
                        dates.append(date(year, month, day))
                    else:
                        year = int(match)
                        dates.append(date(year, 1, 1))
                except (ValueError, IndexError):
                    continue
        
        return dates[:2] if dates else []
    
    def _extract_company(self, line: str) -> str:
        """提取公司名称"""
        # 简单启发式：取日期之后的第一个词组
        parts = line.split()
        if len(parts) > 0:
            return parts[0]
        return ''
    
    def _extract_title(self, line: str) -> str:
        """提取职位名称"""
        # 常见职位关键词
        title_keywords = ['工程师', '经理', '总监', '专家', '架构师', 'Engineer', 'Manager', 'Director', 'Architect']
        for keyword in title_keywords:
            if keyword in line:
                # 提取包含该关键词的词组
                idx = line.find(keyword)
                start = max(0, idx - 20)
                end = min(len(line), idx + len(keyword) + 10)
                return line[start:end].strip()
        return ''
    
    def _extract_project_name(self, line: str) -> str:
        """提取项目名称"""
        # 去除日期和特殊符号后的内容
        cleaned = re.sub(r'\d{4}[年\-/.]?\d{0,2}[月\-/.]?', '', line)
        cleaned = re.sub(r'[：:、，,]', ' ', cleaned)
        return cleaned.strip()[:100]
    
    def _extract_role(self, line: str) -> str:
        """提取项目角色"""
        role_keywords = ['负责', '担任', '作为', '角色']
        for keyword in role_keywords:
            if keyword in line:
                idx = line.find(keyword)
                return line[idx:idx+30].strip()
        return ''
    
    def _extract_school(self, line: str) -> str:
        """提取学校名称"""
        school_keywords = ['大学', '学院', 'University', 'College', 'Institute']
        for keyword in school_keywords:
            if keyword in line:
                idx = line.find(keyword)
                start = max(0, idx - 20)
                end = idx + len(keyword)
                return line[start:end].strip()
        return ''
    
    def _extract_degree(self, line: str) -> str:
        """提取学位"""
        degrees = ['博士', '硕士', '本科', '学士', 'PhD', 'Master', 'Bachelor', 'MBA']
        for degree in degrees:
            if degree in line:
                return degree
        return ''
    
    def _extract_major(self, line: str) -> str:
        """提取专业"""
        # 简单提取：学位后面的内容可能是专业
        degree = self._extract_degree(line)
        if degree and degree in line:
            idx = line.find(degree)
            major_text = line[idx + len(degree):].strip()
            # 取前面的部分作为专业
            return major_text.split()[0] if major_text else ''
        return ''
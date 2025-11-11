"""
创建示例候选人数据
用于测试和演示系统功能
"""
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from models import Candidate, Experience, Education, Project, SkillRecency
from services.indexing_service import IndexingService
from datetime import date, datetime
import sys

# 示例候选人数据
SAMPLE_CANDIDATES = [
    {
        "name": "张伟",
        "email": "zhangwei@example.com",
        "phone": "13800138001",
        "location": "北京",
        "years_experience": 5,
        "current_title": "高级 Python 工程师",
        "current_company": "字节跳动",
        "skills": ["Python", "FastAPI", "Django", "PostgreSQL", "Redis", "Docker", "Kubernetes"],
        "education_level": "本科",
        "experiences": [
            {
                "company": "字节跳动",
                "title": "高级 Python 工程师",
                "start_date": date(2021, 6, 1),
                "end_date": None,
                "skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "Kubernetes"],
                "description": "负责推荐系统后端开发，使用 FastAPI 构建高性能 API 服务，日均处理 1000 万次请求"
            },
            {
                "company": "美团",
                "title": "Python 工程师",
                "start_date": date(2019, 7, 1),
                "end_date": date(2021, 5, 31),
                "skills": ["Python", "Django", "MySQL", "Redis"],
                "description": "参与外卖配送系统开发，负责订单处理模块"
            }
        ],
        "education": [
            {
                "school": "北京大学",
                "degree": "本科",
                "major": "计算机科学与技术",
                "start_date": date(2015, 9, 1),
                "end_date": date(2019, 6, 30)
            }
        ]
    },
    {
        "name": "李娜",
        "email": "lina@example.com",
        "phone": "13900139002",
        "location": "上海",
        "years_experience": 7,
        "current_title": "资深后端架构师",
        "current_company": "阿里巴巴",
        "skills": ["Java", "Spring", "MySQL", "Redis", "Elasticsearch", "Kafka", "微服务"],
        "education_level": "硕士",
        "experiences": [
            {
                "company": "阿里巴巴",
                "title": "资深后端架构师",
                "start_date": date(2020, 3, 1),
                "end_date": None,
                "skills": ["Java", "Spring", "Elasticsearch", "Kafka", "微服务"],
                "description": "负责电商搜索系统架构设计，支撑日均数亿次查询"
            },
            {
                "company": "腾讯",
                "title": "高级 Java 工程师",
                "start_date": date(2017, 7, 1),
                "end_date": date(2020, 2, 28),
                "skills": ["Java", "Spring", "MySQL", "Redis"],
                "description": "开发微信支付后端系统"
            }
        ],
        "education": [
            {
                "school": "清华大学",
                "degree": "硕士",
                "major": "软件工程",
                "start_date": date(2015, 9, 1),
                "end_date": date(2017, 6, 30)
            }
        ]
    },
    {
        "name": "王强",
        "email": "wangqiang@example.com",
        "phone": "13700137003",
        "location": "深圳",
        "years_experience": 4,
        "current_title": "全栈工程师",
        "current_company": "腾讯",
        "skills": ["JavaScript", "TypeScript", "React", "Vue", "Node.js", "Python", "MongoDB"],
        "education_level": "本科",
        "experiences": [
            {
                "company": "腾讯",
                "title": "全栈工程师",
                "start_date": date(2022, 1, 1),
                "end_date": None,
                "skills": ["React", "Node.js", "MongoDB", "TypeScript"],
                "description": "负责企业微信前后端开发"
            },
            {
                "company": "小米",
                "title": "前端工程师",
                "start_date": date(2020, 7, 1),
                "end_date": date(2021, 12, 31),
                "skills": ["Vue", "JavaScript", "Python"],
                "description": "开发小米商城前端页面"
            }
        ],
        "education": [
            {
                "school": "浙江大学",
                "degree": "本科",
                "major": "软件工程",
                "start_date": date(2016, 9, 1),
                "end_date": date(2020, 6, 30)
            }
        ]
    },
    {
        "name": "刘芳",
        "email": "liufang@example.com",
        "phone": "13600136004",
        "location": "杭州",
        "years_experience": 6,
        "current_title": "算法工程师",
        "current_company": "阿里巴巴",
        "skills": ["Python", "TensorFlow", "PyTorch", "NLP", "推荐系统", "Spark"],
        "education_level": "硕士",
        "experiences": [
            {
                "company": "阿里巴巴",
                "title": "算法工程师",
                "start_date": date(2020, 8, 1),
                "end_date": None,
                "skills": ["Python", "TensorFlow", "NLP", "推荐系统"],
                "description": "负责淘宝推荐算法优化，CTR 提升 15%"
            },
            {
                "company": "百度",
                "title": "NLP 工程师",
                "start_date": date(2018, 7, 1),
                "end_date": date(2020, 7, 31),
                "skills": ["Python", "PyTorch", "NLP"],
                "description": "开发智能客服对话系统"
            }
        ],
        "education": [
            {
                "school": "中国科学技术大学",
                "degree": "硕士",
                "major": "人工智能",
                "start_date": date(2016, 9, 1),
                "end_date": date(2018, 6, 30)
            }
        ]
    },
    {
        "name": "陈明",
        "email": "chenming@example.com",
        "phone": "13500135005",
        "location": "北京",
        "years_experience": 3,
        "current_title": "数据工程师",
        "current_company": "京东",
        "skills": ["Python", "Spark", "Hadoop", "Flink", "Kafka", "Hive"],
        "education_level": "本科",
        "experiences": [
            {
                "company": "京东",
                "title": "数据工程师",
                "start_date": date(2021, 7, 1),
                "end_date": None,
                "skills": ["Python", "Spark", "Flink", "Kafka"],
                "description": "构建实时数据处理平台，支撑业务分析"
            }
        ],
        "education": [
            {
                "school": "上海交通大学",
                "degree": "本科",
                "major": "数据科学",
                "start_date": date(2017, 9, 1),
                "end_date": date(2021, 6, 30)
            }
        ]
    }
]


def create_sample_data():
    """创建示例数据"""
    db = SessionLocal()
    
    try:
        print("开始创建示例候选人数据...")
        
        created_count = 0
        
        for candidate_data in SAMPLE_CANDIDATES:
            # 检查是否已存在
            existing = db.query(Candidate).filter(
                Candidate.email == candidate_data["email"]
            ).first()
            
            if existing:
                print(f"  跳过 {candidate_data['name']} (已存在)")
                continue
            
            # 创建候选人
            candidate = Candidate(
                name=candidate_data["name"],
                email=candidate_data["email"],
                phone=candidate_data["phone"],
                location=candidate_data["location"],
                years_experience=candidate_data["years_experience"],
                current_title=candidate_data["current_title"],
                current_company=candidate_data["current_company"],
                skills=candidate_data["skills"],
                education_level=candidate_data["education_level"],
                source="sample_data",
                status="active"
            )
            db.add(candidate)
            db.flush()
            
            # 创建工作经历
            for exp_data in candidate_data.get("experiences", []):
                experience = Experience(
                    candidate_id=candidate.id,
                    company=exp_data["company"],
                    title=exp_data["title"],
                    start_date=exp_data["start_date"],
                    end_date=exp_data.get("end_date"),
                    skills=exp_data["skills"],
                    description=exp_data["description"]
                )
                db.add(experience)
                
                # 创建技能新鲜度记录
                if exp_data.get("end_date"):
                    for skill in exp_data["skills"]:
                        skill_rec = SkillRecency(
                            candidate_id=candidate.id,
                            skill=skill,
                            last_used_date=exp_data["end_date"],
                            source="experience"
                        )
                        db.add(skill_rec)
            
            # 创建教育经历
            for edu_data in candidate_data.get("education", []):
                education = Education(
                    candidate_id=candidate.id,
                    school=edu_data["school"],
                    degree=edu_data["degree"],
                    major=edu_data["major"],
                    start_date=edu_data["start_date"],
                    end_date=edu_data["end_date"]
                )
                db.add(education)
            
            db.commit()
            print(f"  ✓ 创建候选人: {candidate_data['name']}")
            
            # 创建索引
            print(f"    建立索引...")
            indexing_service = IndexingService(db)
            if indexing_service.index_candidate(candidate.id, force=True):
                print(f"    ✓ 索引创建成功")
            else:
                print(f"    ✗ 索引创建失败")
            
            created_count += 1
        
        print(f"\n✅ 成功创建 {created_count} 个候选人")
        
    except Exception as e:
        print(f"\n❌ 创建失败: {str(e)}")
        db.rollback()
        sys.exit(1)
    
    finally:
        db.close()


if __name__ == "__main__":
    create_sample_data()
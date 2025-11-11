-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 候选人表（身份与状态）
CREATE TABLE IF NOT EXISTS candidates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    location VARCHAR(100),
    years_experience INTEGER,
    current_title VARCHAR(200),
    current_company VARCHAR(200),
    skills TEXT[], -- 技能数组
    education_level VARCHAR(50),
    source VARCHAR(100), -- 简历来源
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 简历表（原文引用）
CREATE TABLE IF NOT EXISTS resumes (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    file_uri VARCHAR(500) NOT NULL, -- 对象存储路径
    file_type VARCHAR(20),
    text_content TEXT, -- 提取的文本内容
    text_hash VARCHAR(64), -- SHA256 哈希用于判重
    parsed_data JSONB, -- 解析后的结构化数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(text_hash)
);

-- 工作经历表
CREATE TABLE IF NOT EXISTS experiences (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    company VARCHAR(200) NOT NULL,
    title VARCHAR(200) NOT NULL,
    start_date DATE,
    end_date DATE,
    skills TEXT[], -- 该段经历中使用的技能
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 项目经历表
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    experience_id INTEGER REFERENCES experiences(id) ON DELETE SET NULL,
    project_name VARCHAR(200),
    role VARCHAR(100),
    start_date DATE,
    end_date DATE,
    skills TEXT[],
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 教育经历表
CREATE TABLE IF NOT EXISTS education (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    school VARCHAR(200),
    degree VARCHAR(100),
    major VARCHAR(200),
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引视图（用于检索）
CREATE TABLE IF NOT EXISTS candidate_index (
    candidate_id INTEGER PRIMARY KEY REFERENCES candidates(id) ON DELETE CASCADE,
    lexical_tsv TSVECTOR, -- 全文搜索向量
    embedding vector(1536), -- OpenAI embedding 维度
    filters_json JSONB, -- 过滤字段快照 {location, years, education, etc.}
    features_json JSONB, -- 特征摘要 {key_skills, recent_companies, etc.}
    embedding_version INTEGER DEFAULT 1,
    index_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 合并谱系表（可追溯的合并历史）
CREATE TABLE IF NOT EXISTS merge_lineage (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    from_resume_id INTEGER REFERENCES resumes(id) ON DELETE SET NULL,
    merge_rule VARCHAR(100), -- 合并规则：new_priority, source_priority, non_empty_priority
    field_name VARCHAR(100), -- 被合并的字段
    old_value TEXT,
    new_value TEXT,
    decided_by VARCHAR(100) DEFAULT 'system', -- system 或 user_id
    decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 审计日志表
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50), -- candidate, resume, etc.
    entity_id INTEGER,
    action VARCHAR(50), -- create, update, delete, merge
    changes JSONB,
    performed_by VARCHAR(100),
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 技能最后使用时间表（用于新鲜度计算）
CREATE TABLE IF NOT EXISTS skill_recency (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    skill VARCHAR(200),
    last_used_date DATE,
    source VARCHAR(100), -- experience, project
    UNIQUE(candidate_id, skill)
);

-- 创建索引以优化查询性能

-- 候选人查询索引
CREATE INDEX idx_candidates_email ON candidates(email);
CREATE INDEX idx_candidates_phone ON candidates(phone);
CREATE INDEX idx_candidates_location ON candidates(location);
CREATE INDEX idx_candidates_status ON candidates(status);
CREATE INDEX idx_candidates_updated_at ON candidates(updated_at DESC);

-- 简历判重索引
CREATE INDEX idx_resumes_text_hash ON resumes(text_hash);
CREATE INDEX idx_resumes_candidate_id ON resumes(candidate_id);

-- 经历查询索引
CREATE INDEX idx_experiences_candidate_id ON experiences(candidate_id);
CREATE INDEX idx_experiences_end_date ON experiences(end_date DESC NULLS FIRST);
CREATE INDEX idx_projects_candidate_id ON projects(candidate_id);
CREATE INDEX idx_education_candidate_id ON education(candidate_id);

-- 全文搜索索引
CREATE INDEX idx_candidate_index_lexical ON candidate_index USING GIN(lexical_tsv);

-- 向量相似度搜索索引（HNSW）
CREATE INDEX idx_candidate_index_embedding ON candidate_index USING hnsw (embedding vector_cosine_ops);

-- JSONB 字段索引
CREATE INDEX idx_candidate_index_filters ON candidate_index USING GIN(filters_json);
CREATE INDEX idx_resumes_parsed_data ON resumes USING GIN(parsed_data);

-- 合并谱系查询索引
CREATE INDEX idx_merge_lineage_candidate_id ON merge_lineage(candidate_id);
CREATE INDEX idx_merge_lineage_from_resume_id ON merge_lineage(from_resume_id);

-- 审计日志查询索引
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_performed_at ON audit_log(performed_at DESC);

-- 技能新鲜度索引
CREATE INDEX idx_skill_recency_candidate_id ON skill_recency(candidate_id);
CREATE INDEX idx_skill_recency_skill ON skill_recency(skill);

-- 创建更新时间戳触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为候选人表添加更新时间戳触发器
CREATE TRIGGER update_candidates_updated_at
    BEFORE UPDATE ON candidates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 创建全文搜索更新函数（支持中英文）
CREATE OR REPLACE FUNCTION update_candidate_lexical_tsv()
RETURNS TRIGGER AS $$
BEGIN
    -- 合并候选人信息、经历、项目等文本用于全文搜索
    NEW.lexical_tsv := to_tsvector('simple', 
        COALESCE((SELECT name || ' ' || current_title || ' ' || current_company || ' ' || array_to_string(skills, ' ')
         FROM candidates WHERE id = NEW.candidate_id), '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为索引表添加全文搜索触发器
CREATE TRIGGER update_candidate_index_lexical
    BEFORE INSERT OR UPDATE ON candidate_index
    FOR EACH ROW
    EXECUTE FUNCTION update_candidate_lexical_tsv();

-- 创建视图：候选人完整信息
CREATE OR REPLACE VIEW candidate_full_view AS
SELECT 
    c.*,
    ci.embedding,
    ci.filters_json,
    ci.features_json,
    ci.index_updated_at,
    array_agg(DISTINCT e.company) FILTER (WHERE e.company IS NOT NULL) as companies,
    array_agg(DISTINCT e.title) FILTER (WHERE e.title IS NOT NULL) as titles,
    COUNT(DISTINCT r.id) as resume_count,
    MAX(e.end_date) as last_work_date
FROM candidates c
LEFT JOIN candidate_index ci ON c.id = ci.candidate_id
LEFT JOIN experiences e ON c.id = e.candidate_id
LEFT JOIN resumes r ON c.id = r.candidate_id
GROUP BY c.id, ci.embedding, ci.filters_json, ci.features_json, ci.index_updated_at;

COMMENT ON TABLE candidates IS '候选人基本信息表';
COMMENT ON TABLE resumes IS '简历原文存储表';
COMMENT ON TABLE experiences IS '工作经历表';
COMMENT ON TABLE projects IS '项目经历表';
COMMENT ON TABLE education IS '教育经历表';
COMMENT ON TABLE candidate_index IS '检索索引表（全文+向量）';
COMMENT ON TABLE merge_lineage IS '候选人合并谱系追踪表';
COMMENT ON TABLE audit_log IS '操作审计日志表';
COMMENT ON TABLE skill_recency IS '技能最后使用时间表（用于新鲜度评分）';
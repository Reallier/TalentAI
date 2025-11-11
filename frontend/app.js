// API 基础 URL
const API_BASE_URL = 'http://localhost:8000';

// 切换标签页
function switchTab(tabName) {
    // 隐藏所有标签内容
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.remove('active');
    });
    
    // 移除所有标签的激活状态
    document.querySelectorAll('.tab').forEach(el => {
        el.classList.remove('active');
    });
    
    // 显示选中的标签内容
    document.getElementById(tabName).classList.add('active');
    
    // 激活对应的标签按钮
    event.target.classList.add('active');
    
    // 如果切换到统计页面，加载统计数据
    if (tabName === 'stats') {
        loadStats();
    }
}

// JD 匹配候选人
async function matchCandidates() {
    const jdText = document.getElementById('jd-input').value.trim();
    
    if (!jdText) {
        showMessage('请输入职位描述', 'error', 'match-results');
        return;
    }
    
    const btnText = document.getElementById('match-btn-text');
    btnText.innerHTML = '<span class="loading"></span>匹配中...';
    
    // 构建请求
    const request = {
        jd: jdText,
        filters: {},
        top_k: parseInt(document.getElementById('filter-topk').value) || 20,
        explain: true
    };
    
    // 添加过滤条件
    const location = document.getElementById('filter-location').value.trim();
    if (location) {
        request.filters.location = location;
    }
    
    const minYears = document.getElementById('filter-min-years').value;
    if (minYears) {
        request.filters.min_years = parseInt(minYears);
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/match`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(request)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        displayMatchResults(data);
    } catch (error) {
        showMessage(`匹配失败: ${error.message}`, 'error', 'match-results');
    } finally {
        btnText.textContent = '开始匹配';
    }
}

// 显示匹配结果
function displayMatchResults(data) {
    const container = document.getElementById('match-results');
    
    if (!data.matches || data.matches.length === 0) {
        container.innerHTML = '<div class="message">未找到匹配的候选人</div>';
        return;
    }
    
    let html = `<div class="section"><div class="section-title">找到 ${data.total} 个匹配候选人</div>`;
    
    data.matches.forEach((match, index) => {
        html += `
            <div class="candidate-card" onclick="toggleCandidateDetail(${index})">
                <div class="candidate-header">
                    <div>
                        <div class="candidate-name">${match.name || '未知'}</div>
                        <div class="candidate-info">
                            <span>📍 ${match.location || '未知'}</span>
                            <span>💼 ${match.current_title || '未知'} @ ${match.current_company || '未知'}</span>
                            <span>⏱️ ${match.years_experience || '?'} 年经验</span>
                        </div>
                    </div>
                    <div class="score">${(match.score * 100).toFixed(1)}</div>
                </div>
                
                <div class="score-breakdown">
                    <div class="score-item">向量: ${(match.score_breakdown.vector_sim * 100).toFixed(0)}%</div>
                    <div class="score-item">关键词: ${(match.score_breakdown.lexical * 100).toFixed(0)}%</div>
                    <div class="score-item">技能: ${(match.score_breakdown.skill_coverage * 100).toFixed(0)}%</div>
                    <div class="score-item">新鲜度: ${(match.score_breakdown.recency * 100).toFixed(0)}%</div>
                </div>
                
                <div class="skills">
                    ${match.matched_skills.map(skill => 
                        `<span class="skill-tag matched">✓ ${skill}</span>`
                    ).join('')}
                    ${match.missing_skills.slice(0, 3).map(skill => 
                        `<span class="skill-tag missing">✗ ${skill}</span>`
                    ).join('')}
                </div>
                
                <div id="detail-${index}" style="display: none;">
                    ${match.evidence && match.evidence.length > 0 ? `
                        <div class="evidence">
                            <strong>匹配证据：</strong>
                            ${match.evidence.map(ev => `
                                <div class="evidence-item">
                                    <div class="evidence-skill">• ${ev.skill}</div>
                                    <div class="evidence-snippet">"${ev.snippet}"</div>
                                    ${ev.period ? `<div style="font-size: 12px; color: #95a5a6; margin-top: 4px;">时间: ${ev.period}</div>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// 切换候选人详情显示
function toggleCandidateDetail(index) {
    const detail = document.getElementById(`detail-${index}`);
    if (detail.style.display === 'none') {
        detail.style.display = 'block';
    } else {
        detail.style.display = 'none';
    }
}

// 上传简历
async function uploadResume() {
    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0];
    
    if (!file) return;
    
    const messageDiv = document.getElementById('upload-message');
    messageDiv.innerHTML = '<div class="message"><span class="loading"></span>正在上传和处理简历...</div>';
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source', 'web_upload');
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/candidates/ingest`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            messageDiv.innerHTML = `
                <div class="message success">
                    ✓ ${data.message}<br>
                    候选人ID: ${data.candidate_id}<br>
                    ${data.is_new ? '已创建新候选人' : '已合并到现有候选人'}
                </div>
            `;
        } else {
            messageDiv.innerHTML = `<div class="message error">✗ ${data.message}</div>`;
        }
    } catch (error) {
        messageDiv.innerHTML = `<div class="message error">✗ 上传失败: ${error.message}</div>`;
    } finally {
        fileInput.value = '';
    }
}

// 搜索候选人
async function searchCandidates() {
    const query = document.getElementById('search-input').value.trim();
    
    if (!query) {
        showMessage('请输入搜索关键词', 'error', 'search-results');
        return;
    }
    
    const container = document.getElementById('search-results');
    container.innerHTML = '<div class="message"><span class="loading"></span>搜索中...</div>';
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/search?q=${encodeURIComponent(query)}&top_k=20`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        displaySearchResults(data);
    } catch (error) {
        showMessage(`搜索失败: ${error.message}`, 'error', 'search-results');
    }
}

// 显示搜索结果
function displaySearchResults(data) {
    const container = document.getElementById('search-results');
    
    if (!data.results || data.results.length === 0) {
        container.innerHTML = '<div class="message">未找到匹配的候选人</div>';
        return;
    }
    
    let html = `<div class="section"><div class="section-title">找到 ${data.total} 个候选人</div>`;
    
    data.results.forEach(result => {
        html += `
            <div class="candidate-card">
                <div class="candidate-header">
                    <div>
                        <div class="candidate-name">${result.name || '未知'}</div>
                        <div class="candidate-info">
                            <span>💼 ${result.current_title || '未知'} @ ${result.current_company || '未知'}</span>
                        </div>
                    </div>
                    <div class="score">${(result.score * 10).toFixed(1)}</div>
                </div>
                
                ${result.snippet ? `
                    <div style="margin-top: 12px; padding: 8px; background: #f8f9fa; border-radius: 4px; font-size: 13px;">
                        ${result.snippet}
                    </div>
                ` : ''}
                
                <div class="skills">
                    ${result.skills.slice(0, 10).map(skill => 
                        `<span class="skill-tag">${skill}</span>`
                    ).join('')}
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// 加载统计数据
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        document.getElementById('stat-total').textContent = data.total_candidates || 0;
        document.getElementById('stat-active').textContent = data.active_candidates || 0;
        document.getElementById('stat-resumes').textContent = data.total_resumes || 0;
    } catch (error) {
        console.error('加载统计失败:', error);
    }
}

// 显示消息
function showMessage(message, type, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = `<div class="message ${type}">${message}</div>`;
}

// 拖拽上传
const uploadArea = document.getElementById('upload-area');

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        const fileInput = document.getElementById('file-input');
        fileInput.files = files;
        uploadResume();
    }
});

// 页面加载完成后加载统计数据
window.addEventListener('load', () => {
    // 可以在这里做初始化
    console.log('TalentAI 前端已加载');
});
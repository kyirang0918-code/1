document.addEventListener('DOMContentLoaded', () => {
    const summaryEl = document.getElementById('summary-text');
    const updateDateEl = document.getElementById('update-date');
    const grid = document.getElementById('trends-grid');

    const sentimentMap = {
        hot:      { emoji: '🔥', label: '지금 난리남' },
        growing:  { emoji: '📈', label: '상승세' },
        new:      { emoji: '✨', label: '신상' },
        positive: { emoji: '👍', label: '호평' }
    };

    try {
        // trendData가 로드되지 않았을 때를 대비한 안전 장치
        const data = typeof trendData !== 'undefined' ? trendData : {};

        if (data.error) {
            summaryEl.textContent = `오류: ${data.error}`;
            return;
        }

        if (updateDateEl) updateDateEl.textContent = data.updated_at || '';
        if (summaryEl) summaryEl.textContent = data.summary || '';

        grid.innerHTML = '';

        (data.trends || []).forEach((trend, index) => {
            const s = sentimentMap[trend.sentiment] || { emoji: '🍽️', label: trend.sentiment };
            const keywordsHTML = (trend.keywords || [])
                .map(kw => `<span class="keyword">#${kw}</span>`)
                .join('');

            // 네이버 검색량 뱃지 추가
            let naverBadge = '';
            if (trend.naver_trend) {
                const arrow = trend.naver_trend.is_rising ? '▲ 네이버 검색 상승' : '▽ 네이버 검색 감소';
                const color = trend.naver_trend.is_rising ? '#B3E2A7' : '#FFD6D6';
                naverBadge = `<span class="sentiment" style="background:${color};">${arrow}</span>`;
            }
            let verifiedBadge = '';
            if (trend.cross_verified) {
                verifiedBadge = `<span class="sentiment" style="background:#D4EDFF; margin-left:8px;">✅ 교차검증 완료</span>`;
            }

            const card = document.createElement('div');
            card.className = `trend-card card-${index + 1}`;
            
            // source_link 또는 source_video 등 데이터 변수명 호환성 처리
            const linkUrl = trend.source_link || trend.source_video || '#';
            const linkName = trend.source_name || '출처';

            card.innerHTML = `
                <div class="trend-number">${index + 1}</div>
                <div class="card-content">
                    <div class="trend-header">
                        <span class="sentiment ${trend.sentiment}">${s.emoji} ${s.label}</span>
                        ${naverBadge}
                        ${verifiedBadge}
                    </div>
                    <h3 class="trend-title">${trend.title}</h3>
                    <p class="trend-desc">${trend.description}</p>
                    <div class="keywords">${keywordsHTML}</div>
                    <a href="${linkUrl}" class="source-btn" target="_blank">${linkName} 확인하기</a>
                </div>
            `;
            grid.appendChild(card);
        });

    } catch (error) {
        console.error('Error loading trend data:', error);
        if (summaryEl) summaryEl.textContent = '트렌드 데이터를 불러오는 데 실패했습니다.';
    }
});

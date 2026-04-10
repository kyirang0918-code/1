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
        const data = trendData;

        if (data.error) {
            summaryEl.textContent = `오류: ${data.error}`;
            return;
        }

        if (updateDateEl) updateDateEl.textContent = data.updated_at || '';
        if (summaryEl) summaryEl.textContent = data.summary || '';

        grid.innerHTML = '';

        data.trends.forEach((trend, index) => {
            const s = sentimentMap[trend.sentiment] || { emoji: '🍽️', label: trend.sentiment };
            const keywordsHTML = (trend.keywords || [])
                .map(kw => `<span class="keyword">#${kw}</span>`)
                .join('');

            let naverBadge = '';
            if (trend.naver_trend) {
                const arrow = trend.naver_trend.is_rising ? '▲ 네이버 검색 상승 중' : '▽ 네이버 검색 감소세';
                const color = trend.naver_trend.is_rising ? '#B3E2A7' : '#FFD6D6';
                naverBadge = `<span class="sentiment" style="background:${color}; margin-left:8px;">${arrow}</span>`;
            }

            const card = document.createElement('div');
            card.className = `trend-card card-${index + 1}`;
            
            card.innerHTML = `
                <div class="trend-number">${index + 1}</div>
                <div class="card-content">
                    <div class="trend-header">
                        <span class="sentiment ${trend.sentiment}">${s.emoji} ${s.label}</span>
                        ${naverBadge}
                    </div>
                    <h3 class="trend-title">${trend.title}</h3>
                    <p class="trend-desc">${trend.description}</p>
                    <div class="keywords">${keywordsHTML}</div>
                    <a href="${trend.source_link}" class="source-btn" target="_blank">${trend.source_name} 확인하기</a>
                </div>
            `;
            grid.appendChild(card);
        });

    } catch (error) {
        console.error('Error loading trend data:', error);
        if (summaryEl) summaryEl.textContent = '트렌드 데이터를 불러오는 데 실패했습니다.';
    }
});

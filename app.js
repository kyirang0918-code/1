document.addEventListener('DOMContentLoaded', async () => {
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
            if (summaryEl) summaryEl.textContent = `오류: ${data.error}`;
            return;
        }

        if (updateDateEl) updateDateEl.textContent = data.updated_at || '';
        if (summaryEl) summaryEl.textContent = data.summary || '';

        if (grid) grid.innerHTML = '';

        (data.trends || []).forEach((trend, index) => {
            const s = sentimentMap[trend.sentiment] || { emoji: '💡', label: trend.sentiment };
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

            const card = document.createElement('div');
            card.className = `trend-card card-${index + 1}`;
            
            // source_link 호환성 처리
            const linkUrl = trend.source_link || trend.source_video || '#';
            const linkName = trend.source_name || '출처';

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
                    <a href="${linkUrl}" class="source-btn" target="_blank">${linkName} 확인하기</a>
                </div>
            `;
            if (grid) grid.appendChild(card);
        });

    } catch (error) {
        console.error('Error loading trend data:', error);
        if (summaryEl) summaryEl.textContent = '트렌드 데이터를 불러오는 데 실패했습니다.';
    }

    // 🔥 여기서부터 불꽃 파티클 버튼 애니메이션 및 영구 카운트(Firebase DB) 로직입니다 🔥
    const fireBtn = document.getElementById('fire-btn');
    if (!fireBtn) return;

    let localCount = 0;
    fireBtn.textContent = `도움되었다면 🔥를 눌러주세요 (...)`;

    // 1. 화려하게 터지는 폭죽 애니메이션 함수
    const triggerParticle = (button) => {
        const container = button.parentElement;
        
        // 한 번 클릭할 때마다 8~12개의 파티클이 터지도록 개수 증가
        const particleCount = Math.floor(Math.random() * 5) + 8;
        const emojis = ['🔥', '🔥', '🔥', '✨', '💥', '🧡']; // 🧡 이모지도 슬쩍 추가

        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            
            particle.textContent = emojis[Math.floor(Math.random() * emojis.length)];
            
            // 💡 문제 해결 핵심: 기존 CSS 파일에 남아있는 소심한 애니메이션 강제 무력화
            particle.style.animation = 'none';
            
            // JS 애니메이션 전용 스타일 세팅
            particle.style.position = 'absolute';
            particle.style.left = `calc(50% - 15px)`;
            particle.style.top = `10px`;
            particle.style.pointerEvents = 'none';
            particle.style.zIndex = '5';
            particle.style.userSelect = 'none';
            particle.style.fontSize = '1.8rem'; // 파티클 크기 확대
            
            container.appendChild(particle);

            // X축: 좌우로 더 넓게 퍼짐 (-150px ~ +150px)
            const tx = (Math.random() - 0.5) * 300;
            // Y축: 위로 더 높게 솟구침 (-80px ~ -220px)
            const ty = (Math.random() * -140) - 80;
            // 랜덤 회전각 (-90도 ~ +90도)
            const rot = (Math.random() - 0.5) * 180;
            // 랜덤 최종 크기 (0.8배 ~ 2.2배)
            const endScale = Math.random() * 1.4 + 0.8;
            
            const duration = Math.random() * 600 + 600; // 0.6초 ~ 1.2초의 랜덤 지속시간

            // 최신 Web Animations API를 사용해 폭죽 궤적 그리기
            particle.animate([
                { transform: 'translate(0, 0) scale(0.5) rotate(0deg)', opacity: 1 },
                { transform: `translate(${tx}px, ${ty}px) scale(${endScale}) rotate(${rot}deg)`, opacity: 0 }
            ], {
                duration: duration,
                easing: 'cubic-bezier(0, 0.9, 0.5, 1)', // 초반에 확 터지고 끝에서 천천히 사라지는 타이밍
                fill: 'forwards'
            });

            // 애니메이션이 끝나면 DOM에서 청소
            setTimeout(() => particle.remove(), duration);
        }
    };

    // 2. 회원님의 실제 Firebase 데이터베이스 연동 (실시간 누적 로직)
    let updateDbCount = null;

    try {
        // 공식 DB 모듈 로드
        const { initializeApp } = await import("https://www.gstatic.com/firebasejs/11.6.1/firebase-app.js");
        const { getFirestore, doc, onSnapshot, setDoc, updateDoc, increment, getDoc } = await import("https://www.gstatic.com/firebasejs/11.6.1/firebase-firestore.js");

        // 🔥 전달해주신 회원님만의 설정값 적용 완료! 🔥
        const firebaseConfig = {
            apiKey: "AIzaSyBOpIpRMPEj27XieFl2bzzLRtdlPlRLNZU",
            authDomain: "fnb-trend-db.firebaseapp.com",
            projectId: "fnb-trend-db",
            storageBucket: "fnb-trend-db.firebasestorage.app",
            messagingSenderId: "1092465751942",
            appId: "1:1092465751942:web:28836a7613f6ffb9a85e07",
            measurementId: "G-HK9022ZPN8"
        };

        const app = initializeApp(firebaseConfig);
        const db = getFirestore(app);

        // 데이터베이스 저장 위치 지정 (reactions 폴더 안의 fire 문서)
        const dbRef = doc(db, 'reactions', 'fire');

        // 처음 눌리는 상태면 숫자 0으로 문서 생성
        const docSnap = await getDoc(dbRef);
        if (!docSnap.exists()) {
            await setDoc(dbRef, { count: 0 });
        }

        // 모든 방문자의 클릭 수를 실시간 감지하여 화면에 반영
        onSnapshot(dbRef, (snapshot) => {
            if (snapshot.exists()) {
                localCount = snapshot.data().count || 0;
                fireBtn.textContent = `도움되었다면 🔥를 눌러주세요 (${localCount})`;
            }
        }, (error) => {
            console.error("Firestore 감지 에러:", error);
        });

        // 카운트 +1 증가 함수 세팅
        updateDbCount = async () => {
            await updateDoc(dbRef, { count: increment(1) });
        };
    } catch (e) {
        console.error("데이터베이스 초기화 에러:", e);
        fireBtn.textContent = `도움되었다면 🔥를 눌러주세요 (0)`;
    }

    // 3. 버튼 클릭 시 동작
    fireBtn.addEventListener('click', function() {
        triggerParticle(this); // 화려해진 파티클 폭발!
        
        // 클릭하자마자 화면의 숫자 먼저 1 올리기 (빠른 반응속도 체감)
        localCount++;
        this.textContent = `도움되었다면 🔥를 눌러주세요 (${localCount})`;

        // 데이터베이스에 숫자 영구 저장 전송
        if (updateDbCount) {
            updateDbCount().catch(err => console.error("카운트 업데이트 실패:", err));
        }
    });
});

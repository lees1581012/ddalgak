# 딸깍 인프라 로드맵 (ROADMAP 2)
## 분산 시스템 아키텍처 & 수익 모델 구축

---

## 개요

현재 **가족 전용**으로 운영 중인 딸깍 시스템을 **컨테이너화**하고 **인증 시스템**을 도입하여, 일부 **유료화** 모델을 적용한 서비스로 확장하는 인프라 로드맵입니다.

---

## 1. 현재 vs 목표 아키텍처

### 1.1 현재 구조 (가족 전용)

```mermaid
graph TB
    User[사용자] -->|OpenVPN| NAS[NAS<br/>192.168.1.100]
    NAS --> Web[웹 화면<br/>로컬 호스팅]

    User -->|로컬 네트워크| GPU[3090 PC<br/>192.168.1.50]
    GPU --> Python[Python 실행<br/>uvicorn 0.0.0.0:9000]

    Web -->|내부 네트워크| Python
    Python --> ComfyUI[ComfyUI<br/>localhost:8000]

    style GPU fill:#ff9999
    style NAS fill:#99ccff
```

**한계점:**
- ❌ OpenVPN 없이 외부 접근 불가
- ❌ 인증 시스템 없음
- ❌ 사용자 관리 불가
- ❌ 수익 모델 없음
- ❌ 스케일링 어려움

### 1.2 목표 구조 (Docker + 인증 + 유료)

```mermaid
graph TB
    subgraph 인터넷
        Internet[사용자들]
    end

    subgraph NAS Docker Host
        Nginx[Nginx Reverse Proxy<br/>:443]
        Auth[Auth Service<br/>JWT 인증]
        Web[Web Frontend<br/>React/Vue 빌드]
        DB[(PostgreSQL<br/>사용자 DB)]
        Redis[(Redis<br/>세션/캐시)]
        Pay[Payment Service<br/>결제 연동]
    end

    subgraph 3090 Docker Host
        GPU1[API Container 1<br/>FastAPI + CUDA]
        GPU2[API Container 2<br/>FastAPI + CUDA]
        GPU3[ComfyUI Container<br/>ComfyUI Server]
        Queue[Task Queue<br/>Celery/Redis]
    end

    subgraph 외부 서비스
        Stripe[Stripe 결제]
        OAuth[Google OAuth]
        CDN[CDN<br/>정적 파일]
    end

    Internet -->|HTTPS| Nginx
    Nginx --> Auth
    Auth --> Web
    Nginx -->|로드밸런싱| GPU1
    Nginx -->|로드밸런싱| GPU2

    GPU1 --> Queue
    GPU2 --> Queue
    Queue --> GPU3

    Auth --> DB
    Auth --> Redis
    Pay --> Stripe
    Auth --> OAuth
    Web --> CDN

    style GPU1 fill:#ffcccc
    style GPU2 fill:#ffcccc
    style GPU3 fill:#ffcccc
    style NAS fill:#ccffcc
```

---

## 2. Docker 컨테이너화

### 2.1 3090 PC Docker 구성

#### docker-compose.yml (3090 PC)

```yaml
version: '3.8'

services:
  # FastAPI 메인 서비스
  ddalgak-api:
    build:
      context: ./ddalgak
      dockerfile: Dockerfile
    container_name: ddalgak-api
    ports:
      - "9000:9000"
    environment:
      - CUDA_VISIBLE_DEVICES=0
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - REPLICATE_API_TOKEN=${REPLICATE_API_TOKEN}
      - DATABASE_URL=postgresql://user:pass@nas-host:5432/ddalgak
      - REDIS_URL=redis://nas-host:6379/0
      - JWT_SECRET=${JWT_SECRET}
      - COMFYUI_URL=http://comfyui:8000
    volumes:
      - ./ddalgak:/app
      - ./output:/app/output
      - /tmp/.X11-unix:/tmp/.X11-unix:rw
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
    networks:
      - ddalgak-network
    depends_on:
      - comfyui

  # ComfyUI 서비스
  comfyui:
    build:
      context: ./ComfyUI
      dockerfile: Dockerfile
    container_name: ddalgak-comfyui
    ports:
      - "8188:8188"  # 웹 UI
      - "8000:8000"  # API
    environment:
      - CUDA_VISIBLE_DEVICES=0
    volumes:
      - ./ComfyUI/models:/ComfyUI/models
      - ./output/comfyui:/ComfyUI/output
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
    networks:
      - ddalgak-network

  # Celery Worker (비동기 작업)
  celery-worker:
    build:
      context: ./ddalgak
      dockerfile: Dockerfile.celery
    container_name: ddalgak-celery
    environment:
      - CUDA_VISIBLE_DEVICES=0
      - DATABASE_URL=postgresql://user:pass@nas-host:5432/ddalgak
      - REDIS_URL=redis://nas-host:6379/0
      - COMFYUI_URL=http://comfyui:8000
    volumes:
      - ./ddalgak:/app
      - ./output:/app/output
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
    networks:
      - ddalgak-network
    depends_on:
      - comfyui

networks:
  ddalgak-network:
    driver: bridge
```

#### Dockerfile (3090 PC)

```dockerfile
# ddalgak/Dockerfile
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 시스템 의존성
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3-venv \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리
WORKDIR /app

# 의존성 복사
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 앱 복사
COPY . .

# 포트 노출
EXPOSE 9000

# 실행 명령
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
```

### 2.2 NAS Docker 구성

#### docker-compose.yml (NAS)

```yaml
version: '3.8'

services:
  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: ddalgak-nginx
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./web/dist:/usr/share/nginx/html:ro
    restart: unless-stopped
    networks:
      - ddalgak-network
    depends_on:
      - auth
      - web

  # 인증 서비스
  auth:
    build:
      context: ./auth-service
      dockerfile: Dockerfile
    container_name: ddalgak-auth
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/ddalgak_auth
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET=${JWT_SECRET}
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
    restart: unless-stopped
    networks:
      - ddalgak-network
    depends_on:
      - postgres
      - redis

  # PostgreSQL
  postgres:
    image: postgres:15-alpine
    container_name: ddalgak-postgres
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=ddalgak_auth
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: unless-stopped
    networks:
      - ddalgak-network

  # Redis
  redis:
    image: redis:7-alpine
    container_name: ddalgak-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped
    networks:
      - ddalgak-network

  # 결제 서비스
  payment:
    build:
      context: ./payment-service
      dockerfile: Dockerfile
    container_name: ddalgak-payment
    ports:
      - "8002:8002"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/ddalgak_payment
      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
      - STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}
    restart: unless-stopped
    networks:
      - ddalgak-network
    depends_on:
      - postgres

  # 모니터링 (Grafana + Prometheus)
  prometheus:
    image: prom/prometheus
    container_name: ddalgak-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    restart: unless-stopped
    networks:
      - ddalgak-network

  grafana:
    image: grafana/grafana
    container_name: ddalgak-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana-data:/var/lib/grafana
    restart: unless-stopped
    networks:
      - ddalgak-network

volumes:
  postgres-data:
  redis-data:
  prometheus-data:
  grafana-data:

networks:
  ddalgak-network:
    driver: bridge
```

---

## 3. 인증 시스템

### 3.1 인증 흐름

```mermaid
sequenceDiagram
    participant U as 사용자
    participant N as Nginx
    participant A as Auth Service
    participant DB as PostgreSQL
    participant R as Redis
    participant API as FastAPI

    U->>N: 1. 접속 https://ddalgak.com
    N->>A: 2. 인증 확인 요청

    alt 미인증
        A->>U: 3. 로그인 페이지 반환
        U->>A: 4. Google OAuth 클릭
        A-->>OAuth: 5. OAuth 요청
        OAuth-->>A: 6. 인증 코드
        A->>DB: 7. 사용자 정보 저장/조회
        A->>R: 8. 세션 생성
        A->>U: 9. JWT 토큰 발급 (쿠키)
    end

    U->>N: 10. API 요청 (with JWT)
    N->>A: 11. 토큰 검증
    A->>R: 12. 세션 확인
    R-->>A: 13. 유효함
    A-->>N: 14. 인증 성공
    N->>API: 15. 요청 전달
    API-->>U: 16. 응답
```

### 3.2 JWT 토큰 구조

```python
import jwt
from datetime import datetime, timedelta

# JWT 페이로드
payload = {
    "user_id": "user123",
    "email": "user@example.com",
    "tier": "free",  # free, pro, enterprise
    "quota": {
        "monthly_videos": 10,
        "used_videos": 3
    },
    "exp": datetime.utcnow() + timedelta(days=7),
    "iat": datetime.utcnow()
}

# 토큰 발급
token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

# 토큰 검증
try:
    decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    print(f"User: {decoded['user_id']}, Tier: {decoded['tier']}")
except jwt.ExpiredSignatureError:
    # 토큰 만료
    return "Token expired"
except jwt.InvalidTokenError:
    # 유효하지 않은 토큰
    return "Invalid token"
```

### 3.3 사용자 등급 시스템

| 등급 | 가격 | 월간 생성 | 4K 지원 | 상품 |
|------|------|-----------|---------|------|
| Free | ₩0 | 3개 | ❌ | 기본 기능 |
| Basic | ₩9,900 | 20개 | ❌ | 일반 사용자 |
| Pro | ₩29,000 | 100개 | ✅ | 크리에이터 |
| Studio | ₩99,000 | 무제한 | ✅ | 스튜디오/기업 |

```python
# 사용자 모델
class User(BaseModel):
    id: str
    email: str
    tier: Tier  # Enum: FREE, BASIC, PRO, STUDIO
    quota_used: int
    quota_limit: int
    created_at: datetime
    subscription_id: Optional[str]  # Stripe 결제 ID

# 할당량 확인 미들웨어
async def check_quota(request: Request):
    token = request.cookies.get("jwt_token")
    user = get_user_from_token(token)

    if user.quota_used >= user.quota_limit:
        raise HTTPException(
            403,
            f"할당량 초과. 등급: {user.tier}, 사용: {user.quota_used}/{user.quota_limit}"
        )

    return user
```

---

## 4. 네트워크 구성

### 4.1 내부 네트워크

```
[인터넷]
    ↓
[공유기] 192.168.1.1
    ↓
┌─────────────────────────────────────┐
│         내부 네트워크                │
│                                     │
│  [NAS] 192.168.1.100                 │
│    ├─ nginx:443 (HTTPS)             │
│    ├─ auth:8001                     │
│    ├─ postgres:5432                 │
│    └─ redis:6379                    │
│                                     │
│  [3090 PC] 192.168.1.50             │
│    ├─ ddalgak-api:9000              │
│    ├─ comfyui:8000                  │
│    └─ celery-worker                 │
└─────────────────────────────────────┘
```

### 4.2 외부 접속 (DNS + SSL)

```
사용자
    ↓
ddalgak.com (A 레코드)
    ↓
[DDoS 보호] Cloudflare (선택)
    ↓
[공유기] 포트 포워딩 443 → NAS:443
    ↓
[Nginx] SSL 종료
    ↓
[내부 서비스들]
```

### 4.3 Nginx 설정

```nginx
# nginx/nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream auth_service {
        server auth:8001;
    }

    upstream api_service {
        # 3090 PC의 여러 컨테이너에 로드밸런싱
        server 192.168.1.50:9000;
        # server 192.168.1.50:9001;  # 추가 컨테이너
        # server 192.168.1.51:9000;  # 추가 GPU PC
    }

    # SSL 설정
    server {
        listen 443 ssl http2;
        server_name ddalgak.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        # 정적 파일
        location /static/ {
            alias /usr/share/nginx/html/;
            expires 1y;
        }

        # API 요청 (인증 필요)
        location /api/ {
            # 인증 체크
            auth_request /auth/validate;

            # 프록시
            proxy_pass http://api_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # SSE 지원
            proxy_buffering off;
            proxy_cache off;
            proxy_set_header Connection '';
            proxy_http_version 1.1;
            chunked_transfer_encoding off;
        }

        # 인증 엔드포인트
        location /auth/ {
            proxy_pass http://auth_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        # WebSocket (ComfyUI)
        location /ws/ {
            proxy_pass http://192.168.1.50:8188;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
        }
    }

    # HTTP → HTTPS 리다이렉트
    server {
        listen 80;
        server_name ddalgak.com;
        return 301 https://$server_name$request_uri;
    }
}
```

---

## 5. 수익 모델 구현

### 5.1 Stripe 결제 연동

```python
# payment-service/main.py
import stripe
from fastapi import FastAPI, HTTPException

stripe.api_key = STRIPE_SECRET_KEY

app = FastAPI()

# 상품 정의
PRODUCTS = {
    "basic": {
        "price_id": "price_basic_monthly",
        "amount": 9900,
        "quota": 20
    },
    "pro": {
        "price_id": "price_pro_monthly",
        "amount": 29000,
        "quota": 100
    },
    "studio": {
        "price_id": "price_studio_monthly",
        "amount": 99000,
        "quota": -1  # 무제한
    }
}

@app.post("/create-checkout-session")
async def create_checkout_session(
    user_id: str,
    product_tier: str  # basic, pro, studio
):
    """Stripe 체크아웃 세션 생성"""
    product = PRODUCTS.get(product_tier)
    if not product:
        raise HTTPException(400, "Invalid product tier")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "krw",
                "product_data": {
                    "name": f"딸깍 {product_tier.upper()} 플랜",
                },
                "unit_amount": product["amount"],
            },
            "quantity": 1,
        }],
        mode="subscription",
        success_url="https://ddalgak.com/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://ddalgak.com/cancel",
        customer_email=user_id,  # 또는 customer ID
        metadata={
            "user_id": user_id,
            "tier": product_tier
        }
    )

    return {"checkout_url": session.url}

@app.post("/webhook")
async def stripe_webhook(request: Request):
    """Stripe 웹훅 (결제 완료 처리)"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(400)

    # 결제 성공 처리
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session["metadata"]["user_id"]
        tier = session["metadata"]["tier"]

        # DB 업데이트
        await update_user_tier(user_id, tier)

        # 환영 이메일
        await send_welcome_email(user_id, tier)

    return {"status": "success"}
```

### 5.2 결제 플로우

```mermaid
sequenceDiagram
    participant U as 사용자
    participant W as 웹
    participant P as Payment Service
    participant S as Stripe
    participant DB as DB

    U->>W: 1. 플랜 선택 (Pro)
    W->>P: 2. create_checkout_session
    P->>S: 3. 체크아웃 세션 생성
    S-->>P: 4. session.url 반환
    P-->>W: 5. checkout_url 전달
    W-->>U: 6. Stripe 결제 페이지로 리다이렉트

    U->>S: 7. 결제 정보 입력
    U->>S: 8. 결제 승인
    S->>P: 9. webhook 이벤트 (checkout.session.completed)
    P->>DB: 10. 사용자 등급 업데이트
    P->>U: 11. 환영 이메일

    S-->>U: 12. 성공 페이지로 리다이렉트
    U->>W: 13. 대시보드 접속
    W->>DB: 14. Pro 등급 확인
    DB-->>W: 15. Pro 플랜 정보
    W-->>U: 16. Pro 대시보드 표시
```

---

## 6. 단계별 구현 로드맵

### Phase 1: 도커화 (2주)

| 주차 | 항목 | 상세 내용 |
|------|------|-----------|
| 1주차 | 3090 PC 컨테이너화 | Dockerfile 작성, docker-compose.yml |
| 2주차 | NAS 컨테이너화 | Nginx, PostgreSQL, Redis 구성 |

### Phase 2: 인증 시스템 (3주)

| 주차 | 항목 | 상세 내용 |
|------|------|-----------|
| 3주차 | Auth Service | JWT 발급/검증, Google OAuth |
| 4주차 | 데이터베이스 | 사용자 테이블, 할당량 관리 |
| 5주차 | Nginx 연동 | Reverse Proxy, 인증 미들웨어 |

### Phase 3: 결제 시스템 (2주)

| 주차 | 항목 | 상세 내용 |
|------|------|-----------|
| 6주차 | Stripe 연동 | 체크아웃, 웹훅 |
| 7주차 | 등급 시스템 | 할당량, 기능 제한 |

### Phase 4: 모니터링 (2주)

| 주차 | 항목 | 상세 내용 |
|------|------|-----------|
| 8주차 | Prometheus | 메트릭 수집 |
| 9주차 | Grafana | 대시보드 구축 |

### Phase 5: 안정화 (1주)

| 주차 | 항목 | 상세 내용 |
|------|------|-----------|
| 10주차 | 테스트 & 배포 | 부하 테스트, 버그 수정 |

---

## 7. 배포 절차

### 7.1 초기 설정 (최초 1회)

```bash
# 1. SSL 인증서 발급 (Let's Encrypt)
sudo certbot certonly --standalone -d ddalgak.com

# 2. Docker 네트워크 생성 (NAS + 3090 PC)
docker network create ddalgak-network --driver overlay --attachable

# 3. 데이터베이스 초기화
docker-compose -f docker-compose.nas.yml up -d postgres
docker exec -it ddalgak-postgres psql -U postgres -c CREATE DATABASE ddalgak_auth;

# 4. Redis 초기화
docker-compose -f docker-compose.nas.yml up -d redis

# 5. 환경 변수 설정
cp .env.example .env
# .env 파일에 API 키, JWT_SECRET 등 입력
```

### 7.2 서비스 시작

```bash
# NAS (순서 중요)
docker-compose -f docker-compose.nas.yml up -d postgres redis
docker-compose -f docker-compose.nas.yml up -d auth payment
docker-compose -f docker-compose.nas.yml up -d nginx

# 3090 PC
docker-compose -f docker-compose.3090.yml up -d comfyui
docker-compose -f docker-compose.3090.yml up -d ddalgak-api
docker-compose -f docker-compose.3090.yml up -d celery-worker
```

### 7.3 서비스 확인

```bash
# 건강 체크
curl https://ddalgak.com/health
curl https://ddalgak.com/api/health
curl http://192.168.1.50:9000/health
curl http://192.168.1.50:8000/queue  # ComfyUI
```

---

## 8. 보안 고려사항

### 8.1 네트워크 보안

| 항목 | 조치 |
|------|------|
| 내부 통신 | VPN 외부 접속 차단 |
| API 노출 | Nginx 이외에 직접 접속 차단 |
| 데이터베이스 | 내부 네트워크만 접근 허용 |
| Redis | 비밀번호 + 내부 네트워크 |
| ComfyUI | SSH 터널 또는 VPN |

### 8.2 애플리케이션 보안

```python
# API 속도 제어 (Rate Limiting)
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/api/step1/generate")
@limiter.limit("10/hour")  # 시간당 10회
async def step1_generate(...):
    pass

# CSRF 보호
from fastapi_csrf_protect import CsrfProtect

# SQL Injection 방지
# (SQLAlchemy ORM 사용으로 자동 방지)

# XSS 방지
# (Jinja2 자동 이스케이프)
```

---

## 9. 모니터링 & 로깅

### 9.1 Prometheus 메트릭

```python
from prometheus_client import Counter, Histogram, Gauge

# 카운터
video_generated = Counter(
    "ddalgak_videos_generated_total",
    "Total videos generated",
    ["tier", "status"]
)

# 히스토그램
generation_time = Histogram(
    "ddalgak_generation_duration_seconds",
    "Video generation duration",
    ["step"]
)

# 게이지
active_users = Gauge(
    "ddalgak_active_users",
    "Currently active users"
)

# 사용 예시
@app.post("/api/step1/generate")
async def step1_generate(...):
    with generation_time.labels(step="script").time():
        result = generate_script(...)
        video_generated.labels(tier=user.tier, status="success").inc()
        return result
```

### 9.2 Grafana 대시보드

```
[실시간 모니터링]
┌─────────────────────────────────────┐
│  요청速率 (req/s)                    │
│  ████░░░░░░░░░░░░░                  │
│                                     │
│  응답 시간 (ms)                      │
│  ████████░░                         │
│                                     │
│  활성 사용자                         │
│  ████████████░░                     │
│                                     │
│  GPU 사용률                          │
│  ████████████████░ 90%              │
│                                     │
│  생성 큐                             │
│  ██ 5건 대기 중                      │
└─────────────────────────────────────┘
```

---

## 10. 재해 복구

### 10.1 백업 전략

```bash
# 데이터베이스 백업 (매일)
0 2 * * * docker exec ddalgak-postgres pg_dump -U postgres ddalgak_auth | gzip > /backup/ddalgak_$(date +\%Y\%m\%d).sql.gz

# output 폴더 백업 (매주)
0 3 * * 0 rsync -avz /output/ /backup/output_$(date +\%Y\%m\%d)/
```

### 10.2 장애 조치

| 장애 상황 | 조치 |
|-----------|------|
| 3090 PC 다운 | Docker 컨테이너 자동 재시작 |
| NAS 다운 | 예비 서버로 전환 |
| DB 장애 | Replica에서 승격 |
| ComfyUI 장애 | Replicate로 폴백 |

---

## 11. 비용 분석

### 11.1 고정 비용

| 항목 | 비용 | 비고 |
|------|------|------|
| 도메인 | ₩15,000/년 | ddalgak.com |
| SSL | 무료 | Let's Encrypt |
| 전력 | ₩20,000/월 | 3090 PC 24시간 운영 |
| 백업 저장소 | ₩5,000/월 | 클라우드 스토리지 |

### 11.2 변동 비용

| 항목 | 비용 | 비고 |
|------|------|------|
| Gemini API | ₩1,000/10만 토큰 | $0.075/1M |
| Replicate | ₩50/영상 1개 | z-image 무료 |
| Stripe 수수료 | 2.9% + ₩100/건 | 결제 대금 |

### 11.3 손익분기점

```
고정 비용: ₩40,000/월
변동 비용: ₩2,000/유저 (API)

월 10유저 × ₩9,900 = ₩99,000
- API 비용 (₩20,000)
- 수수료 (₩3,000)
= 순수익 ₩76,000/월

손익분기점: 월 5~6유저
```

---

## 12. 결론

**현재** (가족 전용, OpenVPN)
```
사용자: 가족 (3~5명)
인증: 없음
수익: ₩0
```

**목표** (Docker + 인증 + 유료)
```
사용자: 일반 사용자 (무제한)
인증: JWT + OAuth
수익: 월 ₩500,000~₩5,000,000
```

핵심 개선점:
- ✅ Docker로 스케일링 가능
- ✅ 인증 시스템으로 다중 사용자
- ✅ Stripe로 수익화
- ✅ 모니터링으로 안정성 확보

---

## 변경사항

- 2026-03-10: 초안 작성

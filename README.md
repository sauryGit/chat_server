# 실시간 채팅 애플리케이션

FastAPI WebSocket과 Firebase를 사용한 실시간 채팅 애플리케이션입니다.

## 기능

- ✅ 실시간 메시지 전송 및 수신 (WebSocket)
- ✅ Firebase Firestore를 사용한 메시지 저장
- ✅ 다중 클라이언트 지원
- ✅ 메시지 중복 방지
- ✅ Render를 통한 클라우드 배포

## 기술 스택

- **서버**: FastAPI, WebSocket, Firebase Admin SDK
- **클라이언트**: Flet (Python GUI)
- **데이터베이스**: Firebase Firestore
- **배포**: Render

## 프로젝트 구조

```
chat/
├── server.py          # FastAPI 서버 (Render 배포용)
├── client.py         # Flet 클라이언트 앱
├── requirements.txt  # Python 의존성
├── render.yaml       # Render 배포 설정
├── Procfile         # Render 프로세스 설정
├── secureKey.json    # Firebase 키 (로컬 개발용, Git 제외)
└── DEPLOY.md        # 배포 가이드
```

## 로컬 개발

### 1. 저장소 클론

```bash
git clone https://github.com/your-username/your-repo.git
cd chat
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. Firebase 설정

1. Firebase Console에서 프로젝트 생성
2. Firestore 데이터베이스 생성
3. 서비스 계정 키 다운로드
4. `secureKey.json` 파일을 프로젝트 루트에 배치

### 4. 서버 실행

```bash
python server.py
```

서버가 `http://localhost:8000`에서 실행됩니다.

### 5. 클라이언트 실행

```bash
python client.py
```

## 배포

Render를 통한 배포는 [DEPLOY.md](./DEPLOY.md)를 참조하세요.

## API 엔드포인트

### HTTP

- `POST /send` - 메시지 전송
- `GET /messages` - 메시지 목록 조회 (최신 30개)

### WebSocket

- `WS /ws` - 실시간 채팅 연결

## 환경 변수

### 서버

- `PORT`: 서버 포트 (기본값: 8000)
- `FIREBASE_KEY_JSON`: Firebase 서비스 계정 키 (JSON 문자열)

### 클라이언트

- `RENDER_SERVER_URL`: Render 서버 URL (기본값: http://localhost:8000)

## 라이선스

MIT

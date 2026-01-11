# Render 배포 가이드

이 문서는 Render를 사용하여 채팅 서버를 배포하는 방법을 설명합니다.

## 아키텍처 구조

```
Client (Flet 앱)
    ↓
Render (FastAPI 서버)
    ↓
GitHub (코드 저장소)
    ↓
Firebase (데이터베이스)
```

## 배포 단계

### 1. GitHub 저장소 준비

1. GitHub에 새 저장소를 생성합니다.
2. 로컬 프로젝트를 GitHub에 푸시합니다:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/your-username/your-repo.git
   git push -u origin main
   ```

### 2. Firebase 키 준비

1. Firebase Console에서 서비스 계정 키를 다운로드합니다.
2. `secureKey.json` 파일을 준비합니다 (로컬 개발용).

### 3. Render 배포 설정

1. [Render](https://render.com)에 로그인합니다.
2. "New +" 버튼을 클릭하고 "Web Service"를 선택합니다.
3. GitHub 저장소를 연결합니다.
4. 다음 설정을 입력합니다:

   - **Name**: `chat-server` (원하는 이름)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python server.py`
   - **Plan**: Free 또는 원하는 플랜

5. **Environment Variables** 섹션에서 다음 변수를 추가합니다:

   - `PORT`: `10000` (Render가 자동으로 할당하므로 설정하지 않아도 됩니다)
   - `FIREBASE_KEY_JSON`: Firebase 키 JSON 문자열 (전체 내용을 한 줄로)

   **중요**: `FIREBASE_KEY_JSON`은 다음과 같이 설정합니다:

   ```json
   {"type":"service_account","project_id":"your-project",...}
   ```

   전체 JSON을 한 줄로 복사하여 붙여넣습니다.

6. "Create Web Service"를 클릭합니다.

### 4. Render 서버 URL 확인

배포가 완료되면 Render 대시보드에서 서버 URL을 확인합니다:

- 예: `https://chat-server-xxxx.onrender.com`

### 5. 클라이언트 설정

클라이언트 코드에서 Render 서버 URL을 설정합니다:

**방법 1: 환경 변수 사용**

```bash
export RENDER_SERVER_URL="https://your-app-name.onrender.com"
python client.py
```

**방법 2: 코드에서 직접 수정**
`client.py` 파일에서 다음 줄을 수정:

```python
RENDER_SERVER_URL = os.getenv("RENDER_SERVER_URL", "https://your-app-name.onrender.com")
```

### 6. 자동 배포 설정

Render는 GitHub와 연동되어 자동 배포를 지원합니다:

- `main` 브랜치에 푸시하면 자동으로 재배포됩니다.
- Render 대시보드에서 자동 배포를 활성화/비활성화할 수 있습니다.

## 환경 변수 설명

### 서버 (Render)

- `PORT`: 서버 포트 (Render가 자동 할당)
- `FIREBASE_KEY_PATH`: Firebase 키 파일 경로 (기본값: `/etc/secrets/firebase-key.json`)
- `FIREBASE_KEY_JSON`: Firebase 서비스 계정 키 (JSON 문자열, Secret Files 대신 사용 가능)

### 클라이언트

- `RENDER_SERVER_URL`: Render 서버 URL (기본값: `http://localhost:8000`)

## 문제 해결

### Firebase 연결 오류

1. **Secret Files 사용 시**:

   - Secret Files에 `firebase-key.json`이 올바르게 업로드되었는지 확인
   - 파일 경로가 `/etc/secrets/firebase-key.json`인지 확인
   - `FIREBASE_KEY_PATH` 환경 변수로 다른 경로 지정 가능

2. **환경 변수 사용 시**:

   - `FIREBASE_KEY_JSON` 환경 변수가 올바르게 설정되었는지 확인
   - JSON 형식이 올바른지 확인 (특수 문자 이스케이프)
   - 전체 JSON을 한 줄로 복사했는지 확인

3. Render 로그에서 에러 메시지 확인

### WebSocket 연결 오류

1. Render 서버 URL이 올바른지 확인
2. HTTPS를 사용하는 경우 WSS 프로토콜 사용 확인
3. Render의 무료 플랜은 15분 비활성 후 슬리프 모드로 전환됩니다.

### 배포 실패

1. `requirements.txt`에 모든 의존성이 포함되어 있는지 확인
2. Python 버전 호환성 확인
3. Render 빌드 로그 확인

## 보안 주의사항

⚠️ **중요**:

- `secureKey.json` 파일은 절대 GitHub에 커밋하지 마세요!
- `.gitignore`에 `secureKey.json`이 포함되어 있는지 확인하세요.
- Firebase 키는 Render 환경 변수로만 관리하세요.

## Render 무료 플랜 제한사항

- 15분 비활성 후 슬리프 모드로 전환
- 첫 요청 시 약 30초 정도 지연될 수 있음
- 월 750시간 제한

프로덕션 환경에서는 유료 플랜 사용을 권장합니다.

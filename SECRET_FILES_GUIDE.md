# Render Secret Files 사용 가이드

Render의 Secret Files 기능을 사용하여 Firebase 키를 안전하게 관리하는 방법입니다.

## Secret Files란?

Secret Files는 Render에서 제공하는 기능으로, 민감한 파일을 안전하게 저장하고 서비스에 마운트할 수 있습니다. 환경 변수보다 파일 관리가 편리합니다.

## 설정 방법

### 1. Render 대시보드에서 설정

1. Render 대시보드에서 서비스를 선택합니다.
2. 왼쪽 메뉴에서 **"Environment"** 또는 **"Secret Files"**를 클릭합니다.
3. **"Add Secret File"** 버튼을 클릭합니다.
4. 다음 정보를 입력합니다:
   - **Name**: `firebase-key.json` (또는 원하는 이름)
   - **Contents**: `secureKey.json` 파일의 전체 내용을 복사하여 붙여넣기
5. **"Save"** 버튼을 클릭합니다.

### 2. 파일 경로 확인

Secret Files로 업로드한 파일은 자동으로 다음 경로에 마운트됩니다:
```
/etc/secrets/firebase-key.json
```

서버 코드는 이 경로를 자동으로 감지하여 사용합니다.

### 3. 다른 경로 사용하기

다른 경로를 사용하려면 환경 변수를 설정합니다:
- **Key**: `FIREBASE_KEY_PATH`
- **Value**: `/etc/secrets/your-custom-name.json`

## Secret Files vs 환경 변수

### Secret Files 사용 (권장)
✅ 장점:
- 파일 형식 그대로 사용 가능 (JSON 포맷 유지)
- 여러 줄, 특수 문자 처리 불필요
- 관리가 더 편리함
- 파일 크기 제한이 더 큼

❌ 단점:
- Render 유료 플랜에서만 사용 가능 (일부 플랜)

### 환경 변수 사용
✅ 장점:
- 모든 플랜에서 사용 가능
- 무료 플랜에서도 사용 가능

❌ 단점:
- JSON을 한 줄로 변환해야 함
- 특수 문자 이스케이프 필요
- 긴 JSON 문자열 관리가 불편함

## 우선순위

서버는 다음 순서로 Firebase 키를 찾습니다:

1. **Secret Files** (`/etc/secrets/firebase-key.json` 또는 `FIREBASE_KEY_PATH`)
2. **환경 변수** (`FIREBASE_KEY_JSON`)
3. **로컬 파일** (`secureKey.json`)

## Secret Files 사용 예시

### Render 대시보드 설정

```
Secret Files:
┌─────────────────────────┬──────────────────────────────┐
│ Name                    │ Contents                     │
├─────────────────────────┼──────────────────────────────┤
│ firebase-key.json       │ {                            │
│                         │   "type": "service_account", │
│                         │   "project_id": "...",       │
│                         │   ...                        │
│                         │ }                            │
└─────────────────────────┴──────────────────────────────┘
```

### 서버 코드에서 자동 감지

서버가 시작되면 자동으로 다음 경로를 확인합니다:
```python
# 1. Secret Files 경로 확인
/etc/secrets/firebase-key.json

# 2. 환경 변수 확인
FIREBASE_KEY_JSON

# 3. 로컬 파일 확인
secureKey.json
```

## 문제 해결

### Secret Files가 인식되지 않는 경우

1. **파일 이름 확인**: `firebase-key.json`으로 설정했는지 확인
2. **경로 확인**: `/etc/secrets/firebase-key.json` 경로에 파일이 있는지 확인
3. **환경 변수 설정**: `FIREBASE_KEY_PATH` 환경 변수로 경로 지정
4. **로그 확인**: Render 로그에서 Firebase 초기화 메시지 확인

### 파일 내용 확인

Render 대시보드에서 Secret Files의 내용을 확인할 수 있습니다:
- Environment → Secret Files → 파일 이름 클릭

## 보안 주의사항

⚠️ **중요**:
- Secret Files는 Render 대시보드에서만 관리하세요
- 파일 내용을 외부에 공유하지 마세요
- GitHub에 `secureKey.json`을 커밋하지 마세요 (`.gitignore`에 포함됨)

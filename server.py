# ... imports
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from pydantic import BaseModel
from datetime import datetime
import uvicorn
import json
import urllib.parse
from typing import Set, Optional

# 1. Firebase 초기화 (보안 키 로드)
# ... (Firebase init code remains same) ...
import os

def init_firebase():
    # ... (existing init_firebase code) ...
    # 1. Render Secret Files에서 로드 시도 (우선순위 1)
    firebase_key_path = os.getenv("FIREBASE_KEY_PATH", "/etc/secrets/firebase-key.json")
    if os.path.exists(firebase_key_path):
        cred = credentials.Certificate(firebase_key_path)
        firebase_admin.initialize_app(cred)
        print(f"Firebase 초기화 완료 (Secret Files에서 로드: {firebase_key_path})")
        return
    
    # 2. 환경 변수에서 JSON 문자열로 로드 시도 (우선순위 2)
    firebase_key_json = os.getenv("FIREBASE_KEY_JSON")
    if firebase_key_json:
        try:
            key_dict = json.loads(firebase_key_json)
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
            print("Firebase 초기화 완료 (환경 변수에서 로드)")
            return
        except json.JSONDecodeError as e:
            print(f"환경 변수 FIREBASE_KEY_JSON 파싱 실패: {e}")
            raise
    
    # 3. 로컬 개발 환경: 파일에서 로드 (우선순위 3)
    if os.path.exists("secureKey.json"):
        cred = credentials.Certificate("secureKey.json")
        firebase_admin.initialize_app(cred)
        print("Firebase 초기화 완료 (로컬 파일에서 로드)")
        return
    
    # 모든 방법 실패
    raise FileNotFoundError(
        "Firebase 키를 찾을 수 없습니다. 다음 중 하나를 설정하세요:\n"
        "1. Render Secret Files: /etc/secrets/firebase-key.json\n"
        "2. 환경 변수: FIREBASE_KEY_JSON (JSON 문자열)\n"
        "3. 로컬 파일: secureKey.json"
    )

init_firebase()
db = firestore.client()

# --- 화이트리스트 설정 ---
# 환경 변수 CHAT_WHITELIST가 설정되어 있으면 해당 닉네임만 허용
# 예: CHAT_WHITELIST="홍길동,김철수,이영희"
CHAT_WHITELIST_STR = os.getenv("CHAT_WHITELIST")
CHAT_WHITELIST = set([n.strip() for n in CHAT_WHITELIST_STR.split(",") if n.strip()]) if CHAT_WHITELIST_STR is not None else None

def is_nickname_allowed(nickname: str) -> bool:
    """닉네임이 화이트리스트에 있는지 확인"""
    if CHAT_WHITELIST is None:
        return True # 화이트리스트 설정이 없으면 모두 허용
    return nickname in CHAT_WHITELIST

# 2. FastAPI 앱 생성
app = FastAPI()

# --- 백그라운드 작업 ---
def cleanup_old_messages():
    # ... (existing cleanup_old_messages code) ...
    try:
        messages_ref = db.collection("messages")
        
        # 전체 메시지 수를 초과하는 가장 오래된 문서들을 가져옴
        # timestamp를 기준으로 오름차순 정렬
        docs_query = messages_ref.order_by("timestamp", direction=firestore.Query.ASCENDING)
        
        # 전체 문서 수를 가져오기 위해 모든 문서를 스트리밍
        all_docs = list(docs_query.stream())
        docs_count = len(all_docs)

        if docs_count > 50:
            # 삭제할 문서 수 계산
            num_to_delete = docs_count - 50
            docs_to_delete = all_docs[:num_to_delete]
            
            print(f"메시지 정리: {len(docs_to_delete)}개의 오래된 메시지를 삭제합니다.")

            # 배치(batch) 삭제
            batch = db.batch()
            for doc in docs_to_delete:
                batch.delete(doc.reference)
            batch.commit()
            print("메시지 정리 완료.")

    except Exception as e:
        print(f"백그라운드 메시지 정리 중 에러 발생: {e}")


# 3. WebSocket 연결 관리
class ConnectionManager:
    # ... (existing ConnectionManager code) ...
    def __init__(self):
        # 활성 WebSocket 연결 목록
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"클라이언트 연결됨. 현재 연결 수: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"클라이언트 연결 해제됨. 현재 연결 수: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        # 모든 연결된 클라이언트에 메시지 브로드캐스팅
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"메시지 전송 실패: {e}")
                disconnected.append(connection)
        
        # 연결이 끊어진 클라이언트 제거
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

# 4. 데이터 모델 정의 (채팅 메시지 규격)
class Message(BaseModel):
    nickname: str
    content: str

class FetchMessagesRequest(BaseModel):
    nickname: str
    after: Optional[str] = None

# [API 1] 메시지 전송 (저장) - HTTP 엔드포인트 (하위 호환성 유지)
@app.post("/send")
async def send_message(msg: Message, background_tasks: BackgroundTasks):
    # ... (existing code) ...
    # 화이트리스트 체크
    if not is_nickname_allowed(msg.nickname):
        print(f"[SECURITY_ALERT] 무단 메시지 전송 시도 - 닉네임: {msg.nickname}")
        raise HTTPException(status_code=403, detail="등록되지 않은 닉네임입니다.")

    doc_ref = db.collection("messages").document()
    doc_id = doc_ref.id
    
    # Firestore에 저장 (서버 타임스탬프 사용)
    doc_ref.set({
        "nickname": msg.nickname,
        "content": msg.content,
        "timestamp": firestore.SERVER_TIMESTAMP
    })
    
    # WebSocket으로 모든 클라이언트에 브로드캐스팅
    message_data = {
        "id": doc_id,
        "nickname": msg.nickname,
        "content": msg.content,
        "timestamp": datetime.now().isoformat()
    }
    await manager.broadcast(message_data)
    
    # 백그라운드에서 오래된 메시지 정리 작업 추가
    background_tasks.add_task(cleanup_old_messages)
    
    return {"status": "success"}

# [WebSocket] 실시간 채팅 연결
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # 헤더에서 닉네임 추출 (보안 강화)
    nickname_header = websocket.headers.get("x-nickname")
    nickname = None
    if nickname_header:
        # 헤더 값은 URL 인코딩되어 있을 수 있으므로 디코딩
        nickname = urllib.parse.unquote(nickname_header)
    
    # 헤더에 없으면 쿼리 파라미터에서 확인 (하위 호환성)
    if not nickname:
        nickname = websocket.query_params.get("nickname")

    # 닉네임 파라미터 확인 및 화이트리스트 체크
    if nickname is None:
        # 닉네임이 없으면 연결 거부 (400 Bad Request)
        await websocket.close(code=4000, reason="Nickname required")
        return
        
    if not is_nickname_allowed(nickname):
        print(f"[SECURITY_ALERT] 무단 웹소켓 연결 시도 - 닉네임: {nickname}")
        await websocket.close(code=4003, reason="Forbidden nickname")
        return

    await manager.connect(websocket)
    try:
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_text()
            message_dict = json.loads(data)
            
            # 메시지 유효성 검사
            if "nickname" not in message_dict or "content" not in message_dict:
                await websocket.send_json({"error": "잘못된 메시지 형식"})
                continue

            # 메시지 전송 시 닉네임 재검증 (변조 방지)
            if message_dict["nickname"] != nickname:
                 await websocket.send_json({"error": "닉네임 불일치"})
                 continue
            
            # Firestore에 저장 (서버 타임스탬프 사용)
            doc_ref = db.collection("messages").document()
            doc_id = doc_ref.id
            
            doc_ref.set({
                "nickname": message_dict["nickname"],
                "content": message_dict["content"],
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            
            # 모든 클라이언트에 브로드캐스팅
            message_data = {
                "id": doc_id,
                "nickname": message_dict["nickname"],
                "content": message_dict["content"],
                "timestamp": datetime.now().isoformat()
            }
            await manager.broadcast(message_data)

            # 백그라운드에서 오래된 메시지 정리 작업 추가
            background_tasks = BackgroundTasks()
            background_tasks.add_task(cleanup_old_messages)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket 에러: {e}")
        manager.disconnect(websocket)

# [API 2] 메시지 목록 조회 (최신 30개)
@app.post("/messages")
def get_messages(request: FetchMessagesRequest):
    nickname = request.nickname
    after = request.after

    # 화이트리스트 체크
    if not is_nickname_allowed(nickname):
        print(f"[SECURITY_ALERT] 무단 메시지 조회 시도 - 닉네임: {nickname}")
        raise HTTPException(status_code=403, detail="등록되지 않은 닉네임입니다.")

    # after 파라미터가 있으면 해당 시간 이후의 메시지만 조회
    if after:
        try:
            # ISO 형식 문자열을 datetime으로 변환
            after_dt = datetime.fromisoformat(after.replace('Z', '+00:00'))
            # 시간순 정렬 (과거 -> 현재) 후 필터링
            query = db.collection("messages").order_by("timestamp").where("timestamp", ">", after_dt).limit(30)
            docs = query.get()
        except Exception as e:
            print(f"타임스탬프 파싱 에러: {e}")
            # 에러 발생 시 최신 30개 반환
            docs = db.collection("messages").order_by("timestamp").limit_to_last(30).get()
    else:
        # after 파라미터가 없으면 최신 30개 반환
        docs = db.collection("messages").order_by("timestamp").limit_to_last(30).get()
    
    results = []
    for doc in docs:
        data = doc.to_dict()
        # 문서 ID 추가 (중복 방지용)
        data['id'] = doc.id
        # datetime 객체를 ISO 형식 문자열로 변환
        if isinstance(data.get('timestamp'), datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        else:
            data['timestamp'] = str(data.get('timestamp', ''))
        results.append(data)
    
    return results

# 서버 실행
# ...

# 서버 실행
# Render에서는 PORT 환경 변수를 사용
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
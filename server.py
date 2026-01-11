# server.py
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime
import uvicorn
import json
from typing import Set

# 1. Firebase 초기화 (보안 키 로드)
# 환경 변수에서 Firebase 키를 로드 (Render 배포용)
# 로컬에서는 secureKey.json 파일 사용
import os

def init_firebase():
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

# 2. FastAPI 앱 생성
app = FastAPI()

# --- 백그라운드 작업 ---
def cleanup_old_messages():
    """DB에서 가장 오래된 메시지를 삭제하여 50개만 남기는 함수"""
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

# [API 1] 메시지 전송 (저장) - HTTP 엔드포인트 (하위 호환성 유지)
@app.post("/send")
async def send_message(msg: Message, background_tasks: BackgroundTasks):
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
            # WebSocket에서는 BackgroundTasks를 직접 주입받을 수 없으므로,
            # FastAPI의 의존성 주입을 활용하지 않고 직접 생성하여 사용합니다.
            background_tasks = BackgroundTasks()
            background_tasks.add_task(cleanup_old_messages)
            # 이 함수(websocket_endpoint)가 비동기이므로, 백그라운드 작업은
            # FastAPI 이벤트 루프에 의해 실행됩니다.
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket 에러: {e}")
        manager.disconnect(websocket)

# [API 2] 메시지 목록 조회 (최신 30개)
@app.get("/messages")
def get_messages(after: str = Query(None, description="이 타임스탬프 이후의 메시지만 조회")):
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
# Render에서는 PORT 환경 변수를 사용
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
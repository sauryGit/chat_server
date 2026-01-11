import flet as ft
import aiohttp
import asyncio
import json

# [주의] 서버 URL 설정
# 환경 변수에서 가져오거나 기본값 사용
import os

# Render 서버 URL (배포 후 변경 필요)
# 예: "https://your-app-name.onrender.com"
RENDER_SERVER_URL = os.getenv("RENDER_SERVER_URL", "https://chat-server-x4o4.onrender.com")

# 로컬 개발 모드 감지
IS_LOCAL = RENDER_SERVER_URL == "http://localhost:8000"

SERVER_URL = RENDER_SERVER_URL
# WebSocket URL 변환 (http -> ws, https -> wss)
if SERVER_URL.startswith("https://"):
    WS_URL = SERVER_URL.replace("https://", "wss://") + "/ws"
elif SERVER_URL.startswith("http://"):
    WS_URL = SERVER_URL.replace("http://", "ws://") + "/ws"
else:
    WS_URL = f"ws://{SERVER_URL}/ws"

async def main(page: ft.Page):
    page.title = "스피드 비동기 채팅 🚀"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 400
    page.window_height = 700

    # UI 요소 정의
    chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
    nickname_input = ft.TextField(label="닉네임", width=200, value="익명")
    
    # [수정] focus()는 비동기 함수(Coroutine)이므로 await로 기다려야 합니다.
    # on_submit은 람다 대신 별도 async 함수로 연결하는 것이 안전합니다.
    message_input = ft.TextField(
        label="메시지 입력", 
        expand=True
    )
    
    # 이미 표시된 메시지 ID 추적 (중복 방지)
    seen_message_ids = set()
    # WebSocket 연결
    ws_connection = [None] 

    # [기능 1] 메시지 전송 (WebSocket)
    async def send_click(e):
        if not message_input.value:
            return
        
        current_msg = message_input.value
        current_nick = nickname_input.value
        
        # UI 비우기 & 포커스
        message_input.value = ""
        page.update()
        await message_input.focus()

        # WebSocket으로 메시지 전송
        if ws_connection[0] and not ws_connection[0].closed:
            try:
                message_data = {
                    "nickname": current_nick,
                    "content": current_msg
                }
                await ws_connection[0].send_str(json.dumps(message_data))
            except Exception as err:
                print(f"메시지 전송 에러: {err}")
        else:
            # WebSocket이 연결되지 않았으면 HTTP로 전송 (폴백)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{SERVER_URL}/send", json={
                        "nickname": current_nick,
                        "content": current_msg
                    }) as resp:
                        if resp.status != 200:
                            print("전송 실패")
            except Exception as err:
                print(f"전송 에러: {err}")

    # 엔터키 입력 시 실행될 함수 연결
    message_input.on_submit = send_click

    # 메시지 표시 함수
    def display_message(msg_id: str, nickname: str, content: str):
        # 중복 체크: 이미 본 메시지는 건너뛰기
        if msg_id and msg_id in seen_message_ids:
            return
        
        # 메시지 ID가 있으면 추가
        if msg_id:
            seen_message_ids.add(msg_id)
        
        is_me = nickname == nickname_input.value
        
        # [요청사항 1] ft.Colors 사용
        bg_color = ft.Colors.BLUE_400 if is_me else ft.Colors.GREY_400
        text_color = ft.Colors.WHITE

        chat_list.controls.append(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Column([
                            ft.Text(nickname, size=10, color=ft.Colors.GREY_500),
                            ft.Text(content, color=text_color, size=16)
                        ]),
                        bgcolor=bg_color,
                        padding=10,
                        border_radius=10,
                    )
                ],
                alignment=ft.MainAxisAlignment.END if is_me else ft.MainAxisAlignment.START
            )
        )
        page.update()

    # [기능 2] 초기 메시지 로드 (최신 30개)
    async def load_initial_messages():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{SERVER_URL}/messages") as resp:
                    if resp.status == 200:
                        messages = await resp.json()
                        # 시간순으로 정렬 (오래된 것부터)
                        for msg in messages:
                            msg_id = msg.get('id', '')
                            nickname = msg.get('nickname', '알 수 없음')
                            content = msg.get('content', '...')
                            display_message(msg_id, nickname, content)
        except Exception as e:
            print(f"초기 메시지 로드 에러: {e}")

    # [기능 3] WebSocket 연결 및 메시지 수신
    async def websocket_listener():
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(WS_URL) as ws:
                        ws_connection[0] = ws
                        print("WebSocket 연결됨")
                        
                        # 초기 메시지 로드
                        await load_initial_messages()
                        
                        # WebSocket 메시지 수신
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    message_data = json.loads(msg.data)
                                    msg_id = message_data.get('id', '')
                                    nickname = message_data.get('nickname', '알 수 없음')
                                    content = message_data.get('content', '...')
                                    display_message(msg_id, nickname, content)
                                except json.JSONDecodeError:
                                    print(f"JSON 파싱 에러: {msg.data}")
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                print(f"WebSocket 에러: {ws.exception()}")
                                break
            except Exception as e:
                print(f"WebSocket 연결 에러: {e}")
                ws_connection[0] = None
                # 재연결 시도 전 대기
                await asyncio.sleep(2)

    # [요청사항 2] ft.Icons 사용 (ft.icons.Icons는 존재하지 않음)
    input_row = ft.Row([
        message_input, 
        ft.IconButton(icon=ft.Icons.SEND, on_click=send_click)
    ])
    
    # [수정] add_async 대신 add 사용
    page.add(
        ft.Row([nickname_input], alignment=ft.MainAxisAlignment.CENTER),
        ft.Divider(),
        chat_list,
        ft.Divider(),
        input_row
    )

    # 백그라운드 태스크 시작 (WebSocket 연결)
    asyncio.create_task(websocket_listener())

ft.run(main=main)
import flet as ft
import aiohttp
import asyncio
import json
import os

# --- 서버 URL 설정 ---
RENDER_SERVER_URL = os.getenv("RENDER_SERVER_URL", "https://chat-server-x4o4.onrender.com")
SERVER_URL = RENDER_SERVER_URL

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
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # --- 상태 관리 ---
    # WebSocket 연결, 리스너 태스크, 닉네임 등을 관리
    ws_connection = [None]
    ws_listener_task = [None]
    user_nickname = [None]
    
    # 이미 표시된 메시지 ID (중복 방지)
    seen_message_ids = set()

    # --- UI 요소 ---
    chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
    message_input = ft.TextField(label="메시지 입력", expand=True)

    # --- 함수 정의 ---

    def display_message(msg_id: str, nickname: str, content: str):
        """채팅 메시지를 화면에 표시하는 함수"""
        if msg_id and msg_id in seen_message_ids:
            return
        if msg_id:
            seen_message_ids.add(msg_id)

        is_me = nickname == user_nickname[0]
        bg_color = ft.Colors.BLUE_400 if is_me else ft.Colors.GREY_400
        text_color = ft.Colors.WHITE

        chat_list.controls.append(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(nickname, size=10, color=ft.Colors.GREY_500),
                                ft.Text(content, color=text_color, size=16),
                            ],
                            spacing=2,
                        ),
                        bgcolor=bg_color,
                        padding=10,
                        border_radius=10,
                    )
                ],
                alignment=ft.MainAxisAlignment.END if is_me else ft.MainAxisAlignment.START,
            )
        )
        page.update()

    async def load_initial_messages():
        """서버에서 초기 메시지를 로드하는 함수"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{SERVER_URL}/messages") as resp:
                    if resp.status == 200:
                        messages = await resp.json()
                        for msg in messages:
                            display_message(
                                msg.get("id", ""),
                                msg.get("nickname", "알 수 없음"),
                                msg.get("content", "..."),
                            )
                        page.update() # 메시지들이 추가될 때마다 화면 업데이트
        except Exception as e:
            print(f"초기 메시지 로드 에러: {e}")

    async def websocket_listener():
        """WebSocket 연결 및 메시지 수신을 처리하는 리스너"""
        while True:
            # 연결이 끊어지면 2초 후 재연결 시도
            if ws_connection[0] is None or ws_connection[0].closed:
                try:
                    session = aiohttp.ClientSession()
                    ws = await session.ws_connect(WS_URL)
                    ws_connection[0] = ws
                    print("WebSocket 연결됨")
                    
                    # 연결 후 초기 메시지 로드
                    await load_initial_messages()
                except Exception as e:
                    print(f"WebSocket 연결 에러: {e}")
                    await session.close() # 세션 정리
                    ws_connection[0] = None
                    await asyncio.sleep(2)
                    continue

            # 메시지 수신 대기
            try:
                msg = await ws_connection[0].receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        message_data = json.loads(msg.data)
                        display_message(
                            message_data.get("id", ""),
                            message_data.get("nickname", "알 수 없음"),
                            message_data.get("content", "..."),
                        )
                    except json.JSONDecodeError:
                        print(f"JSON 파싱 에러: {msg.data}")
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    print("WebSocket 연결 끊어짐")
                    await ws_connection[0].close()
                    ws_connection[0] = None
            except Exception as e:
                print(f"WebSocket 수신 에러: {e}")
                if ws_connection[0]:
                    await ws_connection[0].close()
                ws_connection[0] = None
    
    async def send_click(e):
        """메시지 전송 버튼 클릭 이벤트 핸들러"""
        if not message_input.value:
            return

        msg_content = message_input.value
        message_input.value = ""
        await message_input.focus()

        # WebSocket으로 메시지 전송
        if ws_connection[0] and not ws_connection[0].closed:
            try:
                await ws_connection[0].send_str(
                    json.dumps({"nickname": user_nickname[0], "content": msg_content})
                )
            except Exception as err:
                print(f"메시지 전송 에러: {err}")
        page.update()

    message_input.on_submit = send_click

    # --- 화면 전환 함수 ---

    async def login_click(e):
        """로그인 버튼 클릭 이벤트 핸들러"""
        nickname = nickname_input.value.strip()
        if not nickname:
            nickname_input.error_text = "닉네임을 입력하세요."
            page.update()
            return
        
        user_nickname[0] = nickname
        page.clean()  # 페이지의 모든 컨트롤 제거
        await build_chat_view()  # 채팅 화면 구성
        
        # WebSocket 리스너 시작
        if ws_listener_task[0] is None:
            ws_listener_task[0] = asyncio.create_task(websocket_listener())

    async def logout_click(e):
        """로그아웃 버튼 클릭 이벤트 핸들러"""
        # WebSocket 리스너 중지
        if ws_listener_task[0]:
            ws_listener_task[0].cancel()
            ws_listener_task[0] = None
        
        # WebSocket 연결 종료
        if ws_connection[0]:
            await ws_connection[0].close()
            ws_connection[0] = None
            print("WebSocket 연결 종료됨")

        # 상태 초기화
        user_nickname[0] = None
        seen_message_ids.clear()
        chat_list.controls.clear()
        
        page.clean()
        build_login_view() # 로그인 화면 구성

    # --- UI 구성 함수 ---

    # 로그인 UI 요소
    nickname_input = ft.TextField(
        label="닉네임", 
        autofocus=True, 
        on_submit=login_click
    )
    login_button = ft.Button("채팅 시작", on_click=login_click)

    def build_login_view():
        """로그인 화면을 구성합니다."""
        page.add(
            ft.Column(
                [
                    ft.Text("로그인", size=32, weight=ft.FontWeight.BOLD),
                    nickname_input,
                    login_button,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )
        )
        page.update()

    async def build_chat_view():
        """채팅 화면을 구성합니다."""
        page.add(
            ft.Row(
                [
                    ft.Text(f"💬 {user_nickname[0]}", size=16, weight=ft.FontWeight.BOLD),
                    ft.IconButton(
                        icon=ft.Icons.LOGOUT,
                        on_click=logout_click,
                        tooltip="로그아웃",
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Divider(),
            chat_list,
            ft.Divider(),
            ft.Row(
                [
                    message_input,
                    ft.IconButton(icon=ft.Icons.SEND, on_click=send_click, tooltip="전송"),
                ]
            ),
        )
        page.update()
        # 비동기적으로 포커스 설정
        await message_input.focus()


    # --- 앱 시작 ---
    build_login_view()


ft.run(main=main)
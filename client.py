import flet as ft
import aiohttp
import asyncio
import json
import os
import webbrowser
import urllib.parse
import random
from datetime import datetime, timezone, timedelta

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
    page.title = "Bamboo Forest"
    
    # --- 폰트 설정 ---
    page.fonts = {
        "pretendard": "/fonts/Pretendard-Regular.ttf",
    }
    page.theme = ft.Theme(font_family="pretendard")
    
    # 운영체제 설정(다크/라이트)을 자동으로 따르도록 설정
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.window.width = 400
    page.window.height = 700
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

    def display_message(msg_id: str, nickname: str, content: str, timestamp: str = None):
        """채팅 메시지를 화면에 표시하는 함수"""
        if msg_id and msg_id in seen_message_ids:
            return
        if msg_id:
            seen_message_ids.add(msg_id)

        is_me = nickname == user_nickname[0]
        
        # 현재 테마 모드 감지
        is_dark_mode = page.theme_mode == ft.ThemeMode.DARK or (
            page.theme_mode == ft.ThemeMode.SYSTEM and page.platform_brightness == ft.Brightness.DARK
        )

        if is_me:
            # 내 메시지: 다크모드면 조금 더 어두운 파란색
            bg_color = ft.Colors.BLUE_800 if is_dark_mode else ft.Colors.BLUE_400
        else:
            # 라이트 모드용 팔레트 (기존)
            light_palette = [
                ft.Colors.INDIGO_400, ft.Colors.PINK_400, ft.Colors.PURPLE_400,
                ft.Colors.DEEP_PURPLE_400, ft.Colors.INDIGO_400, ft.Colors.CYAN_400,
                ft.Colors.TEAL_400, ft.Colors.GREEN_400, ft.Colors.LIME_400,
                ft.Colors.AMBER_400, ft.Colors.ORANGE_400, ft.Colors.BROWN_400,
                ft.Colors.BLUE_GREY_400,
            ]
            
            
            # 다크 모드용 팔레트 (톤 다운된 색상)
            dark_palette = [
                ft.Colors.INDIGO_700, ft.Colors.PINK_900, ft.Colors.PURPLE_900,
                ft.Colors.DEEP_PURPLE_900, ft.Colors.INDIGO_900, ft.Colors.CYAN_900,
                ft.Colors.TEAL_900, ft.Colors.GREEN_900, ft.Colors.LIME_900,
                ft.Colors.AMBER_900, ft.Colors.ORANGE_900, ft.Colors.BROWN_900,
                ft.Colors.BLUE_GREY_900,
            ]

            current_palette = dark_palette if is_dark_mode else light_palette
            
            color_index = sum(ord(c) for c in nickname) % len(current_palette)
            bg_color = current_palette[color_index]

        text_color = ft.Colors.WHITE
        # 테마 모드에 따른 닉네임 색상 설정 (다크: 밝게, 라이트: 어둡게)
        nickname_color = ft.Colors.WHITE if is_dark_mode else ft.Colors.BLACK

        # 시간 포맷팅
        time_str = ""
        if timestamp:
            try:
                # ISO 문자열을 datetime 객체로 변환
                dt = datetime.fromisoformat(timestamp)
                
                # 만약 타임존 정보가 없다면 UTC로 가정
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                
                # 한국 시간(KST, UTC+9)으로 변환
                kst_timezone = timezone(timedelta(hours=9))
                dt_kst = dt.astimezone(kst_timezone)
                
                time_str = dt_kst.strftime("%H:%M:%S")
            except ValueError:
                time_str = ""


        header_controls = [
            ft.Text(
                nickname, 
                size=15, 
                color=nickname_color, 
                weight=ft.FontWeight.NORMAL, 
                selectable=True,
                
            )
        ]
        if time_str:
            header_controls.append(ft.Text(time_str, size=12, color=ft.Colors.BLACK_45, selectable=True))

        chat_list.controls.append(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Row(header_controls, spacing=5),
                                ft.Text(content, color=text_color, size=16, selectable=True),
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
            # 닉네임을 JSON Body로 전달하여 화이트리스트 검증 수행 (POST)
            payload = {"nickname": user_nickname[0]}
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{SERVER_URL}/messages", json=payload) as resp:
                    if resp.status == 200:
                        messages = await resp.json()
                        for msg in messages:
                            display_message(
                                msg.get("id", ""),
                                msg.get("nickname", "알 수 없음"),
                                msg.get("content", "..."),
                                msg.get("timestamp"),
                            )
                    elif resp.status == 403:
                         print("접근 권한이 없습니다 (화이트리스트 제한).")
                         await perform_logout("등록되지 않은 닉네임입니다.")
                         return
                    else:
                        print(f"메시지 로드 실패. Status: {resp.status}")
                    page.update()

        except Exception as e:
            print(f"초기 메시지 로드 에러: {e}")

    async def websocket_listener():
        """WebSocket 연결 및 메시지 수신을 처리하는 리스너"""
        while True:
            # 연결이 끊어지면 2초 후 재연결 시도
            if ws_connection[0] is None or ws_connection[0].closed:
                try:
                    session = aiohttp.ClientSession()
                    
                    # 닉네임을 헤더에 추가 (URL 인코딩하여 전송)
                    # 한글 닉네임 등을 안전하게 전송하기 위함
                    encoded_nickname = urllib.parse.quote(user_nickname[0])
                    headers = {"x-nickname": encoded_nickname}
                    
                    ws = await session.ws_connect(WS_URL, headers=headers)
                    ws_connection[0] = ws
                    print("WebSocket 연결됨")
                    
                    # 연결 후 초기 메시지 로드
                    await load_initial_messages()
                    # 초기 메시지 로드 중 로그아웃(화이트리스트 거부 등)되면 리스너 종료
                    if user_nickname[0] is None:
                        return

                except aiohttp.WSServerHandshakeError as e:
                    if e.status == 403:
                         print("접근 권한이 없습니다 (화이트리스트 제한 - WebSocket).")
                         await session.close()
                         ws_connection[0] = None
                         await perform_logout("등록되지 않은 닉네임입니다.")
                         return
                    print(f"WebSocket 핸드쉐이크 에러: {e}")
                    await session.close()
                    ws_connection[0] = None
                    await asyncio.sleep(2)
                    continue

                except aiohttp.ClientConnectorError as e:
                    print(f"서버 연결 실패: {e}")
                    await session.close()
                    ws_connection[0] = None
                    await perform_logout("서버에 연결할 수 없습니다. 인터넷 연결을 확인해주세요.")
                    return

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
                            message_data.get("timestamp"),
                        )
                    except json.JSONDecodeError:
                        print(f"JSON 파싱 에러: {msg.data}")
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    # 화이트리스트 거부 (4003) 확인
                    if ws_connection[0].close_code == 4003:
                        await perform_logout("등록되지 않은 닉네임입니다.")
                        return

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

    async def perform_logout(error_message: str = None):
        """로그아웃 처리 및 로그인 화면으로 이동"""
        # WebSocket 리스너 중지
        # 현재 실행 중인 태스크(자신)가 아닐 때만 취소
        if ws_listener_task[0] and ws_listener_task[0] != asyncio.current_task():
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

        # 에러 메시지가 있으면 커스텀 페이드아웃 알림 표시
        if error_message:
            notification = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.WHITE),
                        ft.Text(error_message, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                ),
                bgcolor=ft.Colors.BLACK_87,
                padding=ft.Padding.symmetric(vertical=15, horizontal=25),
                border_radius=30,
                opacity=1,
                animate_opacity=1000, # 1초 동안 페이드 아웃
                margin=ft.Margin.only(top=50), # 상단 여백
            )
            
            # 중앙 정렬을 위한 Row 래퍼
            overlay_wrapper = ft.Row(
                [notification],
                alignment=ft.MainAxisAlignment.CENTER,
            )
            
            page.overlay.append(overlay_wrapper)
            page.update()
            
            # 2.5초 대기 후 페이드 아웃 시작
            await asyncio.sleep(2.5)
            notification.opacity = 0
            page.update()
            
            # 애니메이션 완료 후 제거
            await asyncio.sleep(1.1)
            if overlay_wrapper in page.overlay:
                page.overlay.remove(overlay_wrapper)
            page.update()
        
        page.update()

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
        await perform_logout()

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
        # 특정 URL 설정 (원하시는 URL로 변경하세요)
        target_url = "https://bloob.io/yacht"

        # 랜덤 텍스트 기능
        random_texts = [
            "오늘도 좋은 하루 보내세요!", "행복한 일이 가득하길!", "화이팅입니다!", 
            "잠시 쉬어가는 여유를 가져보세요.", "맛있는 거 드시고 힘내세요!", 
            "웃으면 복이 온대요.", "당신은 최고입니다!", "즐거운 채팅 되세요.",
            "좋은 사람들과 좋은 시간!", "항상 응원합니다."
        ]
        random_text_display = ft.Text("", size=14)

        def generate_random_text(e):
            randint = random.randint(1,5)
            if randint == 1:
                random_text_display.value = "안전하게"
            elif randint == 2:
                random_text_display.value = "지금은 아니다"
            elif randint == 3:
                random_text_display.value = "소신대로"
            elif randint == 4:
                random_text_display.value = "지금이 기회다!"
            elif randint == 5:
                random_text_display.value = "지금 질러야한다"
            page.update()

        page.add(
            ft.Row(
                [
                    ft.Row(
                        [
                            ft.Text(f"   {user_nickname[0]}", size=16, weight=ft.FontWeight.BOLD),
                            ft.Button(
                                "Go to page",
                                on_click=lambda _: webbrowser.open(target_url),
                                style=ft.ButtonStyle(
                                    padding=ft.Padding(10, 5, 10, 5),
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                ),
                                margin=ft.Margin(10,0,0,0)
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=0,
                    ),
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
            ft.Row(
                [
                    ft.ElevatedButton("책님의 조언", on_click=generate_random_text),
                    random_text_display,
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10
            ),
        )
        page.update()
        # 비동기적으로 포커스 설정
        await message_input.focus()


    # --- 앱 시작 ---
    build_login_view()


ft.run(main=main, assets_dir="assets")
# Meeting Room System

Dify 플랫폼에서 사용하는 것을 목적으로 한 회의실 운용 시스템입니다. 자연어로 예약을 조회하거나 예약 요청을 만들 수 있고, 관리자는 요청을 승인하거나 거절할 수 있습니다.
확정된 예약은 설정에 따라 Google Calendar에도 함께 등록됩니다.

이 프로젝트는 AI 에이전트를 통해 사내 회의실 예약 시스템을 제작해 보는 것을 목표로 만들었습니다. 데이터는 SQLite에 저장하므로 별도의 DB 서버 없이 실행할 수 있습니다.

## 주요 기능 (MCP Tools)

[공통 기능]

- 회의실 예약 현황 조회
    - 특정 날짜나 기간으로 회의실 예약 현황을 조회할 수 있습니다.
    -

관리자 기능

일반 사원 기능

- 이메일을 이용한 직원 확인
- 날짜, 기간, 카테고리별 예약 조회
- 회의실 예약 생성 및 중복 시간 검사
- 예약별 참가자 저장과 직원별 일정 조회
- 업무 시간 내 빈 시간 검색
- 카테고리, 요일, 시간대별 이용 통계
- 일반 직원의 예약 요청 등록
- 관리자의 예약 요청 승인 및 거절
- Google Calendar 선택 연동

## 사용 기술

- Python
- FastMCP
- SQLite
- Dify
- Google Calendar API

## 사용 가이드

`services`에는 예약과 요청을 처리하는 로직이 있고, `utils`에는 DB 연결, 날짜 변환, Google Calendar 연동 코드가 들어 있습니다. `mcp_server.py`는 이 기능들을 MCP 도구로 공개합니다.

## 실행 준비

### 요구 사항

- Python 3.10 이상
- Windows PowerShell
- Dify 연동 시 MCP를 사용할 수 있는 Dify 환경
- Google Calendar 연동 시 Google Cloud 서비스 계정

### 가상환경과 패키지 설치

프로젝트 폴더에서 다음 명령을 실행합니다.

```powershell
python -m venv mcp
.\mcp\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install fastmcp google-api-python-client google-auth
```

이미 `mcp` 가상환경을 구성했다면 활성화 명령만 실행하면 됩니다.

## 서버 실행

### Dify 모드

```powershell
$env:MCP_MODE = "dify"
$env:PORT = "8001"
python .\mcp_server.py
```

Dify 모드는 SSE 방식으로 실행됩니다. 저장해둔 설정을 이용하려면 다음 스크립트를 사용할 수 있습니다.

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\run_mcp.ps1
```

### 관리자 모드

```powershell
$env:MCP_MODE = "admin"
python .\mcp_server.py
```

관리자 모드는 표준 입출력 방식으로 실행됩니다. MCP Inspector를 사용하면 각 도구의 입력값과 반환값을 직접 확인할 수 있습니다.

```powershell
npx @modelcontextprotocol/inspector
```

## 환경변수

| 이름                          | 기본값                     | 설명                              |
| ----------------------------- | -------------------------- | --------------------------------- |
| `MCP_MODE`                    | `admin`                    | `admin` 또는 `dify`               |
| `PORT`                        | `8001`                     | Dify 모드에서 사용할 포트         |
| `MEETING_ROOM_DB_PATH`        | `database/meeting_room.db` | SQLite DB 파일 경로               |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | 없음                       | Google 서비스 계정 JSON 파일 경로 |
| `GOOGLE_CALENDAR_ID`          | 없음                       | 연동할 Google Calendar ID         |

DB 파일이 없으면 서버 시작 시 `database/database_setting.sql`을 사용해 새로 생성합니다.

## 제공하는 MCP 도구

| 도구                              | 모드         | 역할                             |
| --------------------------------- | ------------ | -------------------------------- |
| `authenticate_employee`           | Dify         | 이메일로 직원 확인               |
| `list_reservations_with_date`     | Admin / Dify | 날짜, 기간, 카테고리별 예약 조회 |
| `add_reservation`                 | Admin / Dify | 예약을 바로 생성                 |
| `find_available_slots`            | Dify         | 지정한 날짜의 빈 시간 조회       |
| `get_statistics`                  | Dify         | 예약 이용 통계 조회              |
| `list_reservations_with_employee` | Admin / Dify | 직원별 참여 일정 조회            |
| `create_reservation_request`      | Dify         | 예약 요청을 대기 상태로 등록     |
| `list_reservation_requests`       | Admin / Dify | 예약 요청 목록 조회              |
| `approve_reservation_request`     | Admin / Dify | 요청 승인 및 실제 예약 생성      |
| `reject_reservation_request`      | Admin / Dify | 요청 거절 및 사유 저장           |

예약 시간은 `YYYY-MM-DD HH:MM` 형식으로 전달합니다. 카테고리는 코드와 DB에서 사용하는 다음 값 중 하나여야 합니다.

```text
会議 / 接客 / 面接 / 自由
```

직접 예약과 예약 요청 모두 참가자 목록이 필요합니다. 참가자는 `employees` 테이블에 등록된 이름으로 전달하며, 실제 예약에는 해당 직원의 ID 목록이 JSON 형태로 저장됩니다.

## 예약 요청 상태

- `pending`: 관리자 확인 전
- `approved`: 승인되어 실제 예약이 생성된 상태
- `rejected`: 거절된 상태

승인 과정에서 시간 중복이 발견되면 실제 예약은 생성되지 않으며 요청은 `pending` 상태를 유지합니다.

## Google Calendar 연동

서비스 계정 파일과 Calendar ID가 설정되어 있으면 직접 예약 또는 요청 승인 시 Calendar 이벤트가 생성됩니다.

Calendar 설정이 없거나 외부 API 호출에 실패하더라도 SQLite에 생성된 예약은 유지됩니다. 동기화 결과는 응답의 `calendar_sync` 값으로 확인할 수 있습니다.

- `success`: Calendar 등록 성공
- `not_configured`: 연동 정보가 설정되지 않음
- `failed`: API 호출 실패

## 테스트

현재 테스트 DB에는 연속 예약, 서로 다른 이용 시간, 카테고리별 예약, 승인·거절·충돌 요청 등 MCP 동작을 확인하기 위한 데이터가 들어 있습니다.

특히 다음 흐름을 확인할 수 있습니다.

- 시간이 맞닿은 예약이 충돌 없이 생성되는지
- 시간이 겹친 요청의 승인이 차단되는지
- 승인된 요청이 실제 예약과 참가자 정보로 연결되는지
- 거절된 요청에 사유가 남는지
- 날짜·직원·카테고리 조회와 통계가 정상인지

## 참고 사항

- `calendar_credentials.json`은 인증 정보이므로 Git에 커밋하지 않습니다.
- 운영 환경에서는 인증 파일과 Calendar ID를 비밀값으로 관리하는 것이 좋습니다.
- 현재 예약 수정과 삭제 기능은 구현되어 있지 않습니다.
- Dify 에이전트의 상세 동작과 대화 흐름은 Dify 워크플로 YAML 정리 후 이 문서에 추가할 예정입니다.

## Demo

Dify 에이전트와 관리자 승인 과정을 확인할 수 있는 실행 영상은 추후 추가할 예정입니다.

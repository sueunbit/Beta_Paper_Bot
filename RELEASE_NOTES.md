# Paper Bot v2.0.0-beta.6

키워드로 논문을 검색하고 MDPI를 제외하여 Notion의 Paper Bot 표에 정리하는 로컬 Python 도구입니다. Gemini 연결 시 재사용 허용 공개 PDF를 우선 분석하며, 확보하지 못하면 초록을 분석하고 범위를 표시합니다. OpenAI 연결은 초록 분석을 지원합니다.

## 이번 배포 변경

- 01~09 번호 실행 파일: 설치 확인 → Notion 연결 → 표 생성 → 검색 설정 → 선택적 AI/PDF 설정 → 실행
- 90번대 관리 도구: 기존 요약, 전문 재분석, 이전 안내 문구 제거와 표 전환
- `00_READ_FIRST.html` 및 `.txt`: Notion 권한과 페이지 연결부터 문제 해결까지 안내
- GitHub 배포 가이드와 개인 설정을 제외한 ZIP

## 시작

1. Windows에 Python 3.10 이상을 설치하고 ZIP을 모두 압축 해제합니다.
2. `00_READ_FIRST.html`을 열어 Notion 준비와 번호 순서를 따라갑니다.
3. AI를 사용하지 않으면 06·07을 생략하고 09로 수집합니다.

Notion 표: Read / Paper / Publish Date / Journal / DOI / Corresponding author / Keyword / 수집일시.
각 논문 제목을 열면 요약을 확인할 수 있습니다. 각 사용자가 자신의 연결 토큰과 API 키를 설정합니다.

## 기존 사용자

실행 중인 봇을 종료하고 코드 파일을 덮어쓰되 `.env`, `config.json`, `notion_table.json`, `state.sqlite3`, `output`은 유지하세요. 기존 연결이 정상이면 재설정은 필요 없습니다. 기존 이름의 실행 파일도 계속 사용할 수 있습니다.

## 범위와 검증

공개 PDF는 CC BY/CC0 확인, 로그인 불필요, 12 MiB 이하 등 조건이 적용됩니다. 학교 구독 로그인과 별도 보충자료 수집은 지원하지 않습니다. 모든 논문의 전문 확보나 AI 분석의 정확성을 보장하지 않습니다. 무료 API에도 한도가 있으며 유료 프로젝트에서는 요금이 발생할 수 있습니다.

PC와 실행 창이 켜져 있어야 합니다. 백그라운드 서비스와 예약 실행은 포함하지 않습니다.
자동 테스트 49개와 오프라인 데모 통과. Windows 실행 및 실제 Notion·Gemini API는 사용자 환경에서 확인이 필요합니다.

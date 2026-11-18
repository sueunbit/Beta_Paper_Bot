# GitHub 배포 가이드 — v2.0.0-beta.6

이 패키지는 배포 준비 파일입니다. 아직 GitHub에 업로드하거나 Release를 게시하지 않았습니다.
기능은 beta.5와 같으며, beta.6은 번호 실행 파일과 설치·운영 안내를 추가한 버전입니다.

## 1. 배포용 폴더 준비

다운로드한 ZIP을 **평소 사용하는 폴더와 다른 새 폴더**에 압축 해제하세요. 개인 설정이 없는 이 폴더를 GitHub에 올리는 것이 가장 간단합니다.

탐색기에서 숨김 파일 표시를 켜고 `.gitignore`가 있는지 확인하세요. 파일명을 `.gitignore.txt`로 바꾸지 마세요. 이번 ZIP에 이미 포함되어 있습니다.

업로드하지 않는 파일:

- `.env`, `config.json`, `notion_table.json`
- `state.sqlite3` 및 같은 이름으로 시작하는 DB 보조 파일
- `output/`, `.venv/`, `__pycache__/`, `.paper_bot.lock`

예시 파일 `.env.example`, `config.example.json`은 공유해도 됩니다. 실제 키를 예시 파일에 넣지 마세요. `.gitignore`는 이미 커밋된 파일을 제거하지 않습니다. 기존 저장소에 비밀 키가 올라갔다면 해당 키를 폐기·재발급하고 GitHub 안내에 따라 기록을 정리하세요.

## 2. GitHub Desktop에서 저장소 준비

이미 저장소가 있다면 그 저장소 폴더에 새 코드·문서를 복사하고 변경 목록을 확인하세요. `.git` 폴더와 기존 LICENSE는 유지하세요.

처음이라면 GitHub Desktop에서 File → Add local repository → Choose를 눌러 **프로그램 파일이 들어 있는 폴더**를 선택하세요. `.py` 파일들을 개별 선택하는 것이 아닙니다. Git 저장소가 아니라는 안내가 나오면 해당 폴더에 새 저장소를 만드는 링크를 선택하거나 File → New repository로 빈 저장소를 만든 뒤 그 안에 배포용 파일을 복사하세요.

Repository 이름 예: `paper-bot`. Changes에서 실제 키나 개인 데이터가 포함되지 않았는지 확인하세요. 커밋 제목 예: `Prepare v2.0.0-beta.6 distribution guides`.

처음은 Publish repository, 기존 원격 저장소는 Push origin으로 올립니다. 공개 배포하려면 저장소 공개 범위를 Public으로 선택하세요. README가 저장소 첫 화면에 나타납니다.

## 3. 라이선스 선택

기존 저장소에 LICENSE가 있으면 그대로 유지하세요. 새 저장소라면 작성자가 재사용 조건을 선택하고 LICENSE를 추가하세요. 이 패키지는 사용자의 라이선스 선택을 대신하지 않습니다. 코드 공개와 다른 사람의 재사용 허락은 별개입니다.

## 4. GitHub Release 만들기

저장소 웹페이지 → Releases → Draft a new release.

- Tag: `v2.0.0-beta.6` (현재 업로드한 커밋을 대상으로 생성)
- Title: `Paper Bot v2.0.0-beta.6 — Windows quick start`
- 본문: `RELEASE_NOTES.md` 내용 복사
- 첨부: 전달받은 `paper-bot-v2.0.0-beta.6.zip` 원본
- beta 버전이므로 Pre-release로 표시

실사용 폴더를 다시 압축하면 비밀 파일까지 포함될 수 있습니다. `.gitignore`는 탐색기 ZIP 압축에는 적용되지 않습니다. 제공된 깨끗한 ZIP을 첨부하세요.

게시 전 신규 사용자 입장에서 01~08을 한 번 확인하세요. 개발 환경에서 자동 테스트와 오프라인 데모는 통과했지만 Windows 배치 파일 실행과 실제 Gemini·Notion 연결은 배포자의 PC에서 최종 확인이 필요합니다.

## 5. 사용자에게 전달할 안내

“Release의 ZIP을 다운로드하고 모두 압축을 푼 뒤 `00_READ_FIRST.html`을 열어주세요. 최초 01~07 설정 후 평소에는 08을 실행합니다. AI 없는 수집은 09입니다. 각자의 Notion 연결과 AI 키를 사용합니다.”

참고: https://docs.github.com/en/desktop/adding-and-cloning-repositories
참고: https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository

"""Interactive Notion setup and bounded local polling. No external packages."""
import argparse
import datetime as dt
import getpass
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
import urllib.parse
import paper_bot as bot
import ai_provider


def page_id(value):
    path = urllib.parse.urlsplit(value.strip()).path if '://' in value else value.strip()
    match = re.search(r'([0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})/?$', path)
    if not match:
        raise ValueError('일반 Notion 페이지의 링크 또는 32자리 페이지 ID를 입력하세요.')
    return match.group(1).replace('-', '').lower()


def credentials():
    token = os.getenv('NOTION_TOKEN', '').strip()
    if not token:
        raise ValueError('먼저 setup_notion.bat을 실행하세요.')
    return token, page_id(os.getenv('NOTION_PARENT_PAGE_ID', ''))


def check_connection(token, parent):
    data = bot.request_json('https://api.notion.com/v1/pages/' + parent,
        headers={'Authorization': 'Bearer ' + token, 'Notion-Version': '2022-06-28'})
    if data.get('object') != 'page' or data.get('archived') or data.get('in_trash'):
        raise ValueError('활성 일반 페이지가 아닙니다. 다른 부모 페이지를 선택하세요.')
    print('Notion 부모 페이지 읽기 연결 확인 완료. 쓰기 권한은 테스트 페이지로 확인합니다.')
    return data


def save_credentials(token, parent):
    path = bot.ROOT / '.env'
    existing = path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []
    lines = [s for s in existing if not re.match(r'^\s*(NOTION_TOKEN|NOTION_PARENT_PAGE_ID)\s*=', s)]
    lines.extend(['NOTION_TOKEN=' + token, 'NOTION_PARENT_PAGE_ID=' + parent])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    if os.name != 'nt':
        path.chmod(0o600)
    os.environ.update(NOTION_TOKEN=token, NOTION_PARENT_PAGE_ID=parent)


def setup():
    print('Notion 내부 연결의 콘텐츠 읽기/삽입/업데이트 권한을 켜고, 부모 페이지에 해당 연결을 추가하세요.')
    print('토큰은 이 컴퓨터의 .env에만 저장합니다. 입력 문자는 화면에 표시되지 않습니다.')
    token = getpass.getpass('Notion 내부 연결 토큰: ').strip()
    if not token or any(c.isspace() for c in token):
        raise ValueError('공백 없는 토큰을 입력하세요.')
    parent = page_id(input('저장할 일반 Notion 페이지 링크: '))
    check_connection(token, parent)
    save_credentials(token, parent)
    print('설정 저장 완료. test_notion.bat으로 테스트 페이지를 전송하세요.')


def test_write():
    token, parent = credentials()
    check_connection(token, parent)
    paper = {'doi': 'local-notion-connection-test-v1', 'title': '[논문 봇] Notion 연결 테스트',
        'url': '', 'date': dt.date.today().isoformat(), 'publisher': '로컬 연결 테스트',
        'keywords': [], 'basis': '연결 확인용 / 실제 논문 아님',
        'analysis': '이 페이지가 보이면 로컬 프로그램에서 Notion으로 페이지를 생성하는 데 성공했습니다. AI API는 호출하지 않았습니다.'}
    out = bot.ROOT / 'output' / 'connection-test'
    out.mkdir(parents=True, exist_ok=True)
    print(json.dumps(bot.publish([paper], out), ensure_ascii=False, indent=2))


def known_dois(parent):
    import notion_table
    config = notion_table.settings()
    if config:
        parent = 'table:' + config['data_source_id']
    path = bot.ROOT / 'state.sqlite3'
    if not path.exists():
        return set()
    with sqlite3.connect(path) as db:
        if not db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='posted'").fetchone():
            return set()
        # Pending writes are also excluded to avoid duplicate creation after a timeout.
        return {row[0] for row in db.execute('SELECT doi FROM posted WHERE parent=?', (parent,))}


def load_config():
    c = json.loads((bot.ROOT / 'config.json').read_text(encoding='utf-8-sig'))
    if not isinstance(c.get('keywords'), list) or not c['keywords'] or any(not isinstance(x, str) or not x.strip() for x in c['keywords']):
        raise ValueError('config.json의 keywords를 입력하세요.')
    if not 1 <= c.get('max_papers', 0) <= 20 or not 1 <= c.get('candidates_per_keyword', 0) <= 100:
        raise ValueError('max_papers: 1~20, candidates_per_keyword: 1~100')
    dt.date.fromisoformat(c['from_date'])
    return c


def cycle(config, deadline, metadata_only, budget=None):
    _, parent = credentials()
    raw = bot.search(config)
    known = known_dois(parent)
    # Remove posted papers BEFORE limiting, so later candidates can be processed.
    raw = [p for p in raw if bot.doi_key(p.get('doi', '')) not in known]
    selected, audit = bot.select(raw, config)
    out = bot.ROOT / 'output' / dt.datetime.now().strftime('run-%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True, exist_ok=True)
    done, results = [], []
    for p in selected:
        if time.monotonic() >= deadline:
            break
        if metadata_only:
            p['basis'] = '메타데이터 수집 / AI 분석 미실행'
            p['analysis'] = ''
        else:
            if budget is not None:
                if budget['remaining'] <= 0:
                    print('이번 실행의 AI 요청 한도에 도달했습니다.')
                    break
                budget['remaining'] -= 1
            try:
                p['analysis'], p['basis'] = bot.analyze(p, {**config, '_fallback_budget':budget})
                if p['basis'] in ('초록 기반 AI 분석 / 전문 미확인','공개 PDF 기반 AI 분석'):
                    stamp = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds')
                    p['analysis'] = 'AI 요약 생성: ' + stamp + '\n모델: ' + ai_provider.provider() + '/' + ai_provider.model_name() + '\n근거: '+p['basis']+'\n\n' + p['analysis']
            except RuntimeError as exc:
                p['analysis'] = 'AI 분석 실패. summarize_existing.bat으로 나중에 재시도할 수 있습니다.'
                p['basis'] = '요약 실패 / 재시도 가능'
                print(str(exc), flush=True)
        done.append(p)
        bot.save_report(done, audit, config, out, False)
        if time.monotonic() >= deadline:
            print('실행 시간 도달: 분석 미리보기만 저장했습니다. 다음 실행에서 다시 처리합니다.')
            break
        results.extend(bot.publish([p], out))
        (out / 'notion-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Notion 처리: ' + p['title'], flush=True)
    if not done:
        bot.save_report([], audit, config, out, False)
    print(f'이번 검색: 새 후보 {len(selected)}편 / 처리 {len(results)}편', flush=True)


def run_for(minutes, interval_minutes, callback, clock=time.monotonic, sleeper=time.sleep):
    if not all(math.isfinite(v) and v > 0 for v in [minutes, interval_minutes]):
        raise ValueError('실행 시간과 검색 간격은 0보다 큰 유한한 숫자여야 합니다.')
    deadline = clock() + minutes * 60
    while clock() < deadline:
        callback(deadline)
        wake = min(deadline, clock() + interval_minutes * 60)
        # Small waits let Ctrl+C terminate promptly.
        while clock() < wake:
            sleeper(min(1, wake - clock()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['setup', 'test', 'run'])
    parser.add_argument('--minutes', type=float)
    parser.add_argument('--interval', type=float)
    parser.add_argument('--ai-limit', type=int, default=5, help='전체 실행 중 최대 AI 요청 수 (기본 5)')
    parser.add_argument('--metadata-only', action='store_true', help='AI 없이 서지정보·링크만 수집')
    args = parser.parse_args()
    bot.load_env()
    if args.command == 'setup':
        return setup()
    if args.command == 'test':
        return test_write()
    config = load_config()
    minutes = args.minutes if args.minutes is not None else float(input('총 실행 시간(분, 예: 120): '))
    interval = args.interval if args.interval is not None else float(input('검색 완료 후 대기 간격(분, 예: 15): '))
    if not all(math.isfinite(v) and v > 0 for v in [minutes, interval]):
        raise ValueError('시간은 0보다 큰 숫자여야 합니다.')
    metadata_only = args.metadata_only
    if not 1 <= args.ai_limit <= 100:
        raise ValueError('ai-limit는 1~100이어야 합니다.')
    has_ai = ai_provider.ready()
    if args.minutes is None and has_ai and not metadata_only:
        mode = input('실행 모드: 1=기본 수집, 2=AI 요약 포함 (기본 1): ').strip() or '1'
        if mode not in ('1','2'): raise ValueError('1 또는 2를 입력하세요.')
        metadata_only = mode == '1'
        if not metadata_only:
            args.ai_limit = int(input('전체 실행 중 AI 요청 최대 횟수 (1~100, 추천 5): '))
            if not 1 <= args.ai_limit <= 100: raise ValueError('1~100을 입력하세요.')
            print('선택한 모델의 API 사용 비용이 발생할 수 있습니다.')
    if not metadata_only and not ai_provider.ready():
        if args.minutes is not None:
            raise ValueError('AI 설정이 없습니다. 연결 테스트용 서지정보 수집은 --metadata-only를 지정하세요.')
        print('AI API가 아직 연결되지 않았습니다. 제목·출처·링크만 수집할 수 있습니다.')
        if input('요약 없이 서지정보만 수집할까요? (y/N): ').strip().lower() != 'y':
            return
        metadata_only = True
    check_connection(*credentials())
    print(f'{minutes:g}분 동안 실행 / 검색 완료 후 {interval:g}분 대기 / Ctrl+C로 종료', flush=True)
    print('시간이 되면 새 요청을 시작하지 않습니다. 진행 중인 요청은 응답/타임아웃 후 종료됩니다.')
    budget = None if metadata_only else {'remaining': args.ai_limit}
    if budget: print(f'전체 실행 중 AI 요청 최대 {args.ai_limit}회')
    def tick(deadline):
        if budget is not None and budget['remaining'] <= 0:
            raise StopIteration
        cycle(config, deadline, metadata_only, budget)
    try:
        run_for(minutes, interval, tick)
    except StopIteration:
        print('AI 요청 한도에 도달해 종료했습니다.')
    print('설정한 실행 시간이 끝났습니다.')


if __name__ == '__main__':
    try:
        from runtime_lock import single_writer
        with single_writer():
            main()
    except KeyboardInterrupt:
        print('\n사용자가 실행을 중단했습니다. 전송 중이었다면 Notion에서 결과를 확인하세요.')
    except (RuntimeError, ValueError, OSError, KeyError, sqlite3.Error) as exc:
        print('실행 중단: ' + str(exc), file=sys.stderr)
        print('401: 토큰 / 403: 읽기·삽입 권한 / 404: 부모 페이지 연결과 링크를 확인하세요.', file=sys.stderr)
        sys.exit(1)

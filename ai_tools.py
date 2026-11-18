"""Optional OpenAI setup and append-only summaries for existing Notion rows."""
import argparse
import datetime as dt
import getpass
import json
import os
import re
import sqlite3
import sys
import urllib.parse
import paper_bot as bot
import ai_provider
import fulltext
import notion_table as table
from runtime_lock import single_writer

COMPLETE = '초록 기반 AI 분석 / 전문 미확인'
NO_ABSTRACT = '초록 없음 / 분석 보류'
MARKER = 'Paper Bot AI 요약 · 초록 기반'


def require_ai():
    if not ai_provider.ready():
        raise ValueError('먼저 setup_ai.bat에서 API 키와 모델을 설정하세요.')


def write_ai_env(key, model, chosen="openai"):
    prefix = "GEMINI" if chosen == "gemini" else "OPENAI"
    path = bot.ROOT / '.env'
    lines = path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []
    lines = [s for s in lines if not re.match(r'^\s*(' + prefix + r'_(API_KEY|MODEL)|AI_PROVIDER)\s*=', s)]
    lines += ['AI_PROVIDER=' + chosen, prefix + '_API_KEY=' + key, prefix + '_MODEL=' + model]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    if os.name != 'nt': path.chmod(0o600)
    os.environ.update({'AI_PROVIDER':chosen,prefix+'_API_KEY':key,prefix+'_MODEL':model})


def setup_ai():
    choice=input('AI 선택: 1=Gemini 무료 등급 사용, 2=OpenAI (기본 1): ').strip() or '1'
    if choice not in ('1','2'):raise ValueError('1 또는 2를 입력하세요.')
    chosen='gemini' if choice=='1' else 'openai'
    if chosen=='gemini':
        print('https://aistudio.google.com/apikey 에서 무료 등급 프로젝트의 키를 준비하세요.')
        print('프로그램은 프로젝트의 결제 등급을 조회할 수 없습니다. 유료 등급이면 요금이 발생할 수 있습니다.')
        print('무료 등급 입력/응답은 Google 제품 개선에 사용될 수 있습니다. 재사용 허용 공개 초록/PDF만 사용하세요.')
        default='' 
    else:
        print('OpenAI API는 별도 과금될 수 있습니다. 개인 API 키와 모델을 입력하세요.')
        default=''
    key=getpass.getpass('API 키 (입력 문자는 표시되지 않음): ').strip()
    if not key or any(c.isspace() for c in key):raise ValueError('API 키를 확인하세요.')
    if chosen=='gemini':
        print('현재 API에서 제공하는 generateContent 지원 모델 목록을 조회합니다...')
        models=ai_provider.list_gemini_models(key)
        if not models:raise RuntimeError('현재 키로 조회한 목록에 지원 텍스트 모델이 없습니다. AI Studio에서 프로젝트/API 상태를 확인하세요.')
        for i, code in enumerate(models,1):print(f'{i}. {code}')
        print('목록에 있다는 사실이 무료 제공 또는 실제 호출 권한을 보장하지는 않습니다.')
        print('https://ai.google.dev/gemini-api/docs/pricing 에서 무료 등급을 확인한 모델을 선택하세요.')
        selected=input('사용할 모델 번호 또는 정확한 모델 ID (취소: Enter): ').strip()
        if not selected:print('설정을 변경하지 않았습니다.');return
        if selected.isdigit() and 1<=int(selected)<=len(models):model=models[int(selected)-1]
        else:model=selected.removeprefix('models/')
        if model not in models:raise ValueError('조회 목록에 있는 모델을 선택하세요.')
    else:
        model=input('모델 ID: ').strip()
    if not re.fullmatch(r'[A-Za-z0-9_.:/-]+',model):raise ValueError('모델 ID를 확인하세요.')
    if input('연결 테스트 요청 1회를 보낼까요? (y/N): ').strip().lower()!='y':
        print('설정을 변경하지 않았습니다.');return
    ai_provider.generate('Reply briefly.','Reply with OK only.',1024,chosen=chosen,key=key,model=model)
    write_ai_env(key,model,chosen)
    print('AI 연결 확인 및 저장 완료. summarize_existing.bat으로 1편부터 확인하세요.')


def prop_text(row, name):
    return ''.join(x.get('plain_text', x.get('text',{}).get('content',''))
                   for x in row.get('properties',{}).get(name,{}).get('rich_text',[]))


def status(page, value):
    # Processing state is local; the user-facing table has only requested columns.
    with sqlite3.connect(bot.ROOT/'state.sqlite3') as db:
        db.execute('CREATE TABLE IF NOT EXISTS analysis_states (page TEXT PRIMARY KEY, value TEXT)')
        db.execute('INSERT OR REPLACE INTO analysis_states VALUES (?,?)',(page,value))



def summary_exists(page, full_only=False):
    cursor = None
    while True:
        path = 'blocks/' + page + '/children?page_size=100'
        if cursor: path += '&start_cursor=' + urllib.parse.quote(cursor)
        result = table.api(path)
        for block in result.get('results',[]):
            if block.get('type') == 'toggle':
                title = ''.join(x.get('plain_text',x.get('text',{}).get('content','')) for x in block['toggle'].get('rich_text',[]))
                if title == fulltext.MARKER or (not full_only and title == MARKER): return True
        if not result.get('has_more'): return False
        cursor = result['next_cursor']


def target_rows(source, limit, upgrade=False):
    selected=[]; cursor=None
    with sqlite3.connect(bot.ROOT/'state.sqlite3') as db:
        db.execute('CREATE TABLE IF NOT EXISTS analysis_states (page TEXT PRIMARY KEY, value TEXT)')
        done={p for p,v in db.execute('SELECT page,value FROM analysis_states') if v in ((fulltext.COMPLETE,'전문 미확보 / 기존 초록 유지',NO_ABSTRACT,'제외 조건 해당 / 분석 보류') if upgrade else (COMPLETE,fulltext.COMPLETE,NO_ABSTRACT,'제외 조건 해당 / 분석 보류'))}
    while len(selected)<limit:
        query={'page_size':100,'sorts':[{'timestamp':'created_time','direction':'ascending'}]}
        if cursor:query['start_cursor']=cursor
        result=table.api('data_sources/'+source+'/query',query)
        for row in result.get('results',[]):
            if row['id'] in done:continue
            if summary_exists(row['id'], full_only=True) if upgrade else summary_exists(row['id']):
                status(row['id'],fulltext.COMPLETE if upgrade else COMPLETE);continue
            selected.append(row)
            if len(selected)>=limit:break
        if not result.get('has_more'):break
        cursor=result['next_cursor']
    return selected


def record(db, page, state):
    db.execute('INSERT OR REPLACE INTO ai_jobs VALUES (?,?)',(page,state));db.commit()


def summarize_one(row, config, db):
    upgrade=config.get("upgrade_fulltext",False)
    page=row['id'];doi=bot.doi_key(prop_text(row,'DOI'))
    if not doi.startswith('10.'):
        return 'DOI 없음: 건너뜀'
    # Recover interrupted status updates and avoid re-generation across PCs.
    if summary_exists(page, full_only=True) if upgrade else summary_exists(page):
        status(page,fulltext.COMPLETE if upgrade else COMPLETE);record(db,page+'|pdf' if upgrade else page,'complete');return '기존 요약 유지'
    job_page=page+'|pdf' if upgrade else page
    job=db.execute('SELECT state FROM ai_jobs WHERE page=?',(job_page,)).fetchone()
    if job and job[0] in ('pending','complete'):
        return '기존 전송 기록 확인 필요: 자동 재전송 보류'
    status(page,'요약 처리 중')
    try:
        item=bot.request_json('https://api.crossref.org/works/'+urllib.parse.quote(doi,safe=''))['message']
        p=bot.normalize(item,'')
        if bot.exclusion(p,config.get('exclude_keywords',[])):
            status(page,'제외 조건 해당 / 분석 보류');return '제외 조건 해당'
        analysis_config=dict(config)
        analysis_config['keep_existing_abstract']=upgrade and summary_exists(page)
        text,basis=bot.analyze(p,analysis_config)
        if basis=='기존 초록 유지':
            status(page,'전문 미확보 / 기존 초록 유지')
            return '전문 미확보: 기존 초록 요약 유지 / '+text
        if basis == '메타데이터만 확보':
            status(page,NO_ABSTRACT);return NO_ABSTRACT
        if basis not in (COMPLETE,fulltext.COMPLETE):raise RuntimeError('AI 분석이 완료되지 않았습니다.')
        if upgrade and basis != fulltext.COMPLETE and summary_exists(page):
            return '전문 미확보: 기존 초록 요약 유지'
        stamp=dt.datetime.now(table.KST).isoformat(timespec='seconds')
        body='생성일시: '+stamp+'\n모델: '+ai_provider.provider() + '/' + ai_provider.model_name()+'\n분석 범위: '+basis+'\n원문: https://doi.org/'+doi+'\n\n'+text
        if len(body)>150000:raise ValueError('요약 길이 한도를 초과했습니다.')
        # Persist the successful model output before any Notion write.
        folder=bot.ROOT/'output'/'ai-summaries';folder.mkdir(parents=True,exist_ok=True)
        (folder/(page+'.json')).write_text(json.dumps({'doi':doi,'page':page,'created_at':stamp,'model':ai_provider.provider() + '/' + ai_provider.model_name(),'analysis':text},ensure_ascii=False,indent=2),encoding='utf-8')
    except (RuntimeError,ValueError,KeyError,OSError) as exc:
        record(db,job_page,'failed')
        status(page,'요약 실패 / 재시도 가능')
        return '요약 실패: '+str(exc)
    # A timeout after append may already have succeeded: don't blindly retry.
    record(db,job_page,'pending')
    toggle={'object':'block','type':'toggle','toggle':{'rich_text':table.rt(fulltext.MARKER if basis==fulltext.COMPLETE else MARKER),
            'children':[bot.block(body[i:i+1800]) for i in range(0,len(body),1800)]}}
    table.api('blocks/'+page+'/children',{'children':[toggle]},method='PATCH')
    record(db,job_page,'complete')
    status(page,basis)
    return '요약 추가 완료'


def backfill(limit, upgrade=False):
    require_ai()
    if not 1<=limit<=20:raise ValueError('한 번에 1~20편을 지정하세요.')
    settings=table.settings()
    if not settings:raise ValueError('먼저 setup_table.bat을 실행하세요.')
    from notion_runner import load_config
    config=load_config()
    config['upgrade_fulltext']=upgrade
    rows=target_rows(settings['data_source_id'],limit,upgrade)
    print(f'이번 대상 {len(rows)}편 / AI 요청 최대 {limit*2}회. 공개 PDF 우선, 미확보 시 초록으로 분석합니다.')
    with sqlite3.connect(bot.ROOT/'state.sqlite3') as db:
        db.execute('CREATE TABLE IF NOT EXISTS ai_jobs (page TEXT PRIMARY KEY, state TEXT)')
        for row in rows:
            print(prop_text(row,'DOI')+': '+summarize_one(row,config,db),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['setup','existing'])
    parser.add_argument('--limit',type=int)
    parser.add_argument('--upgrade',action='store_true')
    parser.add_argument('--retry-unavailable',action='store_true')
    args=parser.parse_args();bot.load_env()
    with single_writer():
        if args.command=='setup':return setup_ai()
        limit=args.limit if args.limit is not None else int(input('이번에 요약할 최대 논문 수 (1~20, 추천 3): '))
        if args.limit is None and input('AI API 사용 비용이 발생할 수 있습니다. 실행할까요? (y/N): ').strip().lower()!='y':return
        if args.retry_unavailable:
            with sqlite3.connect(bot.ROOT/'state.sqlite3') as db:
                db.execute('CREATE TABLE IF NOT EXISTS analysis_states (page TEXT PRIMARY KEY, value TEXT)')
                db.execute('DELETE FROM analysis_states WHERE value IN (?,?)',('전문 미확보 / 기존 초록 유지',NO_ABSTRACT))
        backfill(limit,args.upgrade)


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\n중단했습니다. Notion 전송 중이었다면 다음 실행에서 기존 요약을 확인합니다.')
    except (ValueError,RuntimeError,OSError,KeyError,sqlite3.Error) as exc:
        print('실행 중단: '+str(exc),file=sys.stderr);sys.exit(1)

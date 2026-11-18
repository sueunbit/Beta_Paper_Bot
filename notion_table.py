"""Notion database rows, metadata enrichment, and non-destructive report import."""
import datetime as dt
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import paper_bot as bot

VERSION = '2025-09-03'
KST = dt.timezone(dt.timedelta(hours=9))
FIELDS = {'Read':'checkbox','Paper':'title','Publish Date':'rich_text','Journal':'rich_text',
          'DOI':'rich_text','Corresponding author':'rich_text','Keyword':'rich_text','수집일시':'date'}
SUMMARY_MARKER = 'Paper Bot AI 요약 · 초록 기반'


def api(path, data=None, method=None):
    time.sleep(0.35)
    return bot.request_json('https://api.notion.com/v1/' + path, data,
        {'Authorization': 'Bearer ' + os.environ['NOTION_TOKEN'], 'Notion-Version': VERSION}, method=method)


def settings():
    path = bot.ROOT / 'notion_table.json'
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    parent = os.getenv('NOTION_PARENT_PAGE_ID', '').replace('-', '').lower()
    if data['parent'] != parent:
        raise ValueError('부모 페이지가 변경되었습니다. 기존 notion_table.json을 백업한 후 표를 다시 연결하세요.')
    return data


def rt(value):
    text = str(value or '')[:18000]
    return [{'type':'text','text':{'content':text[i:i+1800]}} for i in range(0,len(text),1800)]


def setup_table():
    from notion_runner import credentials, check_connection
    token, parent = credentials()
    check_connection(token, parent)
    current = settings()
    if current:
        from migrate_table import migrate
        migrate(current)
        print('기존 논문 표를 사용합니다: ' + current['url'])
        return
    # Recover a database created before a timeout without creating another.
    matches=[];cursor=None
    while True:
        path='blocks/'+parent+'/children?page_size=100'
        if cursor:path+='&start_cursor='+urllib.parse.quote(cursor)
        response=api(path)
        matches.extend(b['id'] for b in response.get('results',[]) if b.get('type')=='child_database' and b.get('child_database',{}).get('title') in ('Paper Bot','논문 수집함 · Paper Bot','논문 수집함'))
        if not response.get('has_more'):break
        cursor=response['next_cursor']
    if len(matches)>1:raise ValueError('같은 이름의 표가 여러 개 있습니다. 하나만 남기거나 이름을 구분한 후 다시 실행하세요.')
    if matches:
        result=api('databases/'+matches[0])
    else:
        result=api('databases', {'parent':{'type':'page_id','page_id':parent},
            'title':rt('Paper Bot'),'is_inline':True,
            'initial_data_source':{'properties':{k:{v:{}} for k,v in FIELDS.items()}}})
    sources=result.get('data_sources',[])
    if len(sources)!=1:raise ValueError('표의 데이터 소스가 하나가 아닙니다. 생성된 표를 확인하세요.')
    source=api('data_sources/'+sources[0]['id'])
    data={'parent':parent,'database_id':result['id'],'data_source_id':sources[0]['id'], 'url':result.get('url','')}
    path=bot.ROOT/'notion_table.json'
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    from migrate_table import migrate
    migrate(data)
    print('표 연결 완료: '+data['url'])


def safe_url(url):
    return url if urllib.parse.urlsplit(url or '').scheme in ('http','https') else None


def row_payload(p, source):
    doi=bot.doi_key(p['doi'])
    props={'Read':{'checkbox':False},'Paper':{'title':rt(p['title'][:1800])},
        'Publish Date':{'rich_text':rt(p.get('date',''))},'Journal':{'rich_text':rt(p.get('journal',''))},
        'DOI':{'rich_text':[{'type':'text','text':{'content':doi,'link':{'url':'https://doi.org/'+doi}}}]},
        'Corresponding author':{'rich_text':rt('; '.join(p.get('corresponding_authors',[])) or '확인 필요')},
        'Keyword':{'rich_text':rt('; '.join(p.get('keywords',[])))},
        '수집일시':{'date':{'start':p['collected_at']}}}
    mapping='\n'.join(p.get('author_affiliations',[])) or '저자별 소속 미제공'
    info='원문: https://doi.org/'+doi+'\n저자별 소속\n'+mapping+'\n수집시각 근거: '+p.get('collected_basis','검색 API 응답 수신 시각')
    children=[bot.block(info[i:i+1800]) for i in range(0,min(len(info),60000),1800)]
    text=p.get('analysis','')
    if p.get('basis') in ('초록 기반 AI 분석 / 전문 미확인','공개 PDF 기반 AI 분석'):
        children.append({'object':'block','type':'toggle','toggle':{'rich_text':rt('Paper Bot AI 요약 · 공개 PDF 기반' if p.get('basis')=='공개 PDF 기반 AI 분석' else SUMMARY_MARKER),
            'children':[bot.block(text[i:i+1800]) for i in range(0,min(len(text),100000),1800)]}})
    else:
        children.append(bot.block(p.get('basis','')+'\n'+text[:1800]))
    return {'parent':{'type':'data_source_id','data_source_id':source},'properties':props,'children':children}


def publish(papers, out):
    config=settings()
    if not config:raise ValueError('먼저 setup_table.bat을 실행하세요.')
    source=config['data_source_id'];scope='table:'+source
    results=[]
    with sqlite3.connect(bot.ROOT/'state.sqlite3') as db:
        db.execute('CREATE TABLE IF NOT EXISTS posted (parent TEXT, doi TEXT, status TEXT, url TEXT, PRIMARY KEY(parent,doi))')
        for p in papers:
            p.setdefault('collected_at',dt.datetime.now(KST).isoformat(timespec='seconds'))
            p.setdefault('collected_basis','표 저장 준비 시각')
            key=bot.doi_key(p['doi'])
            # Query server first; never overwrite checkbox, collection date, or user edits.
            found=api('data_sources/'+source+'/query',{'filter':{'property':'DOI','rich_text':{'equals':key}},'page_size':1})
            if found.get('results'):
                url=found['results'][0].get('url','')
                db.execute('INSERT OR REPLACE INTO posted VALUES (?,?,?,?)',(scope,key,'posted',url));db.commit()
                results.append({'doi':key,'status':'기존 행 유지','url':url});continue
            row=db.execute('SELECT status FROM posted WHERE parent=? AND doi=?',(scope,key)).fetchone()
            if row:
                results.append({'doi':key,'status':'로컬 기록 있음: '+row[0]});continue
            db.execute('INSERT INTO posted VALUES (?,?,?,?)',(scope,key,'pending: Notion 확인 필요',''));db.commit()
            try:
                response=api('pages',row_payload(p,source))
                url=response.get('url','')
                db.execute('UPDATE posted SET status=?,url=? WHERE parent=? AND doi=?',('posted',url,scope,key));db.commit()
                results.append({'doi':key,'status':'posted','url':url})
            except Exception:
                results.append({'doi':key,'status':'전송 결과 불확실: Notion 확인 필요'})
                (out/'notion-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
                raise
    (out/'notion-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    return results


def import_reports():
    if not settings():raise ValueError('먼저 setup_table.bat을 실행하세요.')
    candidates={}
    for path in sorted((bot.ROOT/'output').glob('*/report.json')):
        report=json.loads(path.read_text(encoding='utf-8'))
        if '샘플' in report.get('mode',''):continue
        for p in report.get('papers',[]):
            doi=bot.doi_key(p.get('doi',''))
            if not doi.startswith('10.'):continue
            stamp=p.get('collected_at') or report.get('created_at')
            if doi not in candidates or (stamp or '') < candidates[doi][1]:candidates[doi]=(p,stamp or '')
    out=bot.ROOT/'output'/'table-import';out.mkdir(parents=True,exist_ok=True)
    for doi,(old,stamp) in candidates.items():
        item=bot.request_json('https://api.crossref.org/works/'+urllib.parse.quote(doi,safe=''))['message']
        p=bot.normalize(item,'');p['keywords']=old.get('keywords',[])
        if bot.exclusion(p,[]):continue
        p['basis']=old.get('basis','AI 미실행');p['analysis']=old.get('analysis','')
        if stamp:
            p['collected_at']=dt.datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(KST).isoformat(timespec='seconds')
            p['collected_basis']=old.get('collected_basis','기존 로컬 보고서 생성 시각 (원래 수집시각 대용)')
        print(json.dumps(publish([p],out),ensure_ascii=False))
    print('기존 로컬 보고서 가져오기 완료. 기존 Notion 개별 페이지는 유지됩니다.')


if __name__=='__main__':
    bot.load_env()
    try:
        if len(sys.argv)>1 and sys.argv[1]=='import':import_reports()
        else:setup_table()
    except (ValueError,RuntimeError,OSError,KeyError,sqlite3.Error) as exc:
        print('실행 중단: '+str(exc));sys.exit(1)

"""Rename properties in place, preserve rows, and back up removed metadata."""
import datetime as dt
import json
import sqlite3
import sys
import urllib.parse
import paper_bot as bot
import notion_table as table
from runtime_lock import single_writer

RENAMES={'읽음':'Read','논문':'Paper','발행일':'Publish Date','저널':'Journal','키워드':'Keyword'}
REMOVE={'PDF','PDF 상태','저자','제1저자','마지막 저자','소속기관','연구실·그룹','수집시각 근거','원문','서울대 접속','분석 상태'}
ARCHIVE='Paper Bot · 이전 표 정보'


def plan(properties):
    result={}
    for old,new in RENAMES.items():
        if old in properties:
            if new in properties:raise ValueError(f'{old}와 {new} 열이 함께 있습니다. 중복 열을 확인하세요.')
            if properties[old].get('type')!=table.FIELDS[new]:raise ValueError(f'{old} 열 유형을 확인하세요.')
            result[properties[old]['id']]={'name':new}
    for name,kind in table.FIELDS.items():
        if name in properties:
            if properties[name].get('type')!=kind:raise ValueError(f'{name} 열 유형을 확인하세요.')
        elif name not in RENAMES.values():
            result[name]={kind:{}}
        elif not any(old in properties for old,new in RENAMES.items() if new==name):
            raise ValueError(f'{name}에 대응하는 기존 열이 없습니다. 임의로 빈 열을 만들지 않고 중단합니다.')
    for name in REMOVE:
        if name in properties:result[properties[name]['id']]=None
    return result


def text_prop(value):
    kind=value.get('type')
    if kind in ('rich_text','title'):
        return ''.join(x.get('plain_text',x.get('text',{}).get('content','')) for x in value.get(kind,[]))
    if kind=='url':return value.get('url') or ''
    return ''


def pages(source):
    rows=[];cursor=None
    while True:
        query={'page_size':100}
        if cursor:query['start_cursor']=cursor
        result=table.api('data_sources/'+source+'/query',query)
        rows.extend(result.get('results',[]))
        if not result.get('has_more'):return rows
        cursor=result['next_cursor']


def has_archive(page):
    cursor=None
    while True:
        path='blocks/'+page+'/children?page_size=100'
        if cursor:path+='&start_cursor='+urllib.parse.quote(cursor,safe='')
        result=table.api(path)
        for block in result.get('results',[]):
            if block.get('type')=='toggle' and text_prop({'type':'rich_text',**block['toggle']})==ARCHIVE:return True
        if not result.get('has_more'):return False
        cursor=result['next_cursor']


def preserve_row(row):
    # Keep the old analysis result and metadata inside the existing paper page.
    values={k:text_prop(v) for k,v in row.get('properties',{}).items() if k in REMOVE}
    state=values.get('분석 상태','')
    if state:
        from ai_tools import status
        status(row['id'],state)
    content='\n'.join(k+': '+v for k,v in values.items() if v)
    if not content or has_archive(row['id']):return
    block={'object':'block','type':'toggle','toggle':{'rich_text':table.rt(ARCHIVE),
        'children':[bot.block(content[i:i+1800]) for i in range(0,len(content),1800)]}}
    table.api('blocks/'+row['id']+'/children',{'children':[block]},method='PATCH')


def ordered_view(config, properties):
    # Views use the current API version while the data-source schema remains 2025-09-03.
    import os
    def api(path,data=None,method=None):
        return bot.request_json('https://api.notion.com/v1/'+path,data,
            {'Authorization':'Bearer '+os.environ['NOTION_TOKEN'],'Notion-Version':'2026-03-11'},method=method)
    query='views?database_id='+config['database_id']
    views=[];cursor=None
    while True:
        existing=api(query+('&start_cursor='+urllib.parse.quote(cursor,safe='') if cursor else ''))
        views.extend(existing.get('results',[]))
        if not existing.get('has_more'):break
        cursor=existing['next_cursor']
    matches=[x for x in views if x.get('name')=='Paper Bot' and x.get('type')=='table']
    view_config={'type':'table','properties':[{'property_id':properties[name]['id'],'visible':True,
         'width':420 if name=='Paper' else 90 if name=='Read' else 180,'wrap':True} for name in table.FIELDS]}
    if matches:
        result=api('views/'+matches[0]['id'],{'configuration':view_config},method='PATCH')
    else:
        result=api('views',{'database_id':config['database_id'],'data_source_id':config['data_source_id'],
            'name':'Paper Bot','type':'table','configuration':view_config,'position':{'type':'start'}})
    return result.get('id')


def migrate(config):
    source=config['data_source_id']
    schema=table.api('data_sources/'+source)
    changes=plan(schema['properties'])
    if changes:
        rows=pages(source)
        backup=bot.ROOT/'output'/'schema-backups';backup.mkdir(parents=True,exist_ok=True)
        path=backup/(dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json')
        path.write_text(json.dumps({'config':config,'schema':schema,'rows':rows},ensure_ascii=False,indent=2),encoding='utf-8')
        print('변경 전 열/행 백업: '+str(path))
        for row in rows:preserve_row(row)
        # IDs retain the values, checkboxes, page IDs and existing summaries.
        table.api('data_sources/'+source,{'title':table.rt('Paper Bot'),'properties':changes},method='PATCH')
        if 'Corresponding author' not in schema['properties']:
            for row in rows:
                table.api('pages/'+row['id'],{'properties':{'Corresponding author':{'rich_text':table.rt('확인 필요')}}},method='PATCH')
    table.api('databases/'+config['database_id'],{'title':table.rt('Paper Bot')},method='PATCH')
    final=table.api('data_sources/'+source)
    if any(final['properties'].get(k,{}).get('type')!=v for k,v in table.FIELDS.items()):
        raise RuntimeError('변경 후 열 확인 실패. 백업을 유지하고 오류를 확인하세요.')
    try:
        ordered_view(config,final['properties'])
        print('Paper Bot 표 보기와 열 순서를 적용했습니다.')
    except RuntimeError as exc:
        print('이름/열 변경은 완료했으나 보기 순서 적용은 실패했습니다: '+str(exc))
        print('Notion에서 열을 이 순서로 정렬하세요: '+', '.join(table.FIELDS))
    print('Paper Bot 표 준비 완료. 기존 페이지·읽음 체크·수집일시는 유지됩니다.')


if __name__=='__main__':
    bot.load_env()
    try:
        with single_writer():
            config=table.settings()
            if not config:raise ValueError('기존 표 연결이 없습니다. setup_table.bat을 먼저 실행하세요.')
            migrate(config)
    except (ValueError,RuntimeError,OSError,KeyError,sqlite3.Error) as exc:
        print('실행 중단: '+str(exc));sys.exit(1)

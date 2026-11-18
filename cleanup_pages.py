"""Remove only requested exact boilerplate, preserving other block text and formatting."""
import copy
import datetime as dt
import json
import urllib.parse
import paper_bot as bot
import notion_table as table
from runtime_lock import single_writer

PHRASES=(
'마지막 저자가 교신저자 또는 연구책임자라는 의미는 아닙니다.',
'연구실·그룹은 소속 문자열에 명시된 경우만 표시합니다.',
'PDF 링크의 실제 접근 여부는 로그인/구독에 따라 다릅니다.',
'AI 분석은 아직 연결하지 않았습니다. 연구 내용·결과·한계는 원문에서 확인하세요.',
'교신저자는 저자 순서로 추정하지 않습니다.')


def cleaned_rich_text(items):
    # Detect phrases even when Notion split the sentence over formatted spans.
    texts=[x.get('text',{}).get('content',x.get('plain_text','')) for x in items]
    joined=''.join(texts);remove=set()
    for phrase in PHRASES:
        start=0
        while True:
            start=joined.find(phrase,start)
            if start<0:break
            remove.update(range(start,start+len(phrase)));start+=len(phrase)
    if not remove:return None
    result=[];offset=0
    for item,text in zip(items,texts):
        value=copy.deepcopy(item)
        if value.get('type')=='text':
            value['text']['content']=''.join(c for i,c in enumerate(text,offset) if i not in remove)
        offset+=len(text)
        value.pop('plain_text',None);value.pop('href',None)
        if value.get('type')!='text' or value['text']['content']:result.append(value)
    return result


def clean_page(page,folder):
    cursor=None;count=0
    while True:
        path='blocks/'+page+'/children?page_size=100'
        if cursor:path+='&start_cursor='+urllib.parse.quote(cursor)
        response=table.api(path)
        for block in response.get('results',[]):
            kind=block.get('type')
            if kind in ('paragraph','bulleted_list_item','numbered_list_item','quote','callout','toggle'):
                rich=cleaned_rich_text(block[kind].get('rich_text',[]))
                if rich is not None:
                    (folder/(block['id']+'.json')).write_text(json.dumps(block,ensure_ascii=False,indent=2),encoding='utf-8')
                    table.api('blocks/'+block['id'],{kind:{'rich_text':rich}},method='PATCH');count+=1
            if block.get('has_children'):count+=clean_page(block['id'],folder)
        if not response.get('has_more'):return count
        cursor=response['next_cursor']


def main():
    bot.load_env()
    with single_writer():
        settings=table.settings()
        if not settings:raise ValueError('setup_table.bat을 먼저 실행하세요.')
        folder=bot.ROOT/'output'/'cleanup-backups'/dt.datetime.now().strftime('%Y%m%d-%H%M%S')
        folder.mkdir(parents=True,exist_ok=True)
        cursor=None;count=0
        while True:
            query={'page_size':100}
            if cursor:query['start_cursor']=cursor
            response=table.api('data_sources/'+settings['data_source_id']+'/query',query)
            for row in response.get('results',[]):count+=clean_page(row['id'],folder)
            if not response.get('has_more'):break
            cursor=response['next_cursor']
        # Also handle older standalone pages under the configured parent.
        if settings.get('parent'):count+=clean_page(settings['parent'],folder)
        print(f'완료: {count}개 블록의 지정 안내 문구 제거. 원본 백업: {folder}')

if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError,OSError,KeyError) as exc:
        print('정리 중단: '+str(exc));raise SystemExit(1)

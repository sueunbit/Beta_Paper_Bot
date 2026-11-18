"""Optional email enables Unpaywall discovery in addition to Crossref links."""
import os
import re
import paper_bot as bot
from runtime_lock import single_writer


def main():
    bot.load_env()
    with single_writer():
        print('공개 PDF 검색에 사용할 이메일을 입력하세요. Unpaywall API에 전달됩니다.')
        print('빈칸은 현재 설정 유지. 이 기능은 학교 로그인/구독 자료를 사용하지 않습니다.')
        email=input('이메일: ').strip()
        if not email:return
        if not re.fullmatch(r'[^\s@=]+@[^\s@=]+\.[^\s@=]+',email):raise ValueError('이메일 형식을 확인하세요.')
        path=bot.ROOT/'.env'
        lines=path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []
        lines=[s for s in lines if not re.match(r'^\s*UNPAYWALL_EMAIL\s*=',s)]
        path.write_text('\n'.join(lines+['UNPAYWALL_EMAIL='+email])+'\n',encoding='utf-8')
        if os.name!='nt':path.chmod(0o600)
        print('저장 완료. Gemini 연결 후 upgrade_fulltext.bat으로 기존 논문 1편부터 실행하세요.')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,RuntimeError) as exc:print('설정 중단: '+str(exc));raise SystemExit(1)

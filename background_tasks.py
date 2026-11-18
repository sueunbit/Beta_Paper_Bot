"""Windows Task Scheduler add-on for Paper Bot beta.6. Standard library only."""
import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'output' / 'scheduler'
SETTINGS = DATA / 'settings.json'
NS = 'http://schemas.microsoft.com/windows/2004/02/mit/task'


def ps(script, extra_env=None):
    if os.name != 'nt':raise RuntimeError('Windows 10/11에서 실행하세요.')
    env=os.environ.copy();env.update(extra_env or {})
    exe=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32'/'WindowsPowerShell'/'v1.0'/'powershell.exe'
    result=subprocess.run([str(exe),'-NoProfile','-NonInteractive','-Command',
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); $ErrorActionPreference='Stop'; "+script],
        env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
    if result.returncode:raise RuntimeError(result.stderr.strip() or result.stdout.strip() or '작업 스케줄러 명령 실패')
    return result.stdout.strip()


def identity():
    return ps('[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value')


def task_name(sid):
    seed=str(ROOT).casefold()+'|'+sid
    return 'PaperBot_'+hashlib.sha256(seed.encode()).hexdigest()[:16]


def parse_times(value):
    times=sorted(set(x.strip() for x in value.split(',')))
    if not 1<=len(times)<=8 or any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',x) for x in times):
        raise ValueError('24시간 형식 HH:MM을 입력하세요. 쉼표로 최대 8개 시각을 지정할 수 있습니다.')
    return times


def validate_settings(c):
    parse_times(','.join(c['times']))
    if type(c['ai']) is not bool:raise ValueError('AI 모드 설정 오류')
    for key,low,high in [('minutes',1,120),('ai_limit',1,100)]:
        if type(c[key]) is not int or not low<=c[key]<=high:raise ValueError(key+' 설정 범위를 확인하세요.')
    return c


def build_xml(c, sid, executable, today=None):
    validate_settings(c)
    today=today or dt.date.today()
    ET.register_namespace('',NS)
    def node(parent,name,text=None,**attrs):
        e=ET.SubElement(parent,'{'+NS+'}'+name,attrs)
        if text is not None:e.text=str(text)
        return e
    task=ET.Element('{'+NS+'}Task',{'version':'1.2'})
    info=node(task,'RegistrationInfo');node(info,'Description','Paper Bot local scheduled collection; '+str(ROOT))
    triggers=node(task,'Triggers')
    for clock in c['times']:
        trigger=node(triggers,'CalendarTrigger')
        node(trigger,'StartBoundary',today.isoformat()+'T'+clock+':00')
        node(trigger,'Enabled','true')
        daily=node(trigger,'ScheduleByDay');node(daily,'DaysInterval','1')
    principals=node(task,'Principals');principal=node(principals,'Principal',id='Author')
    node(principal,'UserId',sid);node(principal,'LogonType','InteractiveToken');node(principal,'RunLevel','LeastPrivilege')
    settings=node(task,'Settings')
    for name,value in [('MultipleInstancesPolicy','IgnoreNew'),('DisallowStartIfOnBatteries','false'),
        ('StopIfGoingOnBatteries','false'),('AllowHardTerminate','false'),('StartWhenAvailable','true'),
        ('RunOnlyIfNetworkAvailable','false'),('AllowStartOnDemand','true'),('Enabled','true'),
        ('Hidden','false'),('WakeToRun','false'),('ExecutionTimeLimit','PT0S')]:node(settings,name,value)
    actions=node(task,'Actions',Context='Author');action=node(actions,'Exec')
    node(action,'Command',str(executable))
    node(action,'Arguments',subprocess.list2cmdline([str(ROOT/'background_tasks.py'),'worker']))
    node(action,'WorkingDirectory',str(ROOT))
    return ET.tostring(task,encoding='unicode',xml_declaration=False)


def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def preflight(ai):
    for name in ('paper_bot.py','notion_runner.py','notion_table.py','runtime_lock.py'):
        if not (ROOT/name).exists():raise ValueError('추가 파일을 기존 Paper Bot 프로그램 폴더에 넣으세요: '+name+' 없음')
    import paper_bot as bot
    import notion_runner as runner
    import notion_table
    import ai_provider
    bot.load_env();runner.credentials();runner.load_config()
    if not notion_table.settings():raise ValueError('먼저 04_create_paper_table.bat을 실행하세요.')
    if ai and not ai_provider.ready():raise ValueError('먼저 06_setup_ai_optional.bat으로 AI를 연결하세요.')


def install():
    if os.name!='nt':raise RuntimeError('Windows에서 실행하세요.')
    print('매일 지정 시각에 1회 검색합니다. Windows 로그인 상태(화면 잠금 가능)가 필요합니다.')
    print('시각은 Windows 시간대 기준. 종료/로그아웃 중에는 실행하지 않습니다.')
    times=parse_times(input('매일 실행 시각, 예 09:00 또는 09:00,18:00 [09:00]: ').strip() or '09:00')
    mode=input('1=정보만 수집, 2=AI 요약 포함 [1]: ').strip() or '1'
    if mode not in ('1','2'):raise ValueError('1 또는 2를 입력하세요.')
    minutes=int(input('1회 작업의 새 요청 시작 제한 시간(분, 1~120) [15]: ').strip() or '15')
    limit=int(input('1회 실행의 AI 요청 최대 횟수(1~100) [3]: ').strip() or '3') if mode=='2' else 3
    c=validate_settings({'times':times,'ai':mode=='2','minutes':minutes,'ai_limit':limit})
    preflight(c['ai'])
    exe=Path(sys.executable).with_name('pythonw.exe')
    if not exe.exists():raise ValueError('pythonw.exe를 찾지 못했습니다. Windows Python 설치를 확인하세요.')
    sid=identity();name=task_name(sid);c.update(task_name=name,folder=str(ROOT),pythonw=str(exe))
    print('등록 내용: 매일 '+', '.join(times)+' / '+('AI 요약 포함' if c['ai'] else '정보만 수집'))
    if c['ai']:print('설정된 API 요금/한도가 적용됩니다. 요청 한도는 매 실행마다 초기화됩니다.')
    if input('이 설정으로 예약을 등록/변경할까요? (y/N): ').strip().lower()!='y':return
    from runtime_lock import single_writer
    with single_writer():
        DATA.mkdir(parents=True,exist_ok=True)
        previous=SETTINGS.read_bytes() if SETTINGS.exists() else None
        xml=DATA/'task-definition.xml';xml.write_text(build_xml(c,sid,exe),encoding='utf-8')
        atomic_json(SETTINGS,c)
        try:
            ps("Register-ScheduledTask -TaskName $env:PAPERBOT_TASK -Xml (Get-Content -LiteralPath $env:PAPERBOT_XML -Raw -Encoding UTF8) -Force | Out-Null",
                {'PAPERBOT_TASK':name,'PAPERBOT_XML':str(xml)})
        except Exception:
            if previous is None:SETTINGS.unlink(missing_ok=True)
            else:SETTINGS.write_bytes(previous)
            raise
    print('예약 등록 완료. 이 창은 닫아도 됩니다. 11번으로 즉시 시험 실행하고 12번에서 상태/로그를 확인하세요.')


def current_task():
    return task_name(identity())


def start():
    if not SETTINGS.exists():raise ValueError('10번으로 예약을 먼저 등록하세요.')
    c=validate_settings(json.loads(SETTINGS.read_text(encoding='utf-8')))
    preflight(c['ai'])
    print('저장된 모드로 지금 실행합니다. AI 모드라면 API 요청이 발생합니다.')
    if input('실행할까요? (y/N): ').strip().lower()!='y':return
    ps('Start-ScheduledTask -TaskName $env:PAPERBOT_TASK',{'PAPERBOT_TASK':current_task()})
    print('실행 요청 완료. 완료 여부는 12번의 작업 상태와 최신 로그에서 확인하세요.')


def status():
    name=current_task()
    try:
        print(ps("$t=Get-ScheduledTask -TaskName $env:PAPERBOT_TASK; $i=$t | Get-ScheduledTaskInfo; [pscustomobject]@{Task=$t.TaskName;State=[string]$t.State;LastRun=$i.LastRunTime;NextRun=$i.NextRunTime;Result=$i.LastTaskResult} | Format-List | Out-String",{'PAPERBOT_TASK':name}))
    except RuntimeError as exc:
        print('예약 조회 실패(미등록/해제 여부 확인): '+str(exc))
    if SETTINGS.exists():print(SETTINGS.read_text(encoding='utf-8'))
    latest=DATA/'latest.json'
    if latest.exists():print('최근 봇 실행 기록:\n'+latest.read_text(encoding='utf-8'))
    print('Result 0은 프로세스 정상 종료입니다. 개별 논문 성공 여부는 로그와 Notion에서 확인하세요.')
    print('로그 폴더: '+str(DATA))
    DATA.mkdir(parents=True,exist_ok=True);os.startfile(str(DATA))


def remove():
    print('이 폴더·현재 사용자에 등록된 예약만 삭제합니다. 실행 중 작업은 완료까지 계속될 수 있습니다.')
    if input('예약을 해제할까요? (y/N): ').strip().lower()!='y':return
    ps('Unregister-ScheduledTask -TaskName $env:PAPERBOT_TASK -Confirm:$false',{'PAPERBOT_TASK':current_task()})
    print('예약 해제 완료. 기존 논문·로그·연결 설정은 유지됩니다.')


def worker():
    # pythonw has no console streams; capture everything before importing bot modules.
    DATA.mkdir(parents=True,exist_ok=True)
    stamp=dt.datetime.now().astimezone().isoformat(timespec='seconds')
    path=DATA/('run-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+str(os.getpid())+'.log')
    outcome='failed';code=1
    with path.open('w',encoding='utf-8',buffering=1) as log,open(os.devnull,'r') as empty:
        with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            old_stdin=sys.stdin;sys.stdin=empty
            try:
                print('Started: '+stamp,flush=True)
                c=validate_settings(json.loads(SETTINGS.read_text(encoding='utf-8')))
                preflight(c['ai'])
                import time
                import notion_runner as runner
                from runtime_lock import single_writer
                with single_writer():
                    runner.check_connection(*runner.credentials())
                    budget={'remaining':c['ai_limit']} if c['ai'] else None
                    runner.cycle(runner.load_config(),time.monotonic()+c['minutes']*60,not c['ai'],budget)
                outcome='completed_check_log';code=0
                print('검색 1회 처리 종료. 개별 전송/요약 결과는 위 로그를 확인하세요.',flush=True)
            except Exception:
                traceback.print_exc()
            finally:
                sys.stdin=old_stdin
                print('Finished: '+dt.datetime.now().astimezone().isoformat(timespec='seconds'),flush=True)
    atomic_json(DATA/'latest.json',{'started':stamp,'finished':dt.datetime.now().astimezone().isoformat(timespec='seconds'),'outcome':outcome,'exit_code':code,'log':str(path)})
    return code


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['install','start','status','remove','worker'])
    command=parser.parse_args().command
    if command=='worker':return worker()
    try:
        {'install':install,'start':start,'status':status,'remove':remove}[command]()
        return 0
    except (ValueError,RuntimeError,OSError,KeyError,subprocess.TimeoutExpired) as exc:
        print('작업 실패: '+str(exc));return 1

if __name__=='__main__':raise SystemExit(main())

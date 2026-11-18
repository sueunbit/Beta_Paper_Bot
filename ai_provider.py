"""Explicit provider selection: no automatic paid fallback."""
import base64
import json
import os
import re
import urllib.parse
import paper_bot as bot


def provider():
    name=os.getenv('AI_PROVIDER','openai').strip().lower()
    if name not in ('openai','gemini'):raise ValueError('AI_PROVIDER는 gemini 또는 openai여야 합니다.')
    return name


def model_name():
    return os.getenv('GEMINI_MODEL','') if provider()=='gemini' else os.getenv('OPENAI_MODEL','')


def ready():
    prefix='GEMINI' if provider()=='gemini' else 'OPENAI'
    return bool(os.getenv(prefix+'_API_KEY') and model_name())


def list_gemini_models(key):
    models={}; page=None
    while True:
        url='https://generativelanguage.googleapis.com/v1beta/models?pageSize=100'
        if page:url+='&pageToken='+urllib.parse.quote(page,safe='')
        result=bot.request_json(url,headers={'x-goog-api-key':key})
        for item in result.get('models',[]):
            code=item.get('name','').removeprefix('models/')
            if (code.startswith('gemini-') and 'generateContent' in item.get('supportedGenerationMethods',[])
                and not any(x in code.lower() for x in ('image','tts','audio','live','robotics','computer-use'))):
                models[code]=item
        page=result.get('nextPageToken')
        if not page:break
    return sorted(models)


def generate(instructions, text, max_tokens=3000, chosen=None, key=None, model=None, pdf_bytes=None):
    name=chosen or provider()
    model=model or model_name()
    key=key or os.getenv(('GEMINI' if name=='gemini' else 'OPENAI')+'_API_KEY')
    if not key or not model:raise ValueError('setup_ai.bat에서 API를 연결하세요.')
    if pdf_bytes and name!='gemini':raise ValueError('이 버전의 PDF 분석은 Gemini에서 지원합니다.')
    if name=='gemini':
        parts=[{'text':text}]
        if pdf_bytes:parts.append({'inlineData':{'mimeType':'application/pdf','data':base64.b64encode(pdf_bytes).decode('ascii')}})
        if not re.fullmatch('[A-Za-z0-9_.-]+',model):raise ValueError('Gemini 모델 ID를 확인하세요.')
        config={'maxOutputTokens':max_tokens}
        if model.startswith('gemini-2.5-flash'):
            config['thinkingConfig']={'thinkingBudget':0}
        result=bot.request_json('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent',
            {'systemInstruction':{'parts':[{'text':instructions}]},
             'contents':[{'role':'user','parts':parts}],'generationConfig':config},
            {'x-goog-api-key':key})
        candidates=result.get('candidates',[])
        if not candidates or candidates[0].get('finishReason')!='STOP':
            raise RuntimeError('Gemini 응답 미완료/차단. 출력 한도와 요청 내용을 확인하세요.')
        answer='\n'.join(p.get('text','') for p in candidates[0].get('content',{}).get('parts',[]) if not p.get('thought'))
    elif name=='openai':
        result=bot.request_json('https://api.openai.com/v1/responses',
            {'model':model,'instructions':instructions,'input':text,'max_output_tokens':max_tokens,'store':False},
            {'Authorization':'Bearer '+key})
        if result.get('status')!='completed':raise RuntimeError('OpenAI 응답 미완료. 출력 한도와 모델을 확인하세요.')
        answer='\n'.join(c.get('text','') for item in result.get('output',[]) if item.get('type')=='message'
                         for c in item.get('content',[]) if c.get('type')=='output_text')
    else:raise ValueError('지원하지 않는 AI 공급자입니다.')
    if not answer.strip():raise RuntimeError('AI 텍스트 응답이 없습니다.')
    return answer

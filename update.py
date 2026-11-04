import json, os, re, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from collect import collect
ROOT = Path(__file__).parent
CATEGORIES = {'Concerti', 'Cultura e mostre', 'Fiere', 'Serate'}
def valid(event):
    try:
        datetime.strptime(event['date'], '%Y-%m-%d')
        if event.get('endDate'):
            datetime.strptime(event['endDate'], '%Y-%m-%d')
            if event['endDate'] < event['date']: return False
        return (event['category'] in CATEGORIES and event['url'].startswith('https://') and all(isinstance(event[k], str) and 0 < len(event[k]) <= 300 for k in ['id','title','venue','address','source']) and (event['price'] is None or isinstance(event['price'], (int,float)) and event['price'] >= 0) and (event['time'] is None or re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',event['time'])))
    except (KeyError, ValueError, TypeError): return False
def request(url):
    headers={'Accept':'application/vnd.github+json','Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'User-Agent':'Muviti-events'}
    return json.load(urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=30))
def fields(body):
    result={}
    for match in re.finditer(r'^### (.+)\n+([\s\S]*?)(?=\n### |\Z)',body or '',re.M): result[match[1]]=match[2].strip()
    return result
def issue_event(issue, owner):
    if issue.get('user',{}).get('login') != owner or issue.get('state') != 'open' or 'pull_request' in issue: return None
    f=fields(issue.get('body'))
    try:
        price=f['Prezzo in euro']; time=f['Orario']; note=f.get('Nota prezzo','')
        event={'id':'manual-'+str(issue['number']),'title':f['Nome evento'],'date':f['Data'],'time':None if time in ('_No response_','') else time,'category':f['Categoria'],'venue':f['Luogo'],'address':f['Indirizzo completo'],'price':None if price in ('_No response_','') else float(price.replace(',','.')),'source':'Inserito dal proprietario','url':f['Fonte o sito organizzatore']}
        if note and note != '_No response_': event['priceNote']=note[:500]
        return event if valid(event) else None
    except (KeyError, ValueError): return None
def main():
    repo=os.environ['GITHUB_REPOSITORY']; owner=repo.split('/')[0]
    now=datetime.now(ZoneInfo('Europe/Rome')); today=now.date().isoformat()
    entries=json.loads((ROOT/'manual.json').read_text())
    for page in range(1,4):
        issues=request(f'https://api.github.com/repos/{repo}/issues?state=open&per_page=100&page={page}')
        entries.extend(e for issue in issues if (e:=issue_event(issue,owner)))
        if len(issues)<100: break
    old=json.loads((ROOT/'events.json').read_text()) if (ROOT/'events.json').exists() else {}
    sources=json.loads((ROOT/'sources.json').read_text())
    automatic,statuses=collect(sources,today,old.get('events',[]))
    entries.extend(automatic)
    events={e['id']:e for e in entries if valid(e) and e.get('endDate',e['date'])>=today}
    output={'updatedAt':now.isoformat(),'automaticSourcesActive':bool(sources),'sources':statuses,'events':sorted(events.values(),key=lambda e:(e['date'],e['time'] or ''))[:200]}
    (ROOT/'events.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__': main()

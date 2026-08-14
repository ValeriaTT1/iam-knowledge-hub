#!/usr/bin/env python3
import datetime as dt, html, json, re, sys, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from email.utils import parsedate_to_datetime

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; ARCHIVE=DATA/"archive"; OUT=DATA/"news.json"
MAX_ITEMS=24; LOOKBACK_DAYS=8
SOURCES=[("Cloud Security Alliance","cloudsecurityalliance.org"),("Gartner","gartner.com"),("Identity Defined Security Alliance","idsalliance.org"),("KuppingerCole","kuppingercole.com"),("Microsoft Security","microsoft.com"),("Okta","okta.com"),("Wiz","wiz.io")]
SOURCE_WEIGHT={"Gartner":4,"KuppingerCole":4,"Cloud Security Alliance":3,"Identity Defined Security Alliance":3,"Microsoft Security":3,"Okta":3,"Wiz":3}
SECTION_RULES={
"Latest IAM Trends":["trend","future of identity","identity strategy","zero trust","identity fabric","agentic ai","ai agent","non-human identity","machine identity","passwordless","passkey"],
"Top Security Vendors":["vendor","leader","platform","launch","announces","acquisition","partnership","integration","microsoft","okta","sailpoint","saviynt","cyberark","ping","wiz"],
"Emerging Threats":["threat","attack","breach","exploit","vulnerability","credential","phishing","token theft","account takeover","identity attack","malware","ransomware","compromise"],
"Market Share Insights":["market share","market growth","market size","magic quadrant","leader","challenger","adoption","market forecast","market analysis","market presence","revenue"],
"Technology Developments":["technology","passkey","fido","oauth","openid","mfa","passwordless","conditional access","identity proofing","authorization","policy engine","non-human identity","workload identity","ai agent","itdr"],
"Competitive Analysis":["compare","comparison","versus","vs.","competitive","capabilities","strengths","weaknesses","magic quadrant","market guide","vendor evaluation"]
}
TAG_RULES={"IGA":["identity governance","iga","access review","certification","role management"],"PAM":["privileged access","pam","just-in-time"],"CIAM":["ciam","customer identity","consumer identity"],"Authentication":["passkey","fido","authentication","mfa","passwordless"],"Identity Security":["identity security","identity threat","itdr","account takeover","credential"],"Machine Identity":["non-human identity","machine identity","workload identity","service account"],"Zero Trust":["zero trust","conditional access"],"AI & Identity":["ai agent","agentic ai","identity for ai"],"Authorization":["authorization","policy engine","oauth","openid"]}

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"IAM-Market-Monitor/2.0"})
    with urllib.request.urlopen(req,timeout=30) as r:return r.read()
def strip(v): return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",html.unescape(v or ""))).strip()
def pdate(v):
    try:
        d=parsedate_to_datetime(v); return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)
    except:return dt.datetime.now(dt.timezone.utc)
def clean_title(t,source):
    t=strip(t); t=re.sub(rf"\s*-\s*{re.escape(source)}\s*$","",t,flags=re.I); t=re.sub(r"\s*-\s*[A-Za-z0-9.-]+\.(com|org|net|io)\s*$","",t,flags=re.I); return t.strip(" -|")
def canon(t): return " ".join(re.sub(r"[^a-z0-9]+"," ",t.lower()).split())
def source_for(src,title,link):
    blob=f"{src} {title} {link}".lower()
    for name,domain in SOURCES:
        if domain in blob or name.lower() in blob:return name
    return src or "Approved source"
def scores(text):
    lo=text.lower(); return {s:sum(2 if " " in term else 1 for term in terms if term in lo) for s,terms in SECTION_RULES.items()}
def tags(text):
    lo=text.lower(); out=[tag for tag,terms in TAG_RULES.items() if any(t in lo for t in terms)]; return out[:4] or ["IAM"]
def summary(desc,title):
    c=strip(desc); c=re.sub(r"\s*Read more.*$","",c,flags=re.I)
    return "Open the original source for the full details." if not c or c.lower()==title.lower() else c[:340].rstrip(" ,.;")+("…" if len(c)>340 else "")
def feed(name,domain):
    q=urllib.parse.quote_plus(f"site:{domain} (identity OR IAM OR security OR authentication OR access) when:7d")
    root=ET.fromstring(fetch(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en")); out=[]
    for item in root.findall("./channel/item"):
        raw=item.findtext("title",""); link=item.findtext("link","").strip(); desc=item.findtext("description",""); pub=pdate(item.findtext("pubDate","")); sn=item.find("source"); rss=strip(sn.text if sn is not None and sn.text else ""); src=source_for(rss,raw,link)
        out.append({"title":clean_title(raw,src),"url":link,"description":desc,"published":pub,"source":src or name})
    return out

def main():
    now=dt.datetime.now(dt.timezone.utc); cutoff=now-dt.timedelta(days=LOOKBACK_DAYS); candidates=[]; errors=[]
    for name,domain in SOURCES:
        try:candidates.extend(feed(name,domain))
        except Exception as e:errors.append(f"{name}: {e}")
    unique={}
    for a in candidates:
        if a["published"]<cutoff:continue
        key=canon(a["title"])
        if len(key)<12:continue
        text=f'{a["title"]} {strip(a["description"])}'; sc=scores(text); primary=max(sc,key=sc.get); secs=[s for s,v in sorted(sc.items(),key=lambda x:x[1],reverse=True) if v>0][:2] or ["Latest IAM Trends"]
        rel=min(10,3+SOURCE_WEIGHT.get(a["source"],1)+sc.get(primary,0)+max(0,4-(now-a["published"]).days))
        item={"title":a["title"],"source":a["source"],"published_at":a["published"].isoformat(),"primary_section":primary,"sections":secs,"summary":summary(a["description"],a["title"]),"relevance":rel,"url":a["url"],"tags":tags(text)}
        if key not in unique or item["relevance"]>unique[key]["relevance"]:unique[key]=item
    all_items=sorted(unique.values(),key=lambda x:(x["relevance"],x["published_at"]),reverse=True); selected=[]; seen=set()
    for sec in SECTION_RULES:
        for item in [i for i in all_items if sec in i["sections"]][:3]:
            k=canon(item["title"])
            if k not in seen:selected.append(item);seen.add(k)
    for item in all_items:
        if len(selected)>=MAX_ITEMS:break
        k=canon(item["title"])
        if k not in seen:selected.append(item);seen.add(k)
    if not selected:
        print("No suitable items found; existing data was not overwritten.",file=sys.stderr);return 1
    payload={"generated_at":now.isoformat(),"items":selected[:MAX_ITEMS],"collector_notes":{"approved_sources":[d for _,d in SOURCES],"method":"Google News RSS restricted to approved domains; rule-based classification","errors":errors}}
    DATA.mkdir(exist_ok=True);ARCHIVE.mkdir(parents=True,exist_ok=True);content=json.dumps(payload,indent=2,ensure_ascii=False)+"\n";OUT.write_text(content,encoding="utf-8");(ARCHIVE/f"{now.date().isoformat()}.json").write_text(content,encoding="utf-8");print(f"Wrote {len(payload['items'])} selected items");return 0
if __name__=="__main__": raise SystemExit(main())

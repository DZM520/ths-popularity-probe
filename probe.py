#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os, sys, time
from datetime import datetime, timezone
from urllib.parse import quote
import requests

# --- 配置区 ---
TARGET_URL = "https://eq.10jqka.com.cn/frontend/thsTopRank/index.html?client_userid=Suk4y&share_hxapp=gsc&share_action=&back_source=hyperlink#/"
BASE_URL = "https://eq.10jqka.com.cn/frontend/thsTopRank/index.html"
CANDIDATE_URLS = [
    BASE_URL,
    TARGET_URL,
    "https://data.10jqka.com.cn/market/thstoprank.json",
    "https://data.10jqka.com.cn/market/lh/",
    "https://m.10jqka.com.cn/",
    "https://apphisapi.10jqka.com.cn/api/stock/hotStockList?type=popularity&page=1&size=20",
    "https://open.10jqka.com.cn/api/stock/toprank?type=up&num=10",
]
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Referer": "https://eq.10jqka.com.cn/",
}
RESULTS_DIR = "results"
DOCS_DIR = "docs"   # GitHub Pages source (main branch /docs)

# --- 工具函数 ---
def utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def safe_json_dump(path, obj):
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")

def http_get(url, headers=None, timeout=20, allow_redirects=True):
    try:
        r = requests.get(url, headers=headers or DEFAULT_HEADERS, timeout=timeout, allow_redirects=allow_redirects)
        meta = {
            "ok": True,
            "status_code": r.status_code,
            "final_url": r.url,
            "content_type": r.headers.get("Content-Type",""),
            "length": len(r.content),
            "text_preview": r.text[:4000],
        }
        return meta, r
    except Exception as e:
        return {"ok": False, "error": str(e)}, None

# --- 探测函数（Wayback / archive.today / candidate） ---
def probe_wayback(url):
    encoded = quote(url, safe="")
    cdx = f"https://web.archive.org/cdx/search/cdx?url={encoded}&output=json&fl=original,timestamp,statuscode&collapse=urlkey"
    meta, r = http_get(cdx, timeout=25)
    if not meta.get("ok"):
        return {"requested_url":url,"api_url":cdx,"status":"error","error":meta.get("error")}
    try:
        payload = r.json()
    except Exception:
        return {"requested_url":url,"api_url":cdx,"status":"non_json","raw_preview":r.text[:1000]}
    snaps = []
    if isinstance(payload, list) and len(payload) > 1:
        for row in payload[1:]:
            if len(row) < 3: continue
            original, ts, status = row[:3]
            snaps.append({
                "original": original, "timestamp": ts, "statuscode": status,
                "snapshot_url": f"https://web.archive.org/web/{ts}id_/{original}"
            })
    return {"requested_url":url,"api_url":cdx,"status":"ok" if snaps else "no_snapshots","snapshots_count":len(snaps),"snapshots":snaps[:30]}

def probe_archive_today(url):
    encoded = quote(url, safe="")
    probe_url = f"https://archive.today/?run=1&url={encoded}"
    meta, r = http_get(probe_url, timeout=25)
    if not meta.get("ok"):
        return {"requested_url":url,"probe_url":probe_url,"status":"error","error":meta.get("error")}
    text = r.text[:3000]
    status = "possible_snapshot_found" if ("archive.today" in meta.get("final_url","\").lower() or "archived" in text.lower() or "save" in text.lower()) else "no_snapshot_found"
    return {"requested_url":url,"probe_url":probe_url,"status":status,"status_code":meta.get("status_code"),"final_url":meta.get("final_url")}

def probe_candidate(url):
    headers = dict(DEFAULT_HEADERS)
    if "10jqka" in url:
        headers["Referer"] = "https://eq.10jqka.com.cn/"
    meta, r = http_get(url, headers=headers, timeout=15)
    if not meta.get("ok"):
        return {"url":url,"status":"error","error":meta.get("error")}
    json_payload = None
    try:
        ct = meta.get("content_type","" ) .lower()
        if "json" in ct or r.text.strip().startswith("{") or r.text.strip().startswith("["):
            json_payload = r.json()
    except Exception:
        json_payload = None
    return {
        "url": url,
        "status": "ok" if meta.get("status_code",500) < 400 else "http_error",
        "status_code": meta.get("status_code"),
        "final_url": meta.get("final_url"),
        "content_type": meta.get("content_type"),
        "length": meta.get("length"),
        "preview": r.text[:1000],
        "json_detected": json_payload is not None,
        "json_preview": json_payload if isinstance(json_payload, (list,dict)) else None,
    }

# --- 主流程 ---
def gather():
    res = {
        "generated_at": utc_now_iso(),
        "target_url": TARGET_URL,
        "base_url": BASE_URL,
        "wayback": probe_wayback(TARGET_URL),
        "archive_today": probe_archive_today(TARGET_URL),
        "candidate_urls": []
    }
    for u in CANDIDATE_URLS:
        res["candidate_urls"].append(probe_candidate(u))
        time.sleep(1.2)
    return res

# --- 生成静态页面（简单模板） ---
HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>同花顺 人气榜 探测报告</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,"Noto Sans CJK SC",Helvetica,Arial;margin:18px}
h1,h2{color:#0b4a6f}
table{border-collapse:collapse;width:100%;margin:8px 0}
th,td{border:1px solid #ddd;padding:6px 8px;text-align:left;font-size:14px}
th{background:#f7fbff}
pre{background:#f6f8fa;padding:10px;border-radius:6px;overflow:auto}
.bad{color:#b33}
.ok{color:#167a3d}
.btn{display:inline-block;padding:6px 10px;background:#0b75d1;color:#fff;border-radius:6px;text-decoration:none;margin:6px 0}
.small{font-size:13px;color:#666}
</style>
</head>
<body>
<h1>同花顺 人气榜 探测报告</h1>
<div class="small">生成时间： <strong id="gen_at"></strong></div>

<h2>概览</h2>
<div id="summary"></div>

<h2>候选接口检测结果</h2>
<table id="candidates_table">
<thead><tr><th>URL</th><th>状态</th><th>HTTP</th><th>Content-Type</th><th>JSON?</th><th>操作</th></tr></thead>
<tbody></tbody>
</table>

<h2>Wayback 快照（若有）</h2>
<div id="wayback_div"></div>

<h2>Archive.today 探测</h2>
<div id="archive_div"></div>

<p><a id="download_csv" class="btn" href="#">下载候选接口 CSV</a></p>

<script>
const SUMMARY = __SUMMARY__;
const CANDIDATES = __CANDIDATES__;
const WAYBACK = __WAYBACK__;
const ARCHIVE = __ARCHIVE__;

document.getElementById('gen_at').innerText = SUMMARY.generated_at || '';

function renderSummary(s){
  const el = document.getElementById('summary');
  const html = `
    <table>
      <tr><th>目标页面</th><td>${s.target_url}</td></tr>
      <tr><th>Wayback 状态</th><td>${s.wayback_status} (${s.wayback_snapshots_count||0})</td></tr>
      <tr><th>Archive.today</th><td>${s.archive_today_status||''}</td></tr>
      <tr><th>成功接口数</th><td>${s.candidate_success_count}</td></tr>
    </table>`;
  el.innerHTML = html;
}

function renderCandidates(list){
  const tb = document.querySelector('#candidates_table tbody');
  tb.innerHTML = '';
  list.forEach(it=>{
    const tr=document.createElement('tr');
    tr.innerHTML = `<td><a href="${it.url}" target="_blank">${it.url}</a></td>
      <td class="${it.status==='ok'?'ok':'bad'}">${it.status}</td>
      <td>${it.status_code||''}</td>
      <td>${it.content_type||''}</td>
      <td>${it.json_detected? '是':''}</td>
      <td><button onclick="showPreview(this)" data-preview='${escapeHtml(JSON.stringify(it.preview||it.json_preview||'').slice(0,2000))}'>预览</button></td>`;
    tb.appendChild(tr);
  });
}

function renderWayback(w){
  const el=document.getElementById('wayback_div');
  if(!w||!w.snapshots_count){ el.innerHTML='<div class="small">未发现 Wayback 快照</div>'; return; }
  let html = '<table><thead><tr><th>timestamp</th><th>snapshot</th></tr></thead><tbody>';
  (w.snapshots||[]).forEach(s=>{
    html += `<tr><td>${s.timestamp}</td><td><a href="${s.snapshot_url}" target="_blank">${s.snapshot_url}</a></td></tr>`;
  });
  html += '</tbody></table>';
  el.innerHTML = html;
}

function renderArchive(a){
  const el=document.getElementById('archive_div');
  el.innerHTML = `<div class="small">状态: ${a.status||''} ${a.final_url? '<a href="'+a.final_url+'" target="_blank">查看</a>':''}</div>`;
}

function escapeHtml(s){ return (s+'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function showPreview(btn){
  const p = btn.getAttribute('data-preview')||'';
  const w = window.open('', '_blank');
  w.document.write('<pre>'+p.replace(/</g,'&lt;')+'</pre>');
  w.document.close();
}

function downloadCSV(){
  const rows=[['url','status','status_code','content_type','json_detected','final_url']];
  CANDIDATES.forEach(c=>rows.push([c.url||'',c.status||'',c.status_code||'',c.content_type||'',c.json_detected?'1':'0',c.final_url||'']));
  const csv = rows.map(r=>r.map(cell=>'"'+(String(cell||'').replace(/"/g,'""'))+'"').join(',')).join('\n');
  const blob = new Blob([csv], {type:'text/csv;charset=utf-8;'});
  const url = URL.createObjectURL(blob);
  const a = document.getElementById('download_csv');
  a.href = url;
  a.download = 'candidate_endpoints.csv';
}
document.getElementById('download_csv').addEventListener('click', function(e){ downloadCSV(); });

renderSummary(SUMMARY);
renderCandidates(CANDIDATES);
renderWayback(WAYBACK);
renderArchive(ARCHIVE);
</script>
</body>
</html>
"""

def render_site(results):
    ensure_dir(DOCS_DIR)
    # prepare JS-safe JSON (escape closing script sequence)
    def safe_js(obj):
        s = json.dumps(obj, ensure_ascii=False)
        s = s.replace("</", "<\\/")  # avoid </script> break
        return s
    html = HTML_TEMPLATE.replace("__SUMMARY__", safe_js({
        "generated_at": results.get("generated_at"),
        "target_url": results.get("target_url"),
        "wayback_status": results.get("wayback",{}).get("status"),
        "wayback_snapshots_count": results.get("wayback",{}).get("snapshots_count",0),
        "archive_today_status": results.get("archive_today",{}).get("status"),
        "candidate_success_count": sum(1 for c in results.get("candidate_urls",[]) if c.get("status")=="ok")
    }))
    html = html.replace("__CANDIDATES__", safe_js(results.get("candidate_urls",[])))
    html = html.replace("__WAYBACK__", safe_js(results.get("wayback",{})))
    html = html.replace("__ARCHIVE__", safe_js(results.get("archive_today",{})))
    path = os.path.join(DOCS_DIR, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote site to", path)

def main():
    ensure_dir(RESULTS_DIR)
    res = gather()
    safe_json_dump(os.path.join(RESULTS_DIR, "full_probe.json"), res)
    safe_json_dump(os.path.join(RESULTS_DIR, "candidate_endpoints.json"), res.get("candidate_urls",[]))
    safe_json_dump(os.path.join(RESULTS_DIR, "wayback.json"), res.get("wayback",{}))
    safe_json_dump(os.path.join(RESULTS_DIR, "archive_today.json"), res.get("archive_today",{}))
    # 简要 summary
    summary = {
        "generated_at": res.get("generated_at"),
        "target_url": res.get("target_url"),
        "wayback_status": res.get("wayback",{}).get("status"),
        "wayback_snapshots_count": res.get("wayback",{}).get("snapshots_count",0),
        "archive_today_status": res.get("archive_today",{}).get("status"),
        "candidate_success_count": sum(1 for c in res.get("candidate_urls",[]) if c.get("status")=="ok")
    }
    safe_json_dump(os.path.join(RESULTS_DIR, "summary.json"), summary)
    # 生成站点到 docs/
    render_site(res)
    print("Done. results/ and docs/ updated.")

if __name__ == "__main__":
    main()

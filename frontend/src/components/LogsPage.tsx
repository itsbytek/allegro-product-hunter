import { useEffect, useState } from 'react'
import { RefreshCw, ScrollText } from 'lucide-react'
import { api } from '../api'

export default function LogsPage() {
  const [rows,setRows]=useState<Array<Record<string,unknown>>>([])
  const load=()=>void api.logs().then(setRows)
  useEffect(load,[])
  return <div className="page"><header className="page-header"><div><p className="eyebrow">OBSERVABILITY</p><h1>System Logs</h1><p>Błędy API, retry, rate limits i decyzje pipeline’u. Sekrety nie trafiają do logów.</p></div><button className="btn ghost" onClick={load}><RefreshCw size={16}/> Odśwież</button></header><section className="log-panel">{rows.map(row=><div className="log-row" key={String(row.id)}><span className={`log-level ${String(row.level).toLowerCase()}`}>{String(row.level)}</span><time>{new Date(String(row.created_at)).toLocaleString('pl-PL')}</time><strong>{String(row.event)}</strong><p>{String(row.message)}</p><code>{JSON.stringify(row.context)}</code></div>)}{!rows.length&&<div className="empty-state"><ScrollText/><strong>Brak wpisów</strong></div>}</section></div>
}


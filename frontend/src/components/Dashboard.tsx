import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { Bell, ChevronDown, Download, Filter, Play, RefreshCw, Search, SlidersHorizontal, Sparkles } from 'lucide-react'
import { api } from '../api'
import type { ResultItem, Scan, Stats } from '../types'
import StatusBadge from './StatusBadge'

const ProductDrawer = lazy(() => import('./ProductDrawer'))

const money = (value: number | null) => value === null ? '—' : `${value.toFixed(2)} zł`
const number = (value: number | null) => value === null ? '—' : String(value)

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({ scanned: 0, passed: 0, failed: 0, verify: 0, new_products: 0, last_scan_at: null, running_scan: null })
  const [items, setItems] = useState<ResultItem[]>([])
  const [onlyPass, setOnlyPass] = useState(false)
  const [sort, setSort] = useState('ranking')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<number | null>(null)
  const [scan, setScan] = useState<Scan | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [minProfit, setMinProfit] = useState<number | null>(null)
  const [maxCompetition, setMaxCompetition] = useState<number | null>(null)

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({ sort, direction: 'desc', limit: '500' })
      if (onlyPass) params.set('status', 'PASS')
      if (minProfit !== null) params.set('min_profit', String(minProfit))
      if (maxCompetition !== null) params.set('max_competition', String(maxCompetition))
      const [nextStats, result] = await Promise.all([api.stats(), api.results(params)])
      setStats(nextStats)
      setItems(result.items)
      if (nextStats.running_scan) setScan(nextStats.running_scan)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Nie udało się pobrać danych')
    }
  }, [onlyPass, sort, minProfit, maxCompetition])

  useEffect(() => { void load() }, [load])

  useEffect(() => {
    if (!scan || !['QUEUED', 'RUNNING'].includes(scan.status)) return
    const timer = window.setInterval(async () => {
      const current = await api.scan(scan.id)
      setScan(current)
      if (!['QUEUED', 'RUNNING'].includes(current.status)) {
        setBusy(false)
        window.clearInterval(timer)
        await load()
        if (current.pass_count > 0 && Notification.permission === 'granted') {
          const passes = await api.results(new URLSearchParams({status: 'PASS', sort: 'ranking', direction: 'desc', limit: '1'}))
          const winner = passes.items[0]
          const notice = new Notification('Nowy produkt PASS', { body: winner ? `${winner.name}\nZakup ${money(winner.cheapest_price)} · sprzedaż ${money(winner.sale_price)} · zysk ${money(winner.profit)} · ROI ${winner.roi?.toFixed(1) ?? '—'}% · ofert ${winner.offer_count ?? '—'}` : `Nowe wyniki PASS: ${current.pass_count}` })
          if (winner) notice.onclick = () => { window.focus(); setSelected(winner.id) }
        }
      }
    }, 1200)
    return () => window.clearInterval(timer)
  }, [scan?.id, scan?.status, load])

  const start = async (mode: 'live' | 'demo') => {
    setBusy(true); setError(null)
    try {
      if ('Notification' in window && Notification.permission === 'default') void Notification.requestPermission()
      setScan(await api.startScan(mode))
    } catch (reason) {
      setBusy(false)
      setError(reason instanceof Error ? reason.message : 'Nie udało się uruchomić skanu')
    }
  }

  const visible = useMemo(() => items.filter((item) => item.name.toLowerCase().includes(search.toLowerCase())), [items, search])
  const isRunning = busy || !!(scan && ['QUEUED', 'RUNNING'].includes(scan.status))

  return <div className="page dashboard-page">
    <header className="page-header">
      <div><p className="eyebrow">MARKET INTELLIGENCE</p><h1>Product Research</h1><p>Algorytmiczna analiza ofert Allegro, bez zgadywania i bez AI.</p></div>
      <div className="header-actions">
        <button className="btn ghost" onClick={() => void start('demo')} disabled={isRunning}><Sparkles size={16}/> Tryb demo</button>
        <button className="btn primary" onClick={() => void start('live')} disabled={isRunning}>{isRunning ? <RefreshCw className="spin" size={16}/> : <Play size={16}/>} ROZPOCZNIJ RESEARCH</button>
      </div>
    </header>

    {error && <div className="alert error"><strong>Operacja nieudana</strong><span>{error}</span><button onClick={() => setError(null)}>×</button></div>}
    {scan?.error_message && <div className="alert warning"><strong>Ograniczenie źródła</strong><span>{scan.error_message}. Sprawdź uprawnienia aplikacji w ustawieniach.</span></div>}
    {isRunning && scan && <div className="scan-progress"><div><span>{scan.pipeline_stage}</span><strong>{scan.progress}%</strong></div><div className="progress-track"><i style={{width: `${scan.progress}%`}} /></div></div>}

    <section className="stats-grid">
      <Stat label="Przeskanowane" value={stats.scanned} tone="neutral" />
      <Stat label="PASS" value={stats.passed} tone="green" />
      <Stat label="FAIL" value={stats.failed} tone="red" />
      <Stat label="VERIFY" value={stats.verify} tone="orange" />
      <Stat label="Nowe produkty" value={stats.new_products} tone="blue" />
      <div className="stat-card last"><small>OSTATNI SKAN</small><strong>{stats.last_scan_at ? new Date(stats.last_scan_at).toLocaleString('pl-PL') : 'Jeszcze nie wykonano'}</strong><span><Bell size={13}/> Scheduler monitoruje ustawienia</span></div>
    </section>

    <section className="results-panel">
      <div className="results-toolbar">
        <div><h2>Wyniki researchu</h2><span>{visible.length} produktów</span></div>
        <div className="toolbar-actions">
          <label className="search-box"><Search size={16}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Szukaj produktu..." /></label>
          <button className={`btn icon ${filtersOpen ? 'active' : ''}`} onClick={() => setFiltersOpen(!filtersOpen)}><SlidersHorizontal size={16}/> Filtry</button>
          <div className="export-menu"><button className="btn icon"><Download size={16}/> Eksport <ChevronDown size={14}/></button><div><a href={`/api/export/csv${onlyPass ? '?status=PASS' : ''}`}>CSV</a><a href={`/api/export/xlsx${onlyPass ? '?status=PASS' : ''}`}>XLSX</a><a href={`/api/export/json${onlyPass ? '?status=PASS' : ''}`}>JSON</a></div></div>
        </div>
      </div>
      {filtersOpen && <div className="filter-row">
        <label className="toggle"><input type="checkbox" checked={onlyPass} onChange={(e) => setOnlyPass(e.target.checked)}/><i/><span>Pokaż tylko PASS</span></label>
        <label>Min. zysk <input type="number" placeholder="dowolny" value={minProfit ?? ''} onChange={(e) => setMinProfit(e.target.value ? Number(e.target.value) : null)}/></label>
        <label>Max ofert <input type="number" placeholder="dowolny" value={maxCompetition ?? ''} onChange={(e) => setMaxCompetition(e.target.value ? Number(e.target.value) : null)}/></label>
        <label>Sortuj <select value={sort} onChange={(e) => setSort(e.target.value)}><option value="ranking">Priorytet</option><option value="profit">Zysk</option><option value="roi">ROI</option><option value="demand">Popyt / popularność</option><option value="competition">Konkurencja</option><option value="purchase_price">Cena zakupu</option><option value="sale_price">Cena sprzedaży</option><option value="checked_at">Ostatnie sprawdzenie</option></select></label>
        <Filter size={16}/>
      </div>}
      <div className="table-wrap">
        <table><thead><tr><th>Produkt</th><th>ID / EAN</th><th>Oferty</th><th>Zakup + dostawa</th><th>Sprzedaż</th><th>Zysk</th><th>ROI</th><th>Popyt</th><th>CE</th><th>External</th><th>Status</th><th>Sprawdzono</th></tr></thead>
        <tbody>{visible.map((item) => <tr key={item.id} onClick={() => setSelected(item.id)}>
          <td><div className="product-cell"><div className="product-thumb">{item.image_url ? <img src={item.image_url} alt=""/> : item.name.slice(0,1)}</div><div><strong>{item.name}</strong><small>{item.category ?? 'BRAK DANYCH'}</small>{item.is_new_opportunity && <em>NEW OPPORTUNITY</em>}</div></div></td>
          <td className="mono"><span>{item.allegro_product_id ?? 'VERIFY'}</span><small>{item.ean ?? 'EAN: —'}</small></td>
          <td><strong>{number(item.offer_count)}</strong></td>
          <td><strong>{money(item.cheapest_price)}</strong><small>+ {money(item.delivery_price)} · {item.carrier ?? 'VERIFY'}</small></td>
          <td><strong>{money(item.sale_price)}</strong><small>mediana popytu</small></td>
          <td className={item.profit !== null && item.profit >= 20 ? 'positive' : ''}><strong>{money(item.profit)}</strong></td>
          <td><strong>{item.roi === null ? '—' : `${item.roi.toFixed(1)}%`}</strong></td>
          <td><strong>{item.demand_sellers.length}/2</strong><small>sprzedawców</small></td>
          <td><span className="soft-tag">{item.ce_status}</span></td>
          <td><small>Temu: {item.external.Temu?.status ?? '—'}</small><small>Ali: {item.external.AliExpress?.status ?? '—'}</small></td>
          <td><StatusBadge status={item.status}/><small>{item.confidence}</small></td>
          <td><small>{new Date(item.checked_at).toLocaleString('pl-PL')}</small></td>
        </tr>)}</tbody></table>
        {!visible.length && <div className="empty-state"><Search size={26}/><strong>Brak wyników</strong><span>Uruchom research live lub jawnie oznaczony tryb demo.</span></div>}
      </div>
    </section>
    {selected !== null && <Suspense fallback={null}><ProductDrawer resultId={selected} onClose={() => setSelected(null)} onChanged={() => void load()} /></Suspense>}
  </div>
}

function Stat({ label, value, tone }: {label: string; value: number; tone: string}) {
  return <div className={`stat-card ${tone}`}><small>{label.toUpperCase()}</small><strong>{value.toLocaleString('pl-PL')}</strong><span>ostatni przebieg</span></div>
}

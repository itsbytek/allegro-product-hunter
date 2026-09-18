import { useEffect, useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Check, ExternalLink, ShieldAlert, Star, X, XCircle } from 'lucide-react'
import { api } from '../api'
import type { ResultDetailData } from '../types'
import StatusBadge from './StatusBadge'

const cash = (value: unknown) => typeof value === 'number' ? `${value.toFixed(2)} zł` : 'BRAK DANYCH'

export default function ProductDrawer({ resultId, onClose, onChanged }: { resultId: number; onClose: () => void; onChanged: () => void }) {
  const [data, setData] = useState<ResultDetailData | null>(null)
  useEffect(() => { void api.detail(resultId).then(setData) }, [resultId])
  const history = useMemo(() => (data?.history ?? []).map((row) => ({...row, date: new Date(String(row.captured_at)).toLocaleDateString('pl-PL')})), [data])
  if (!data) return <div className="drawer-backdrop"><aside className="drawer loading">Ładowanie...</aside></div>
  const result = data.result
  const product = data.product
  const status = String(result.status)
  const toggle = async () => { await api.toggleWatchlist(Number(product.id)); setData({...data, watchlisted: !data.watchlisted}); onChanged() }
  return <div className="drawer-backdrop" onMouseDown={onClose}><aside className="drawer" onMouseDown={(e) => e.stopPropagation()}>
    <div className="drawer-header"><div><span>SZCZEGÓŁY PRODUKTU</span><h2>{String(product.name)}</h2></div><button onClick={onClose}><X size={20}/></button></div>
    <div className="drawer-status"><StatusBadge status={status}/><span>Data confidence: <strong>{String(result.confidence)}</strong></span><button className={`watch ${data.watchlisted ? 'active' : ''}`} onClick={() => void toggle()}><Star size={15} fill={data.watchlisted ? 'currentColor' : 'none'}/>{data.watchlisted ? 'Obserwowany' : 'Dodaj do obserwowanych'}</button></div>
    <section className="detail-section"><h3>Overview</h3><div className="overview-grid"><Info label="Allegro Product ID" value={product.allegro_product_id}/><Info label="EAN" value={product.ean}/><Info label="Wariant" value={product.variant}/><Info label="Kategoria" value={product.category}/><Info label="Generic / no-name" value={product.is_generic}/><Info label="Liczba ofert" value={result.offer_count}/></div></section>
    <section className="detail-section"><h3>Popyt</h3><div className="seller-grid">{(result.demand_sellers as Array<Record<string, unknown>> ?? []).map((seller, index) => <div className="seller-card" key={String(seller.offer_id)}><span>SPRZEDAWCA #{index+1}</span><strong>{String(seller.seller)}</strong><b>{String(seller.value)} potwierdzeń</b><small>{String(seller.signal)}</small><a href={String(seller.url)} target="_blank">Źródło <ExternalLink size={12}/></a></div>)}{!(result.demand_sellers as unknown[] ?? []).length && <p className="muted">BRAK DANYCH / WYMAGA WERYFIKACJI</p>}</div></section>
    <section className="detail-section"><h3>Konkurencja i zakup</h3><div className="offers-list">{data.offers.map((offer) => <div key={String(offer.id)}><div><strong>{String(offer.seller ?? 'sprzedawca nieznany')}</strong><small>{String(offer.carrier ?? 'przewoźnik: VERIFY')} · popyt {String(offer.popularity ?? '—')}</small></div><b>{cash(offer.total_price)}</b><a href={String(offer.url)} target="_blank"><ExternalLink size={14}/></a></div>)}</div></section>
    <section className="detail-section"><h3>Kalkulacja</h3><div className="calculation"><Line label="Cena sprzedaży" value={result.realistic_sale_price}/><Line label="− cena zakupu" value={result.purchase_price}/><Line label="− dostawa" value={result.delivery_price}/><Line label="− prowizja Allegro" value={result.commission}/><Line label="− inne koszty" value={result.other_fees}/><Line label="− podatki" value={result.taxes}/><div className="total"><span>ZYSK</span><strong>{cash(result.profit)}</strong><em>ROI {typeof result.roi === 'number' ? `${result.roi.toFixed(1)}%` : '—'}</em></div><small>Metoda ceny: {String(result.realistic_price_method ?? 'BRAK DANYCH')}</small></div></section>
    <section className="detail-section"><h3>Historia</h3><div className="chart"><ResponsiveContainer width="100%" height={210}><AreaChart data={history}><defs><linearGradient id="profit" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#42d392" stopOpacity={0.35}/><stop offset="95%" stopColor="#42d392" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#222832" vertical={false}/><XAxis dataKey="date" stroke="#68707c" fontSize={11}/><YAxis stroke="#68707c" fontSize={11}/><Tooltip contentStyle={{background:'#11151b',border:'1px solid #2a313c'}}/><Area type="monotone" dataKey="profit" stroke="#42d392" fill="url(#profit)"/></AreaChart></ResponsiveContainer></div></section>
    <section className="detail-section"><h3>CE i konkurencja zewnętrzna</h3><div className="overview-grid"><Info label="CE" value={result.ce_status}/>{data.external_competition.map((row) => <Info key={String(row.provider)} label={String(row.provider)} value={`${String(row.status)} · ryzyko ${String(row.risk)}`}/>)}</div></section>
    <section className="detail-section"><h3>Decyzja</h3><div className="decision-columns"><Decision title="Passed" icon={<Check/>} tone="pass" rows={result.passed_checks as string[]}/><Decision title="Failed" icon={<XCircle/>} tone="fail" rows={result.failed_checks as string[]}/><Decision title="Needs verification" icon={<ShieldAlert/>} tone="verify" rows={result.verification_checks as string[]}/></div></section>
    <section className="detail-section"><h3>Źródła danych</h3><div className="evidence-list">{data.evidence.map((row) => <div key={String(row.id)}><span>{String(row.field)}</span><code>{JSON.stringify(row.value)}</code><b>{String(row.confidence)}</b>{row.source_url ? <a href={String(row.source_url)} target="_blank"><ExternalLink size={13}/></a> : null}</div>)}</div></section>
  </aside></div>
}

function Info({label,value}:{label:string;value:unknown}) { return <div className="info-box"><span>{label}</span><strong>{value === null || value === undefined ? 'BRAK DANYCH' : String(value)}</strong></div> }
function Line({label,value}:{label:string;value:unknown}) { return <div className="calc-line"><span>{label}</span><b>{cash(value)}</b></div> }
function Decision({title,icon,tone,rows}:{title:string;icon:React.ReactNode;tone:string;rows:string[]}) { return <div className={`decision ${tone}`}><h4>{icon}{title}</h4>{rows?.length ? rows.map((row,i)=><p key={i}>{row}</p>) : <p>—</p>}</div> }


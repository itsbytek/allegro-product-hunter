import { useEffect, useState } from 'react'
import { Check, ExternalLink, FileWarning, RefreshCw } from 'lucide-react'
import { api } from '../api'

export default function VerificationPage() {
  const resolvable = new Set(['shipping', 'identity', 'ce', 'generic', 'demand', 'sale_price'])
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([])
  const [editing, setEditing] = useState<number | null>(null)
  const [value, setValue] = useState('')
  const [source, setSource] = useState('')
  const [message, setMessage] = useState('')
  const load = () => void api.verification().then(setRows)
  useEffect(load, [])

  const begin = (row: Record<string, unknown>) => {
    setEditing(Number(row.id))
    setValue('')
    setSource(String(row.source_url ?? ''))
    setMessage('')
  }

  const save = async (row: Record<string, unknown>) => {
    const type = String(row.check_type)
    let parsed: unknown = value
    if (type === 'shipping') parsed = { carrier: value }
    if (type === 'identity') parsed = { allegro_product_id: value }
    if (type === 'demand' || type === 'sale_price') parsed = Number(value)
    if (type === 'generic') parsed = value.toLowerCase() === 'true' || value.toLowerCase() === 'tak'
    await api.addEvidence(Number(row.product_id), {
      field: type,
      value: parsed,
      source_url: source,
      confidence: 'HIGH',
      offer_id: row.offer_id ?? null,
    })
    setMessage('Dowód zapisany. Zostanie użyty w kolejnym skanie tej oferty.')
    setEditing(null)
    load()
  }

  const hint = (type: unknown) => ({
    shipping: 'np. InPost Paczkomat',
    identity: 'Allegro Product ID',
    ce: 'CE_CONFIRMED / CE_NOT_REQUIRED / CE_FAIL',
    generic: 'tak / nie',
    demand: 'potwierdzona liczba',
    sale_price: 'potwierdzona cena PLN',
  }[String(type)] ?? 'potwierdzona wartość')

  return <div className="page">
    <header className="page-header"><div><p className="eyebrow">BROWSER VERIFICATION</p><h1>Wymaga ręcznej weryfikacji</h1><p>Kolejka danych, których nie można potwierdzić oficjalnym API. Moduł nie omija CAPTCHA, logowania ani zabezpieczeń.</p></div><button className="btn ghost" onClick={load}><RefreshCw size={16}/> Odśwież</button></header>
    {message && <div className="alert info"><Check size={16}/><span>{message}</span></div>}
    <section className="verification-grid">
      {rows.map(row => <article key={String(row.id)}>
        <div><span>{String(row.check_type).toUpperCase()}</span><small>Produkt #{String(row.product_id ?? 'global')}</small></div>
        <p>{String(row.reason)}</p>
        {Boolean(row.source_url) && <a href={String(row.source_url)} target="_blank">Otwórz źródło <ExternalLink size={13}/></a>}
        {editing === Number(row.id) ? <div className="verify-form">
          <input value={value} onChange={event => setValue(event.target.value)} placeholder={hint(row.check_type)}/>
          <input value={source} onChange={event => setSource(event.target.value)} placeholder="URL źródła"/>
          <button className="btn primary" disabled={!value || !source} onClick={() => void save(row)}>Zapisz dowód</button>
        </div> : resolvable.has(String(row.check_type)) ? <button className="btn ghost verify-action" onClick={() => begin(row)}>Wprowadź potwierdzenie</button> : null}
      </article>)}
      {!rows.length && <div className="empty-state"><FileWarning/><strong>Kolejka jest pusta</strong><span>Brak nierozstrzygniętych wpisów.</span></div>}
    </section>
  </div>
}

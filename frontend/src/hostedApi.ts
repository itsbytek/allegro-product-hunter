import type { AppSettings, ResultDetailData, ResultItem, ResultsPage, Scan, Stats } from './types'

const now = () => new Date().toISOString()

const seed: ResultItem[] = [
  { id: 1, product_id: 1, name: 'Organizer obrotowy do kuchni 27 cm', image_url: null, category: 'Dom i Ogród / Organizacja kuchni', allegro_product_id: 'DEMO-APL-001', ean: '5901234567001', offer_count: 12, cheapest_price: 39.99, delivery_price: 8.99, carrier: 'InPost Paczkomat', sale_price: 84.99, profit: 23.27, roi: 47.5, demand_sellers: [{seller:'HomeBox',value:184,signal:'liczba kupujących',offer_id:'D1',url:'https://allegro.pl/'},{seller:'Porządek24',value:92,signal:'opinie po zakupie',offer_id:'D2',url:'https://allegro.pl/'}], ce_status: 'CE_NOT_REQUIRED', external: {Temu:{price:null,url:null,risk:'MEDIUM',status:'VERIFY'},AliExpress:{price:null,url:null,risk:'MEDIUM',status:'VERIFY'}}, status: 'PASS', confidence: 'HIGH', is_watchlisted: false, is_new_opportunity: true, checked_at: now() },
  { id: 2, product_id: 2, name: 'Pojemniki próżniowe zestaw 6 szt.', image_url: null, category: 'Dom i Ogród / Przechowywanie', allegro_product_id: 'DEMO-APL-002', ean: '5901234567002', offer_count: 38, cheapest_price: 61.5, delivery_price: 0, carrier: 'DPD', sale_price: 89.99, profit: 14.99, roi: 24.4, demand_sellers: [{seller:'SmartKitchen',value:240,signal:'liczba kupujących',offer_id:'D3',url:'https://allegro.pl/'},{seller:'DomowyŁad',value:118,signal:'opinie po zakupie',offer_id:'D4',url:'https://allegro.pl/'}], ce_status: 'CE_NOT_REQUIRED', external: {Temu:{price:39.9,url:null,risk:'HIGH',status:'MANUAL'},AliExpress:{price:null,url:null,risk:'MEDIUM',status:'VERIFY'}}, status: 'FAIL', confidence: 'HIGH', is_watchlisted: false, is_new_opportunity: false, checked_at: now() },
  { id: 3, product_id: 3, name: 'Lampka biurkowa LED USB', image_url: null, category: 'Dom i Ogród / Domowe biuro', allegro_product_id: 'DEMO-APL-003', ean: null, offer_count: 17, cheapest_price: 42.0, delivery_price: 9.99, carrier: 'DHL', sale_price: 79.9, profit: 15.93, roi: 30.6, demand_sellers: [{seller:'OfficePoint',value:76,signal:'oceny produktu',offer_id:'D5',url:'https://allegro.pl/'}], ce_status: 'CE_VERIFY', external: {Temu:{price:null,url:null,risk:'MEDIUM',status:'VERIFY'},AliExpress:{price:null,url:null,risk:'MEDIUM',status:'VERIFY'}}, status: 'VERIFY', confidence: 'LOW', is_watchlisted: false, is_new_opportunity: false, checked_at: now() },
]

const defaultResearch: AppSettings['research'] = { min_demand:30, min_sellers:2, max_competition:30, min_profit:20, min_roi:null, commission_rate:.15, other_fees:0, tax_rate:0, accepted_carriers:['InPost Paczkomat','InPost Kurier','DPD','DHL','DHL POP'], require_ce_when_applicable:true, categories:[], purchase_price_min:null, purchase_price_max:null, sale_price_min:null, sale_price_max:null, result_limit:500, concurrency:4, requests_per_second:2, scheduler_interval:'manual', default_query:'organizer do domu', default_category_id:'' }
let settings: AppSettings = { research: defaultResearch, allegro: { client_id:'', client_secret_configured:false, redirect_uri:`${location.origin}/api/allegro/oauth/callback`, environment:'production', user_agent:'AllegroProductHunter/0.1', connected:false, listing_access:'HOSTED_DEMO', last_connection_error:'Integracja live jest dostępna w wersji lokalnej.' } }
let items = seed.map(x => ({...x}))
let lastScan: Scan | null = null

const detailFor = (id:number): ResultDetailData => {
  const item = items.find(x=>x.id===id) ?? items[0]
  const purchase = (item.cheapest_price ?? 0)
  return {
    result: { ...item, realistic_sale_price:item.sale_price, purchase_price:item.cheapest_price, commission:(item.sale_price ?? 0)*.15, other_fees:0, taxes:0, realistic_price_method:'mediana ofert z potwierdzonym popytem', passed_checks:['Znaleziono ofertę źródłową','Akceptowana dostawa'], failed_checks:item.status==='FAIL'?['Przekroczony limit konkurencji','Zysk poniżej progu']:[], verification_checks:item.status==='VERIFY'?['Brak drugiego niezależnego sprzedawcy','CE wymaga potwierdzenia']:[] },
    product: { id:item.product_id, name:item.name, category:item.category, allegro_product_id:item.allegro_product_id, ean:item.ean, variant:'wariant demonstracyjny', is_generic:item.status!=='VERIFY' },
    offers: [{id:1,seller:'Oferta źródłowa',carrier:item.carrier,popularity:48,total_price:purchase+(item.delivery_price??0),url:'https://allegro.pl/'},{id:2,seller:'Sprzedawca popytowy',carrier:'InPost Paczkomat',popularity:120,total_price:item.sale_price,url:'https://allegro.pl/'}],
    evidence: [{id:1,field:'price',value:item.cheapest_price,confidence:'HIGH',source_url:'https://allegro.pl/'},{id:2,field:'demand',value:item.demand_sellers,confidence:item.confidence,source_url:'https://allegro.pl/'}],
    external_competition:Object.entries(item.external).map(([provider,row])=>({provider,...row})),
    history:[{captured_at:new Date(Date.now()-86400000*2).toISOString(),profit:(item.profit??0)-2},{captured_at:new Date(Date.now()-86400000).toISOString(),profit:(item.profit??0)-1},{captured_at:now(),profit:item.profit}],
    watchlisted:item.is_watchlisted,
  }
}

export const hostedApi = {
  stats: async ():Promise<Stats> => ({scanned:items.length,passed:items.filter(x=>x.status==='PASS').length,failed:items.filter(x=>x.status==='FAIL').length,verify:items.filter(x=>x.status==='VERIFY').length,new_products:items.filter(x=>x.is_new_opportunity).length,last_scan_at:lastScan?.completed_at ?? now(),running_scan:null}),
  results: async (params:URLSearchParams):Promise<ResultsPage> => { let out=[...items]; const status=params.get('status'); if(status) out=out.filter(x=>x.status===status); const min=Number(params.get('min_profit')); if(params.has('min_profit')) out=out.filter(x=>(x.profit??-Infinity)>=min); const max=Number(params.get('max_competition')); if(params.has('max_competition')) out=out.filter(x=>(x.offer_count??Infinity)<=max); return {items:out,total:out.length,limit:500,offset:0} },
  detail: async (id:number) => detailFor(id),
  startScan: async (_mode:'live'|'demo'):Promise<Scan> => { lastScan={id:Date.now(),status:'COMPLETED',pipeline_stage:'FINAL VALIDATION',progress:100,scanned_count:items.length,pass_count:1,fail_count:1,verify_count:1,new_count:1,mode:'hosted-demo',error_message:'Wersja Sites działa w trybie demonstracyjnym. Research live pozostaje w aplikacji lokalnej.',created_at:now(),started_at:now(),completed_at:now()}; return lastScan },
  scan: async () => lastScan!,
  settings: async () => settings,
  saveResearch: async (value:AppSettings['research']) => { settings={...settings,research:value}; return settings.research },
  saveAllegro: async (_value:Record<string,unknown>) => settings.allegro,
  testAllegro: async () => ({oauth:'HOSTED_DEMO',listing_access:'HOSTED_DEMO'}),
  oauthUrl: async () => { throw new Error('OAuth Allegro nie jest jeszcze dostępny w hostowanej wersji demonstracyjnej.') },
  toggleWatchlist: async (productId:number) => { const item=items.find(x=>x.product_id===productId); if(item)item.is_watchlisted=!item.is_watchlisted; return {watchlisted:!!item?.is_watchlisted} },
  logs: async () => [{id:1,level:'INFO',created_at:now(),event:'HOSTED_DEMO',message:'Panel Sites uruchomiony w bezpiecznym trybie demonstracyjnym.',context:{ai:'OFF',source:'fixture'}}],
  verification: async () => [{id:1,product_id:3,check_type:'ce',reason:'Brak źródła potwierdzającego CE dla produktu demonstracyjnego.',source_url:'https://allegro.pl/'}],
  addEvidence: async () => ({ok:true}),
}

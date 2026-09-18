export type Status = 'PASS' | 'FAIL' | 'VERIFY'

export interface Scan {
  id: number
  status: string
  pipeline_stage: string
  progress: number
  scanned_count: number
  pass_count: number
  fail_count: number
  verify_count: number
  new_count: number
  mode: string
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface Stats {
  scanned: number
  passed: number
  failed: number
  verify: number
  new_products: number
  last_scan_at: string | null
  running_scan: Scan | null
}

export interface ResultItem {
  id: number
  product_id: number
  name: string
  image_url: string | null
  category: string | null
  allegro_product_id: string | null
  ean: string | null
  offer_count: number | null
  cheapest_price: number | null
  delivery_price: number | null
  carrier: string | null
  sale_price: number | null
  profit: number | null
  roi: number | null
  demand_sellers: Array<Record<string, unknown>>
  ce_status: string
  external: Record<string, { price: number | null; url: string | null; risk: string; status: string }>
  status: Status
  confidence: string
  is_watchlisted: boolean
  is_new_opportunity: boolean
  checked_at: string
}

export interface ResultsPage {
  items: ResultItem[]
  total: number
  limit: number
  offset: number
}

export interface ResultDetailData {
  result: Record<string, unknown>
  product: Record<string, unknown>
  offers: Array<Record<string, unknown>>
  evidence: Array<Record<string, unknown>>
  external_competition: Array<Record<string, unknown>>
  history: Array<Record<string, unknown>>
  watchlisted: boolean
}

export interface ResearchSettings {
  min_demand: number
  min_sellers: number
  max_competition: number
  min_profit: number
  min_roi: number | null
  commission_rate: number
  other_fees: number
  tax_rate: number
  accepted_carriers: string[]
  require_ce_when_applicable: boolean
  categories: string[]
  purchase_price_min: number | null
  purchase_price_max: number | null
  sale_price_min: number | null
  sale_price_max: number | null
  result_limit: number
  concurrency: number
  requests_per_second: number
  scheduler_interval: 'manual' | 'hourly' | '6h' | '12h' | 'daily'
  default_query: string
  default_category_id: string
}

export interface AppSettings {
  research: ResearchSettings
  allegro: {
    client_id: string
    client_secret_configured: boolean
    redirect_uri: string
    environment: 'production' | 'sandbox'
    user_agent: string
    connected: boolean
    listing_access: string
    last_connection_error: string | null
  }
}


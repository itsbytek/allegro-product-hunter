import type { Status } from '../types'

export default function StatusBadge({ status }: { status: Status | string }) {
  return <span className={`status-badge ${status.toLowerCase()}`}><i />{status}</span>
}


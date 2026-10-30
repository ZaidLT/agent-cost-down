import { useState, type ReactNode } from 'react'
import s from '../App.module.css'
export function Icon({name, size = 18}: {name: 'arrow' | 'down' | 'check' | 'code' | 'clock' | 'external' | 'download'; size?: number}) {
  const paths = {arrow: 'M4 12h16m-6-6 6 6-6 6', down: 'M12 4v16m-6-6 6 6 6-6', check: 'm5 12 4 4L19 6', code: 'm8 6-6 6 6 6m8-12 6 6-6 6', clock: 'M12 8v4l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0', external: 'M14 3h7v7m0-7L10 14M10 3H3v18h18v-7', download: 'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5'}
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
export function Mark() { return <svg width="30" height="30" viewBox="0 0 30 30" fill="none" aria-hidden="true"><path d="M3 5h7v7h7v7h10" stroke="currentColor" strokeWidth="3"/><path d="m21 13 6 6-6 6" stroke="currentColor" strokeWidth="3"/></svg> }
export function Badge({children, tone = 'neutral'}: {children: ReactNode; tone?: 'neutral' | 'good' | 'warn' | 'bad'}) { return <span className={`${s.badge} ${s[tone]}`}>{children}</span> }
export function Raw({value, label = 'View raw evidence'}: {value: unknown; label?: string}) {
  const [open, setOpen] = useState(false)
  return <details className={s.raw} onToggle={e => setOpen(e.currentTarget.open)}><summary><Icon name="code" size={15} />{label}</summary>{open && <pre tabIndex={0} aria-label={label} className={s.json}>{JSON.stringify(value, null, 2)}</pre>}</details>
}
export function PageTitle({title, description, children}: {title: string; description?: string; children?: ReactNode}) {
  return <div className={s.pageTitle}><div><h1>{title}</h1>{description && <p>{description}</p>}</div>{children}</div>
}

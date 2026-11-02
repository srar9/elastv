import type {SVGProps} from 'react';
type Props=SVGProps<SVGSVGElement>&{size?:number};
const shapes:Record<string,React.ReactNode>={
 Play:<path d="m8 5 12 7-12 7Z"/>,CalendarDays:<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 11h18M8 3v4m8-4v4M8 15h.01M12 15h.01M16 15h.01M8 18h.01M12 18h.01"/></>,
 Tv:<><rect x="3" y="7" width="18" height="14" rx="2"/><path d="m7 2 5 5 5-5"/></>,Heart:<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>,
 Search:<><circle cx="10.5" cy="10.5" r="7.5"/><path d="m16 16 5 5"/></>,ChevronRight:<path d="m9 5 7 7-7 7"/>,ArrowUpRight:<path d="M7 7h10v10M7 17 17 7"/>,X:<path d="m6 6 12 12M6 18 18 6"/>,
 Maximize2:<path d="M8 3H3v5m18 8v5h-5M3 3l7 7m4 4 7 7"/>,RefreshCw:<><path d="M20 7v5h-5M4 17v-5h5"/><path d="M4.5 8A8 8 0 0 1 18 5l2 2M4 17l2 2a8 8 0 0 0 13.5-3"/></>,ArrowRight:<path d="M4 12h16m-7-7 7 7-7 7"/>,
 ShieldCheck:<><path d="M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6Z"/><path d="m8 12 3 3 5-6"/></>,Radio:<><circle cx="12" cy="12" r="2"/><path d="M8 8a6 6 0 0 0 0 8m8-8a6 6 0 0 1 0 8M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14"/></>,
 WifiOff:<><path d="m3 3 18 18M2 8a17 17 0 0 1 3-2M9 4a17 17 0 0 1 13 4M5 12a11 11 0 0 1 4-2m5 0a11 11 0 0 1 5 2M8 16a5 5 0 0 1 7-1"/><circle cx="12" cy="20" r="1"/></>,Clock3:<><circle cx="12" cy="12" r="9"/><path d="M12 7v5h4"/></>,
 Share2:<><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.5 10.5 7-4M8.5 13.5l7 4"/></>,
};
const icon=(name:string)=>function Icon({size=24,...props}:Props){return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{shapes[name]}</svg>;};
export const Play=icon('Play'),CalendarDays=icon('CalendarDays'),Tv=icon('Tv'),Heart=icon('Heart'),Search=icon('Search'),ChevronRight=icon('ChevronRight'),ArrowUpRight=icon('ArrowUpRight'),X=icon('X'),Maximize2=icon('Maximize2'),RefreshCw=icon('RefreshCw'),ArrowRight=icon('ArrowRight'),ShieldCheck=icon('ShieldCheck'),Radio=icon('Radio'),WifiOff=icon('WifiOff'),Clock3=icon('Clock3'),Share2=icon('Share2');

export type Signal = { id: string; name: string; slug: string };
export type Match = { id: string; title: string; league: string; time: string; startsAt: string; teams: string[]; signals: Signal[] };
export type Channel = Signal & { group: string };
export type Agenda = { day: string; updatedAt: string; stale: boolean; events: Match[]; channels: Channel[] };

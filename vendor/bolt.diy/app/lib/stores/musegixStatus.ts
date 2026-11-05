import { atom } from 'nanostores';

/** Latest Musegix status block (raw JSON text), shown in the sticky bar above the chat. */
export const musegixStatus = atom<string | null>(null);

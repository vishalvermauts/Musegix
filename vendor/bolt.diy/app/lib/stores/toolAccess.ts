import { create } from 'zustand';

export type ToolAccessMode = 'full-access' | 'ask-for-all';

const TOOL_ACCESS_MODE_KEY = 'tool_access_mode';

function getInitialMode(): ToolAccessMode {
  if (typeof window === 'undefined') {
    return 'full-access';
  }

  return window.localStorage.getItem(TOOL_ACCESS_MODE_KEY) === 'ask-for-all' ? 'ask-for-all' : 'full-access';
}

type ToolAccessStore = {
  mode: ToolAccessMode;
  setMode: (mode: ToolAccessMode) => void;
};

export const useToolAccessStore = create<ToolAccessStore>((set) => ({
  mode: getInitialMode(),
  setMode: (mode) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(TOOL_ACCESS_MODE_KEY, mode);
    }

    set({ mode });
  },
}));

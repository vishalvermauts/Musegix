import { useStore } from '@nanostores/react';
import { musegixStatus } from '~/lib/stores/musegixStatus';
import { MusegixStatus } from './MusegixStatus';

/** Sticky strip at the top of the chat: always shows the latest prompt's Musegix status. */
export const MusegixStickyStatus = () => {
  const raw = useStore(musegixStatus);

  if (!raw) {
    return null;
  }

  return (
    <div className="sticky top-0 z-20 w-full max-w-chat mx-auto px-1 pt-2 pb-1 bg-bolt-elements-background-depth-1">
      <MusegixStatus raw={raw} sticky />
    </div>
  );
};

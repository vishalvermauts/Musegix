import { describe, expect, it } from 'vitest';
import { EnhancedStreamingMessageParser } from './enhanced-message-parser';

/** Shell actions the parser would send to WebContainer's /bin/jsh for one model message. */
function shellActions(text: string): string[] {
  const out: string[] = [];
  const parser = new EnhancedStreamingMessageParser({
    callbacks: {
      onActionClose: (data: any) => {
        if (data.action.type === 'shell') {
          out.push(data.action.content.trim());
        }
      },
    },
  });
  parser.parse('msg_1', text, true);

  return out;
}

describe('prose inside ```bash blocks (Musegix jsh audit)', () => {
  it('A: a prose-only line is not executed', () => {
    expect(shellActions('Next step:\n```bash\nAdd the new component styles:\n```\n')).toEqual([]);
  });

  it('B: prose header + real command runs only the command', () => {
    expect(shellActions('```bash\nInstall the dependencies:\nnpm install\n```\n')).toEqual(['npm install']);
  });

  it('C: plain command sequence still runs', () => {
    expect(shellActions('```bash\nnpm install\nnpm run dev\n```\n')).toEqual(['npm install\nnpm run dev']);
  });

  it('D: chained command still runs', () => {
    expect(shellActions('```bash\nnpm install && npm run dev\n```\n')).toEqual(['npm install && npm run dev']);
  });

  it('E: prose with punctuation is not executed', () => {
    expect(shellActions('```bash\nNote (important): run "npm install" first\n```\n')).toEqual([]);
  });
});

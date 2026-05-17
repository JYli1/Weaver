import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';

// 加载 WEAVER.md 文件（类似 Claude Code 的 CLAUDE.md）
// 优先级：项目级 > 用户全局级
export function loadWeaverMd(): string {
  const paths = [
    join(homedir(), '.weaver', 'WEAVER.md'),
    join(process.cwd(), '.weaver', 'WEAVER.md'),
    join(process.cwd(), 'WEAVER.md'),
  ];

  const contents: string[] = [];

  for (const p of paths) {
    if (existsSync(p)) {
      try {
        const content = readFileSync(p, 'utf-8').trim();
        if (content) contents.push(content);
      } catch {}
    }
  }

  return contents.join('\n\n---\n\n');
}

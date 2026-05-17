import { ToolDefinition, ToolResult } from '../../types/tool';

export function createGlobTool(): ToolDefinition {
  return {
    name: 'Glob',
    description: '按 glob 模式搜索文件路径。返回匹配的文件列表。',
    inputSchema: {
      type: 'object',
      properties: {
        pattern: { type: 'string', description: 'glob 模式，如 "**/*.ts"' },
        path: { type: 'string', description: '搜索目录，默认当前目录' },
      },
      required: ['pattern'],
    },
    async execute(input): Promise<ToolResult> {
      const pattern = input.pattern as string;
      const searchPath = (input.path as string) || process.cwd();

      try {
        const glob = new Bun.Glob(pattern);
        const matches: string[] = [];
        for (const entry of glob.scanSync({ cwd: searchPath, absolute: true })) {
          matches.push(entry);
          if (matches.length >= 500) break;
        }
        if (matches.length === 0) {
          return { output: 'No matches found', exitCode: 0 };
        }
        return { output: matches.join('\n'), exitCode: 0 };
      } catch (err: any) {
        return { output: `Error: ${err.message}`, exitCode: 1 };
      }
    },
  };
}

import { execCommand } from '../../utils/shell';
import { ToolDefinition, ToolResult } from '../../types/tool';

export function createGrepTool(): ToolDefinition {
  return {
    name: 'Grep',
    description: '在文件内容中搜索正则表达式模式。使用 ripgrep 或 findstr 作为后端。',
    inputSchema: {
      type: 'object',
      properties: {
        pattern: { type: 'string', description: '正则表达式搜索模式' },
        path: { type: 'string', description: '搜索路径，默认当前目录' },
        glob: { type: 'string', description: '文件过滤 glob，如 "*.ts"' },
      },
      required: ['pattern'],
    },
    async execute(input): Promise<ToolResult> {
      const pattern = input.pattern as string;
      const searchPath = (input.path as string) || process.cwd();
      const fileGlob = input.glob as string | undefined;

      const args: string[] = ['--no-heading', '--line-number', '--color=never'];
      if (fileGlob) args.push('--glob', fileGlob);
      args.push(pattern, searchPath);

      const cmd = `rg ${args.map(a => `"${a}"`).join(' ')}`;
      const result = await execCommand(cmd, { type: 'local' }, { timeout: 30000 });

      if (result.exitCode === 1 && !result.stdout) {
        return { output: 'No matches found', exitCode: 0 };
      }
      return { output: result.stdout, exitCode: result.exitCode };
    },
  };
}

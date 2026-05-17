import { execCommand, ShellResult } from '../../utils/shell';
import { ExecBackend } from '../../types/config';
import { ToolDefinition, ToolResult } from '../../types/tool';

export function createBashTool(backend: ExecBackend): ToolDefinition {
  return {
    name: 'Bash',
    description: '在配置的执行后端运行 shell 命令。支持 local/wsl/ssh/docker 后端。',
    inputSchema: {
      type: 'object',
      properties: {
        command: { type: 'string', description: '要执行的 bash 命令' },
        timeout: { type: 'number', description: '超时时间（毫秒），默认 120000' },
      },
      required: ['command'],
    },
    async execute(input: Record<string, unknown>): Promise<ToolResult> {
      const command = input.command as string;
      const timeout = (input.timeout as number) ?? 120000;

      const result: ShellResult = await execCommand(command, backend, { timeout });

      return {
        output: result.stdout || '(no output)',
        exitCode: result.exitCode,
        timedOut: result.timedOut,
      };
    },
  };
}

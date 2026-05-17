import { readFileSync, existsSync } from 'fs';
import { ToolDefinition, ToolResult } from '../../types/tool';

export function createFileReadTool(): ToolDefinition {
  return {
    name: 'Read',
    description: '读取文件内容。返回带行号的文件内容。',
    inputSchema: {
      type: 'object',
      properties: {
        file_path: { type: 'string', description: '文件的绝对路径' },
        offset: { type: 'number', description: '起始行号（从 0 开始）' },
        limit: { type: 'number', description: '读取行数' },
      },
      required: ['file_path'],
    },
    async execute(input): Promise<ToolResult> {
      const filePath = input.file_path as string;
      const offset = (input.offset as number) ?? 0;
      const limit = (input.limit as number) ?? 2000;

      if (!existsSync(filePath)) {
        return { output: `Error: file not found: ${filePath}`, exitCode: 1 };
      }

      try {
        const content = readFileSync(filePath, 'utf-8');
        const lines = content.split('\n');
        const slice = lines.slice(offset, offset + limit);
        const numbered = slice.map((line, i) => `${offset + i + 1}\t${line}`).join('\n');
        return { output: numbered, exitCode: 0 };
      } catch (err: any) {
        return { output: `Error reading file: ${err.message}`, exitCode: 1 };
      }
    },
  };
}

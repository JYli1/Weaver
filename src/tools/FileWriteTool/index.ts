import { writeFileSync, mkdirSync } from 'fs';
import { dirname } from 'path';
import { ToolDefinition, ToolResult } from '../../types/tool';

export function createFileWriteTool(): ToolDefinition {
  return {
    name: 'Write',
    description: '写入文件。如果文件不存在则创建，存在则覆盖。自动创建父目录。',
    inputSchema: {
      type: 'object',
      properties: {
        file_path: { type: 'string', description: '文件的绝对路径' },
        content: { type: 'string', description: '要写入的内容' },
      },
      required: ['file_path', 'content'],
    },
    async execute(input): Promise<ToolResult> {
      const filePath = input.file_path as string;
      const content = input.content as string;

      try {
        mkdirSync(dirname(filePath), { recursive: true });
        writeFileSync(filePath, content, 'utf-8');
        return { output: `File written: ${filePath}`, exitCode: 0 };
      } catch (err: any) {
        return { output: `Error writing file: ${err.message}`, exitCode: 1 };
      }
    },
  };
}

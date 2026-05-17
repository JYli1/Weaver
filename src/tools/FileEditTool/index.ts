import { readFileSync, writeFileSync, existsSync } from 'fs';
import { ToolDefinition, ToolResult } from '../../types/tool';

export function createFileEditTool(): ToolDefinition {
  return {
    name: 'Edit',
    description: '对文件执行精确字符串替换。old_string 必须在文件中唯一匹配。',
    inputSchema: {
      type: 'object',
      properties: {
        file_path: { type: 'string', description: '文件的绝对路径' },
        old_string: { type: 'string', description: '要替换的文本' },
        new_string: { type: 'string', description: '替换后的文本' },
        replace_all: { type: 'boolean', description: '是否替换所有匹配项', default: false },
      },
      required: ['file_path', 'old_string', 'new_string'],
    },
    async execute(input): Promise<ToolResult> {
      const filePath = input.file_path as string;
      const oldStr = input.old_string as string;
      const newStr = input.new_string as string;
      const replaceAll = (input.replace_all as boolean) ?? false;

      if (!existsSync(filePath)) {
        return { output: `Error: file not found: ${filePath}`, exitCode: 1 };
      }

      try {
        let content = readFileSync(filePath, 'utf-8');

        if (!replaceAll) {
          const count = content.split(oldStr).length - 1;
          if (count === 0) {
            return { output: `Error: old_string not found in file`, exitCode: 1 };
          }
          if (count > 1) {
            return { output: `Error: old_string matches ${count} times, must be unique`, exitCode: 1 };
          }
        }

        if (replaceAll) {
          content = content.replaceAll(oldStr, newStr);
        } else {
          content = content.replace(oldStr, newStr);
        }

        writeFileSync(filePath, content, 'utf-8');
        return { output: `File edited: ${filePath}`, exitCode: 0 };
      } catch (err: any) {
        return { output: `Error editing file: ${err.message}`, exitCode: 1 };
      }
    },
  };
}

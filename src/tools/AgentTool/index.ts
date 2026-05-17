import Anthropic from '@anthropic-ai/sdk';
import chalk from 'chalk';
import { WeaverConfig } from '../../types/config';
import { ToolDefinition, ToolResult } from '../../types/tool';
import { execCommand } from '../../utils/shell';

export function createAgentTool(config: WeaverConfig, parentTools: ToolDefinition[]): ToolDefinition {
  return {
    name: 'Agent',
    description: '启动一个子 agent 执行独立任务。子 agent 有自己的上下文和工具，完成后返回结果。适合并行执行独立的侦察/枚举任务。',
    inputSchema: {
      type: 'object',
      properties: {
        prompt: { type: 'string', description: '给子 agent 的任务描述' },
        description: { type: 'string', description: '简短描述（用于状态显示）' },
      },
      required: ['prompt'],
    },
    async execute(input): Promise<ToolResult> {
      const prompt = input.prompt as string;
      const description = (input.description as string) || '子任务';

      console.log(chalk.cyan(`  [子Agent] ${description}`));

      const client = new Anthropic({
        apiKey: config.apiKey,
        baseURL: config.baseUrl,
      });

      const tools = parentTools
        .filter(t => t.name !== 'Agent')
        .map(t => ({
          name: t.name,
          description: t.description,
          input_schema: t.inputSchema as Anthropic.Tool['input_schema'],
        }));

      const systemPrompt = `你是 Weaver 的子 agent，负责执行一个具体的渗透测试子任务。
完成任务后，用简洁的文本总结你的发现和结果。`;

      const messages: Anthropic.MessageParam[] = [
        { role: 'user', content: prompt },
      ];

      let maxTurns = 20;
      let finalText = '';

      while (maxTurns-- > 0) {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 4096,
          system: systemPrompt,
          tools,
          messages,
        });

        const assistantContent = response.content;
        messages.push({ role: 'assistant', content: assistantContent });

        const textBlocks = assistantContent.filter(b => b.type === 'text');
        const toolBlocks = assistantContent.filter(b => b.type === 'tool_use');

        if (textBlocks.length > 0) {
          finalText = textBlocks.map(b => (b as Anthropic.TextBlock).text).join('\n');
        }

        if (toolBlocks.length === 0 || response.stop_reason === 'end_turn') {
          break;
        }

        const toolResults: Anthropic.ToolResultBlockParam[] = [];
        for (const block of toolBlocks) {
          const toolUse = block as Anthropic.ToolUseBlock;
          const tool = parentTools.find(t => t.name === toolUse.name);
          if (!tool) {
            toolResults.push({
              type: 'tool_result',
              tool_use_id: toolUse.id,
              content: `Error: tool "${toolUse.name}" not found`,
            });
            continue;
          }

          const result = await tool.execute(toolUse.input as Record<string, unknown>);
          toolResults.push({
            type: 'tool_result',
            tool_use_id: toolUse.id,
            content: result.output,
          });
        }

        messages.push({ role: 'user', content: toolResults });
      }

      console.log(chalk.cyan(`  [子Agent 完成] ${description}`));
      return { output: finalText || '(子 agent 无输出)', exitCode: 0 };
    },
  };
}

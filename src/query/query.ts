import Anthropic from '@anthropic-ai/sdk';
import chalk from 'chalk';
import { WeaverConfig } from '../types/config';
import { ToolDefinition, ToolResult } from '../types/tool';
import { Skill } from '../skills/types';
import { buildSystemPrompt } from '../constants/systemPrompt';
import { detectPhase, PHASE_COLORS, PHASE_LABELS, formatTokens, Phase } from '../components/theme';

export interface Message {
  role: 'user' | 'assistant';
  content: string | ContentBlock[];
}

export type ContentBlock =
  | { type: 'text'; text: string }
  | { type: 'tool_use'; id: string; name: string; input: Record<string, unknown> }
  | { type: 'tool_result'; tool_use_id: string; content: string };

export interface Conversation {
  messages: Message[];
  startTime: number;
  tokenUsage: { input: number; output: number };
}

interface QueryOptions {
  config: WeaverConfig;
  tools: ToolDefinition[];
  skills?: Skill[];
}

export async function query(
  userInput: string,
  conversation: Conversation,
  options: QueryOptions
): Promise<void> {
  const { config, tools, skills = [] } = options;

  const client = new Anthropic({
    apiKey: config.apiKey,
    baseURL: config.baseUrl,
  });

  const systemPrompt = buildSystemPrompt(skills);

  conversation.messages.push({ role: 'user', content: userInput });

  const anthropicTools = tools.map((t) => ({
    name: t.name,
    description: t.description,
    input_schema: t.inputSchema as Anthropic.Tool['input_schema'],
  }));

  let continueLoop = true;

  while (continueLoop) {
    const response = await client.messages.create({
      model: config.model,
      max_tokens: 8192,
      system: systemPrompt,
      tools: anthropicTools,
      messages: conversation.messages.map(formatMessage),
    });

    conversation.tokenUsage.input += response.usage.input_tokens;
    conversation.tokenUsage.output += response.usage.output_tokens;

    const assistantContent: ContentBlock[] = [];
    continueLoop = false;

    for (const block of response.content) {
      if (block.type === 'text') {
        assistantContent.push({ type: 'text', text: block.text });
        const phase = detectPhase(block.text);
        const colorFn = PHASE_COLORS[phase];
        console.log('\n' + colorFn(block.text));
      } else if (block.type === 'tool_use') {
        assistantContent.push({
          type: 'tool_use',
          id: block.id,
          name: block.name,
          input: block.input as Record<string, unknown>,
        });
      }
    }

    conversation.messages.push({ role: 'assistant', content: assistantContent });

    const toolUseBlocks = assistantContent.filter(
      (b): b is Extract<ContentBlock, { type: 'tool_use' }> => b.type === 'tool_use'
    );

    if (toolUseBlocks.length > 0) {
      const toolResults: ContentBlock[] = [];

      for (const toolUse of toolUseBlocks) {
        const tool = tools.find((t) => t.name === toolUse.name);
        if (!tool) {
          toolResults.push({
            type: 'tool_result',
            tool_use_id: toolUse.id,
            content: `Error: tool "${toolUse.name}" not found`,
          });
          continue;
        }

        console.log(chalk.gray(`\n[执行] ${toolUse.name}: ${formatToolInput(toolUse.input)}`));

        const result: ToolResult = await tool.execute(toolUse.input);

        if (result.timedOut) {
          console.log(chalk.yellow('[超时]'));
        }

        const output = truncateOutput(result.output, 10000);
        if (output) {
          console.log(chalk.gray(output));
        }

        toolResults.push({
          type: 'tool_result',
          tool_use_id: toolUse.id,
          content: result.timedOut
            ? `[TIMEOUT] ${output}`
            : `[exit code: ${result.exitCode}]\n${output}`,
        });
      }

      conversation.messages.push({ role: 'user', content: toolResults });
      continueLoop = true;
    }

    if (response.stop_reason === 'end_turn') {
      continueLoop = false;
    }
  }

  const { input, output } = conversation.tokenUsage;
  const elapsed = Math.round((Date.now() - conversation.startTime) / 1000);
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  console.log(chalk.gray(`\n[${formatTokens(input + output)} tokens │ ${min}:${String(sec).padStart(2, '0')}]`));
}

function formatMessage(msg: Message): Anthropic.MessageParam {
  if (typeof msg.content === 'string') {
    return { role: msg.role, content: msg.content };
  }
  return {
    role: msg.role,
    content: msg.content.map((block) => {
      if (block.type === 'tool_result') {
        return {
          type: 'tool_result' as const,
          tool_use_id: block.tool_use_id,
          content: block.content,
        };
      }
      return block as any;
    }),
  };
}

function formatToolInput(input: Record<string, unknown>): string {
  if (input.command) return String(input.command).slice(0, 80);
  return JSON.stringify(input).slice(0, 80);
}

function truncateOutput(output: string, maxLen: number): string {
  if (output.length <= maxLen) return output;
  return output.slice(0, maxLen) + '\n... [truncated]';
}

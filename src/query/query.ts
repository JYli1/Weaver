import Anthropic from '@anthropic-ai/sdk';
import chalk from 'chalk';
import { WeaverConfig } from '../types/config';
import { ToolDefinition, ToolResult } from '../types/tool';
import { Skill } from '../skills/types';
import { buildSystemPrompt, buildSkillsReminder } from '../constants/systemPrompt';
import {
  Spinner,
  displayToolStart,
  displayToolOutput,
  displayToolSuccess,
  displayToolFail,
  displayFileWrite,
  displayAssistantText,
  displayTokenInfo,
} from '../utils/display';

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

  const systemPrompt = buildSystemPrompt(skills, config);

  // 注入 skills listing 作为 <system-reminder>（对标 Claude Code）
  const skillsReminder = buildSkillsReminder(skills);
  const userContent = skillsReminder
    ? `${userInput}\n${skillsReminder}`
    : userInput;
  conversation.messages.push({ role: 'user', content: userContent });

  const anthropicTools = tools.map((t) => ({
    name: t.name,
    description: t.description,
    input_schema: t.inputSchema as Anthropic.Tool['input_schema'],
  }));

  const spinner = new Spinner();
  let continueLoop = true;

  while (continueLoop) {
    spinner.start('思考中...');

    const response = await client.messages.create({
      model: config.model,
      max_tokens: 8192,
      system: systemPrompt,
      tools: anthropicTools,
      messages: conversation.messages.map(formatMessage),
    });

    spinner.stop();

    conversation.tokenUsage.input += response.usage.input_tokens;
    conversation.tokenUsage.output += response.usage.output_tokens;

    const assistantContent: ContentBlock[] = [];
    continueLoop = false;

    for (const block of response.content) {
      if (block.type === 'text') {
        assistantContent.push({ type: 'text', text: block.text });
        displayAssistantText(block.text);
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

        const detail = formatToolDetail(toolUse.name, toolUse.input);
        displayToolStart(toolUse.name, detail);

        spinner.start(`${toolUse.name} 执行中...`);
        const result: ToolResult = await tool.execute(toolUse.input);
        spinner.stop();

        const output = truncateOutput(result.output, 10000);

        if (result.timedOut) {
          displayToolFail('超时');
        } else if (result.exitCode !== 0) {
          displayToolFail(`exit code ${result.exitCode}`);
          displayToolOutput(output, 8);
        } else {
          if (toolUse.name === 'Write') {
            const lines = output.split('\n');
            displayFileWrite(String(toolUse.input.file_path), lines.length, lines);
          } else if (toolUse.name === 'Edit') {
            displayToolSuccess(`Edited ${toolUse.input.file_path}`);
          } else if (toolUse.name === 'Read') {
            const lines = output.split('\n').length;
            displayToolSuccess(`Read ${lines} lines from ${toolUse.input.file_path}`);
            displayToolOutput(output, 6);
          } else {
            displayToolOutput(output, 12);
          }
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
  displayTokenInfo(input, output, elapsed);
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

function formatToolDetail(name: string, input: Record<string, unknown>): string {
  switch (name) {
    case 'Bash': return String(input.command || '').slice(0, 60);
    case 'Read':
    case 'Write':
    case 'Edit': return String(input.file_path || '');
    case 'Glob': return String(input.pattern || '');
    case 'Grep': return String(input.pattern || '');
    case 'Skill': return String(input.skill || '');
    case 'Agent': return String(input.description || input.prompt || '').slice(0, 40);
    default: return JSON.stringify(input).slice(0, 50);
  }
}

function truncateOutput(output: string, maxLen: number): string {
  if (output.length <= maxLen) return output;
  return output.slice(0, maxLen) + '\n... [truncated]';
}

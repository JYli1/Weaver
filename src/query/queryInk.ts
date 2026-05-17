import Anthropic from '@anthropic-ai/sdk';
import { WeaverConfig } from '../types/config';
import { ToolDefinition, ToolResult } from '../types/tool';
import { Skill } from '../skills/types';
import { buildSystemPrompt } from '../constants/systemPrompt';
import { Conversation, Message, ContentBlock } from './query';

interface QueryCallbacks {
  onText: (text: string) => void;
  onToolStart: (name: string, input: Record<string, unknown>) => void;
  onToolEnd: (output: string) => void;
}

interface QueryOptions {
  config: WeaverConfig;
  tools: ToolDefinition[];
  skills?: Skill[];
}

export async function queryWithCallbacks(
  userInput: string,
  conversation: Conversation,
  options: QueryOptions,
  callbacks: QueryCallbacks
): Promise<void> {
  const { config, tools, skills = [] } = options;

  const client = new Anthropic({
    apiKey: config.apiKey,
    baseURL: config.baseUrl,
  });

  const systemPrompt = buildSystemPrompt(skills, config);

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
        callbacks.onText(block.text);
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

        callbacks.onToolStart(toolUse.name, toolUse.input);
        const result: ToolResult = await tool.execute(toolUse.input);
        const output = truncateOutput(result.output, 10000);
        callbacks.onToolEnd(output);

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

function truncateOutput(output: string, maxLen: number): string {
  if (output.length <= maxLen) return output;
  return output.slice(0, maxLen) + '\n... [truncated]';
}

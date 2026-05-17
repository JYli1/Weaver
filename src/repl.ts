import * as readline from 'readline';
import chalk from 'chalk';
import { WeaverConfig } from './types/config';
import { ToolDefinition } from './types/tool';
import { Skill } from './skills/types';
import { McpManager } from './services/mcp';
import { query, Conversation } from './query/query';
import { generateReport, saveReport } from './utils/session';

interface ReplOptions {
  config: WeaverConfig;
  tools: ToolDefinition[];
  skills: Skill[];
  mcp: McpManager;
}

export async function startRepl(options: ReplOptions) {
  const { config, tools, skills, mcp } = options;

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const conversation: Conversation = {
    messages: [],
    startTime: Date.now(),
    tokenUsage: { input: 0, output: 0 },
  };

  const prompt = () => {
    rl.question(chalk.green('weaver> '), async (input) => {
      const trimmed = input.trim();

      if (!trimmed) {
        prompt();
        return;
      }

      if (trimmed === '/exit' || trimmed === 'exit') {
        if (conversation.messages.length > 0) {
          console.log(chalk.gray('\n正在生成本次任务报告...'));
          const report = generateReport(conversation, config);
          const filepath = saveReport(report, config);
          console.log(chalk.gray(`报告已保存至: ${filepath}`));
        }
        console.log(chalk.gray('\n再见。'));
        rl.close();
        process.exit(0);
      }

      if (trimmed === '/report') {
        if (conversation.messages.length === 0) {
          console.log(chalk.yellow('当前 session 无交互记录'));
        } else {
          const report = generateReport(conversation, config);
          const filepath = saveReport(report, config);
          console.log(chalk.gray(`报告已保存至: ${filepath}`));
        }
        prompt();
        return;
      }

      if (trimmed === '/status') {
        printStatus(config, conversation, skills);
        prompt();
        return;
      }

      if (trimmed === '/env') {
        printEnv(config);
        prompt();
        return;
      }

      if (trimmed.startsWith('/skill')) {
        handleSkillCommand(trimmed, skills);
        prompt();
        return;
      }

      if (trimmed === '/mcp') {
        handleMcpCommand(mcp);
        prompt();
        return;
      }

      if (trimmed === '/compact') {
        compactConversation(conversation);
        prompt();
        return;
      }

      try {
        await query(trimmed, conversation, { config, tools, skills });
      } catch (err: any) {
        console.error(chalk.red(`错误: ${err.message}`));
      }

      prompt();
    });
  };

  prompt();
}

function printStatus(config: WeaverConfig, conversation: Conversation, skills: Skill[]) {
  const elapsed = Math.round((Date.now() - conversation.startTime) / 1000);
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  const { input, output } = conversation.tokenUsage;
  const total = input + output;

  console.log(chalk.gray('─'.repeat(40)));
  console.log(chalk.white(`模型: ${config.model}`));
  console.log(chalk.white(`后端: ${config.backend.type}`));
  console.log(chalk.white(`Token: ${total.toLocaleString()} (输入 ${input.toLocaleString()} / 输出 ${output.toLocaleString()})`));
  console.log(chalk.white(`Skills: ${skills.filter(s => s.enabled).length} 已启用`));
  console.log(chalk.white(`时长: ${min}分${sec}秒`));
  console.log(chalk.gray('─'.repeat(40)));
}

function printEnv(config: WeaverConfig) {
  console.log(chalk.gray('─'.repeat(40)));
  console.log(chalk.white('执行环境:'));
  console.log(chalk.gray(`  平台: ${process.platform}`));
  console.log(chalk.gray(`  Node: ${process.version}`));
  console.log(chalk.gray(`  CWD: ${process.cwd()}`));
  console.log(chalk.gray(`  后端类型: ${config.backend.type}`));
  console.log(chalk.white('API:'));
  console.log(chalk.gray(`  Key: ${config.apiKey ? '***已配置' : '未配置'}`));
  console.log(chalk.gray(`  BaseURL: ${config.baseUrl || '(默认)'}`));
  console.log(chalk.gray('─'.repeat(40)));
}

function handleSkillCommand(input: string, skills: Skill[]) {
  const parts = input.split(/\s+/);
  const subcommand = parts[1] || 'list';
  const skillName = parts[2];

  switch (subcommand) {
    case 'list':
      if (skills.length === 0) {
        console.log(chalk.gray('  (无已加载 skill)'));
        return;
      }
      console.log(chalk.gray('─'.repeat(40)));
      for (const s of skills) {
        const status = s.enabled ? chalk.green('●') : chalk.red('○');
        console.log(`  ${status} ${chalk.white(s.metadata.name)} ${chalk.gray(`[${s.source}]`)}`);
        console.log(`    ${chalk.gray(s.metadata.description)}`);
      }
      console.log(chalk.gray('─'.repeat(40)));
      break;

    case 'show':
      if (!skillName) {
        console.log(chalk.yellow('用法: /skill show <name>'));
        return;
      }
      const skill = skills.find(s => s.metadata.name === skillName);
      if (!skill) {
        console.log(chalk.red(`Skill "${skillName}" 未找到`));
        return;
      }
      console.log(chalk.gray('─'.repeat(40)));
      console.log(chalk.white(`名称: ${skill.metadata.name}`));
      console.log(chalk.white(`描述: ${skill.metadata.description}`));
      console.log(chalk.white(`来源: ${skill.source}`));
      console.log(chalk.white(`路径: ${skill.filePath}`));
      if (skill.metadata.allowedTools) {
        console.log(chalk.white(`工具: ${skill.metadata.allowedTools.join(', ')}`));
      }
      console.log(chalk.gray('─'.repeat(40)));
      break;

    default:
      console.log(chalk.gray('可用命令: /skill list | /skill show <name>'));
  }
}

function handleMcpCommand(mcp: McpManager) {
  console.log(chalk.gray('─'.repeat(40)));
  if (mcp.clients.size === 0) {
    console.log(chalk.gray('  (无 MCP 连接)'));
  } else {
    for (const [name, client] of mcp.clients) {
      const status = client.isConnected() ? chalk.green('●') : chalk.red('○');
      console.log(`  ${status} ${chalk.white(name)}`);
    }
    console.log(chalk.gray(`  工具总数: ${mcp.tools.length}`));
  }
  console.log(chalk.gray('─'.repeat(40)));
}

function compactConversation(conversation: Conversation) {
  const msgCount = conversation.messages.length;
  if (msgCount <= 4) {
    console.log(chalk.yellow('对话太短，无需压缩'));
    return;
  }

  const keepRecent = 4;
  const oldMessages = conversation.messages.slice(0, msgCount - keepRecent);
  const recentMessages = conversation.messages.slice(msgCount - keepRecent);

  let summary = '[上下文压缩摘要]\n';
  for (const msg of oldMessages) {
    if (typeof msg.content === 'string') {
      summary += `- 用户: ${msg.content.slice(0, 100)}\n`;
    } else if (Array.isArray(msg.content)) {
      for (const block of msg.content) {
        if (block.type === 'text') {
          summary += `- 助手: ${block.text.slice(0, 100)}\n`;
        } else if (block.type === 'tool_use') {
          summary += `- 执行: ${block.name}\n`;
        }
      }
    }
  }

  conversation.messages = [
    { role: 'user', content: summary },
    { role: 'assistant', content: [{ type: 'text', text: '已了解之前的上下文，继续工作。' }] },
    ...recentMessages,
  ];

  const removed = msgCount - conversation.messages.length;
  console.log(chalk.green(`已压缩 ${removed} 条消息，保留最近 ${keepRecent} 条 + 摘要`));
}

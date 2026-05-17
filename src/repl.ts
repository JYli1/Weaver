import * as readline from 'readline';
import chalk from 'chalk';
import { WeaverConfig } from './types/config';
import { ToolDefinition } from './types/tool';
import { Skill } from './skills/types';
import { McpManager } from './services/mcp';
import { query, Conversation } from './query/query';
import { generateReport, saveReport } from './utils/session';
import { formatTokens } from './components/theme';

interface ReplOptions {
  config: WeaverConfig;
  tools: ToolDefinition[];
  skills: Skill[];
  mcp: McpManager;
}

const COMMANDS = [
  { name: '/status', description: '显示当前状态' },
  { name: '/env', description: '显示执行环境' },
  { name: '/skill', description: '管理 skill' },
  { name: '/skill list', description: '列出所有 skill' },
  { name: '/skill show', description: '查看 skill 详情' },
  { name: '/mcp', description: '查看 MCP 连接' },
  { name: '/report', description: '生成渗透测试报告' },
  { name: '/compact', description: '压缩对话上下文' },
  { name: '/exit', description: '退出' },
];

export async function startRepl(options: ReplOptions) {
  const { config, tools, skills, mcp } = options;

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    completer: (line: string) => {
      if (line.startsWith('/')) {
        const matches = COMMANDS
          .filter(c => c.name.startsWith(line))
          .map(c => c.name);
        return [matches.length ? matches : COMMANDS.map(c => c.name), line];
      }
      return [[], line];
    },
  });

  const conversation: Conversation = {
    messages: [],
    startTime: Date.now(),
    tokenUsage: { input: 0, output: 0 },
  };

  const prompt = () => {
    rl.question(chalk.green.bold('weaver> '), async (input) => {
      const trimmed = input.trim();

      if (!trimmed) {
        prompt();
        return;
      }

      if (trimmed === '/exit' || trimmed === 'exit') {
        if (conversation.messages.length > 0) {
          console.log(chalk.gray('\n  正在生成本次任务报告...'));
          const report = generateReport(conversation, config);
          const filepath = saveReport(report, config);
          console.log(chalk.green(`  ✓ 报告已保存至: ${filepath}`));
        }
        console.log(chalk.gray('\n  再见。\n'));
        rl.close();
        process.exit(0);
      }

      if (trimmed === '/report') {
        if (conversation.messages.length === 0) {
          console.log(chalk.yellow('  当前 session 无交互记录'));
        } else {
          const report = generateReport(conversation, config);
          const filepath = saveReport(report, config);
          console.log(chalk.green(`  ✓ 报告已保存至: ${filepath}`));
        }
        prompt();
        return;
      }

      if (trimmed === '/status') {
        printStatus(config, conversation, skills, mcp);
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

      if (trimmed.startsWith('/')) {
        const fuzzy = COMMANDS.filter(c => c.name.includes(trimmed.slice(1)));
        if (fuzzy.length > 0) {
          console.log(chalk.gray('  你是不是想输入:'));
          for (const c of fuzzy) {
            console.log(chalk.gray(`    ${chalk.white(c.name)} — ${c.description}`));
          }
        } else {
          console.log(chalk.yellow(`  未知命令: ${trimmed}`));
          console.log(chalk.gray('  可用命令: /status /env /skill /mcp /report /compact /exit'));
        }
        prompt();
        return;
      }

      try {
        await query(trimmed, conversation, { config, tools, skills });
      } catch (err: any) {
        console.log(chalk.red(`\n  ✗ 错误: ${err.message}`));
      }

      prompt();
    });
  };

  prompt();
}

function printStatus(config: WeaverConfig, conversation: Conversation, skills: Skill[], mcp: McpManager) {
  const elapsed = Math.round((Date.now() - conversation.startTime) / 1000);
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  const { input, output } = conversation.tokenUsage;
  const total = input + output;

  console.log('');
  console.log(chalk.gray('  ┌─ 状态 ─────────────────────────────────'));
  console.log(chalk.gray('  │ ') + chalk.gray('模型:   ') + chalk.white(config.model));
  console.log(chalk.gray('  │ ') + chalk.gray('后端:   ') + chalk.white(formatBackend(config)));
  console.log(chalk.gray('  │ ') + chalk.gray('Token:  ') + chalk.white(`${formatTokens(total)} (输入 ${formatTokens(input)} / 输出 ${formatTokens(output)})`));
  console.log(chalk.gray('  │ ') + chalk.gray('Skills: ') + chalk.white(`${skills.filter(s => s.enabled).length} 已启用`));
  if (mcp.clients.size > 0) {
    console.log(chalk.gray('  │ ') + chalk.gray('MCP:    ') + chalk.green(`${mcp.clients.size} 已连接`));
  }
  console.log(chalk.gray('  │ ') + chalk.gray('时长:   ') + chalk.white(`${min}:${String(sec).padStart(2, '0')}`));
  console.log(chalk.gray('  └──────────────────────────────────────────'));
  console.log('');
}

function printEnv(config: WeaverConfig) {
  console.log('');
  console.log(chalk.gray('  ┌─ 环境 ─────────────────────────────────'));
  console.log(chalk.gray('  │ ') + chalk.gray('平台:     ') + chalk.white(process.platform));
  console.log(chalk.gray('  │ ') + chalk.gray('Runtime:  ') + chalk.white(process.version));
  console.log(chalk.gray('  │ ') + chalk.gray('CWD:      ') + chalk.white(process.cwd()));
  console.log(chalk.gray('  │ ') + chalk.gray('后端:     ') + chalk.white(formatBackend(config)));
  console.log(chalk.gray('  │ ') + chalk.gray('API Key:  ') + chalk.white(config.apiKey ? '***已配置' : chalk.red('未配置')));
  console.log(chalk.gray('  │ ') + chalk.gray('Base URL: ') + chalk.white(config.baseUrl || '(默认)'));
  console.log(chalk.gray('  └──────────────────────────────────────────'));
  console.log('');
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
      console.log('');
      for (const s of skills) {
        const status = s.enabled ? chalk.green('●') : chalk.red('○');
        console.log(`  ${status} ${chalk.bold.white(s.metadata.name)} ${chalk.gray(`[${s.source}]`)}`);
        console.log(chalk.gray(`    ${s.metadata.description}`));
      }
      console.log('');
      break;

    case 'show':
      if (!skillName) {
        console.log(chalk.yellow('  用法: /skill show <name>'));
        return;
      }
      const skill = skills.find(s => s.metadata.name === skillName);
      if (!skill) {
        console.log(chalk.red(`  ✗ Skill "${skillName}" 未找到`));
        const similar = skills.filter(s => s.metadata.name.includes(skillName));
        if (similar.length > 0) {
          console.log(chalk.gray('  你是不是想找:'));
          for (const s of similar) {
            console.log(chalk.gray(`    ${chalk.white(s.metadata.name)}`));
          }
        }
        return;
      }
      console.log('');
      console.log(chalk.gray('  ┌─ Skill ────────────────────────────────'));
      console.log(chalk.gray('  │ ') + chalk.gray('名称: ') + chalk.bold.white(skill.metadata.name));
      console.log(chalk.gray('  │ ') + chalk.gray('描述: ') + chalk.white(skill.metadata.description));
      console.log(chalk.gray('  │ ') + chalk.gray('来源: ') + chalk.white(skill.source));
      console.log(chalk.gray('  │ ') + chalk.gray('路径: ') + chalk.gray(skill.filePath));
      if (skill.metadata.allowedTools) {
        console.log(chalk.gray('  │ ') + chalk.gray('工具: ') + chalk.white(skill.metadata.allowedTools.join(', ')));
      }
      if (skill.metadata.argumentHint) {
        console.log(chalk.gray('  │ ') + chalk.gray('参数: ') + chalk.yellow(skill.metadata.argumentHint));
      }
      console.log(chalk.gray('  └──────────────────────────────────────────'));
      console.log('');
      break;

    default:
      console.log(chalk.gray('  可用命令:'));
      console.log(chalk.gray(`    ${chalk.white('/skill list')}  — 列出所有 skill`));
      console.log(chalk.gray(`    ${chalk.white('/skill show')} <name> — 查看 skill 详情`));
  }
}

function handleMcpCommand(mcp: McpManager) {
  console.log('');
  if (mcp.clients.size === 0) {
    console.log(chalk.gray('  (无 MCP 连接)'));
    console.log(chalk.gray('  在 .weaver/settings.json 中配置 mcpServers 来连接外部工具'));
  } else {
    console.log(chalk.gray('  ┌─ MCP ──────────────────────────────────'));
    for (const [name, client] of mcp.clients) {
      const status = client.isConnected() ? chalk.green('●') : chalk.red('○');
      console.log(chalk.gray('  │ ') + `${status} ${chalk.bold.white(name)}`);
    }
    console.log(chalk.gray('  │ ') + chalk.gray(`工具总数: ${mcp.tools.length}`));
    console.log(chalk.gray('  └──────────────────────────────────────────'));
  }
  console.log('');
}

function compactConversation(conversation: Conversation) {
  const msgCount = conversation.messages.length;
  if (msgCount <= 4) {
    console.log(chalk.yellow('  对话太短，无需压缩'));
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
  console.log(chalk.green(`  ✓ 已压缩 ${removed} 条消息，保留最近 ${keepRecent} 条 + 摘要`));
}

function formatBackend(config: WeaverConfig): string {
  const b = config.backend;
  switch (b.type) {
    case 'local': return 'local';
    case 'wsl': return `wsl://${b.distro}`;
    case 'ssh': return `ssh://${b.user}@${b.host}:${b.port}`;
    case 'docker': return `docker://${b.container}`;
  }
}

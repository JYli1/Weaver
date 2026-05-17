import chalk from 'chalk';

const SYMBOLS = {
  tool: '●',
  result: '⎿',
  success: '✓',
  fail: '✗',
  thinking: '✻',
  spinner: ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
  indent: '  ',
};

export class Spinner {
  private interval: ReturnType<typeof setInterval> | null = null;
  private frame = 0;
  private text = '';
  private startTime = 0;

  start(text: string) {
    this.text = text;
    this.frame = 0;
    this.startTime = Date.now();
    this.interval = setInterval(() => {
      const symbol = SYMBOLS.spinner[this.frame % SYMBOLS.spinner.length];
      const elapsed = Math.round((Date.now() - this.startTime) / 1000);
      const timeStr = elapsed > 0 ? chalk.gray(` ${elapsed}s`) : '';
      process.stdout.write(`\r${chalk.magenta(SYMBOLS.thinking)} ${chalk.italic.gray(this.text)}${timeStr}`);
      this.frame++;
    }, 80);
  }

  update(text: string) {
    this.text = text;
  }

  stop() {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }
    const elapsed = Math.round((Date.now() - this.startTime) / 1000);
    process.stdout.write(`\r\x1b[K`);
    if (elapsed >= 2) {
      console.log(chalk.magenta(`${SYMBOLS.thinking} `) + chalk.italic.gray(`Baked for ${elapsed}s`));
    }
  }
}

export function displayToolStart(name: string, detail: string) {
  console.log(`\n${chalk.cyan(SYMBOLS.tool)} ${chalk.bold.white(name)}(${chalk.yellow(detail)})`);
}

export function displayToolOutput(output: string, maxLines = 12) {
  if (!output.trim()) return;
  const lines = output.split('\n');
  const shown = lines.slice(0, maxLines);
  for (const line of shown) {
    console.log(`  ${chalk.gray(SYMBOLS.result)}  ${highlightLine(line)}`);
  }
  if (lines.length > maxLines) {
    console.log(`  ${chalk.gray(SYMBOLS.result)}  ${chalk.gray(`... ${lines.length - maxLines} more lines`)}`);
  }
}

export function displayToolSuccess(summary: string) {
  console.log(`  ${chalk.gray(SYMBOLS.result)}  ${chalk.green(summary)}`);
}

export function displayToolFail(summary: string) {
  console.log(`  ${chalk.gray(SYMBOLS.result)}  ${chalk.red(SYMBOLS.fail)} ${chalk.red(summary)}`);
}

export function displayFileWrite(path: string, content: string) {
  const lines = content.split('\n');
  displayToolSuccess(`Wrote ${lines.length} lines to ${path}`);
  const shown = lines.slice(0, 8);
  for (let i = 0; i < shown.length; i++) {
    const num = chalk.gray(String(i + 1).padStart(6));
    console.log(`  ${chalk.gray(SYMBOLS.result)}  ${num} ${highlightCodeLine(shown[i], guessLang(path))}`);
  }
  if (lines.length > 8) {
    console.log(`  ${chalk.gray(SYMBOLS.result)}  ${chalk.gray(`       ... ${lines.length - 8} more lines`)}`);
  }
}

export function displayAssistantText(text: string) {
  const blocks = parseBlocks(text);
  console.log('');
  for (const block of blocks) {
    if (block.type === 'code') {
      console.log(`${chalk.cyan(SYMBOLS.tool)} ${highlightCodeBlock(block.content, block.lang)}`);
    } else {
      const lines = renderMarkdownProse(block.content);
      for (const line of lines) {
        console.log(`  ${line}`);
      }
    }
  }
}

interface Block {
  type: 'prose' | 'code';
  content: string;
  lang: string;
}

function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  const codeBlockRegex = /```(\w*)\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = codeBlockRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      const prose = text.slice(lastIndex, match.index).trim();
      if (prose) blocks.push({ type: 'prose', content: prose, lang: '' });
    }
    blocks.push({ type: 'code', content: match[2].trimEnd(), lang: match[1] || '' });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    const prose = text.slice(lastIndex).trim();
    if (prose) blocks.push({ type: 'prose', content: prose, lang: '' });
  }

  return blocks;
}

function highlightCodeBlock(code: string, lang: string): string {
  const lines = code.split('\n');
  const highlighted = lines.map(line => highlightCodeLine(line, lang));
  const indented = highlighted.map((line, i) => {
    if (i === 0) return line;
    return `  ${line}`;
  });
  return indented.join('\n');
}

function highlightCodeLine(line: string, lang: string): string {
  if (lang === 'json' || line.trim().startsWith('{') || line.trim().startsWith('"')) {
    return highlightJson(line);
  }
  if (lang === 'bash' || lang === 'sh' || line.startsWith('#') || line.startsWith('$')) {
    return highlightBash(line);
  }
  if (lang === 'python' || lang === 'py') {
    return highlightPython(line);
  }
  if (lang === 'typescript' || lang === 'ts' || lang === 'javascript' || lang === 'js') {
    return highlightTs(line);
  }
  return highlightGeneric(line);
}

function highlightJson(line: string): string {
  return line
    .replace(/"([^"]+)"(?=\s*:)/g, chalk.cyan('"$1"'))
    .replace(/:\s*"([^"]*)"/g, ': ' + chalk.green('"$1"'))
    .replace(/:\s*(true|false)/g, ': ' + chalk.yellow('$1'))
    .replace(/:\s*(null)/g, ': ' + chalk.gray('$1'))
    .replace(/:\s*(\d+\.?\d*)/g, ': ' + chalk.magenta('$1'))
    .replace(/[{}\[\]]/g, (m) => chalk.white(m))
    .replace(/,$/g, chalk.gray(','));
}

function highlightBash(line: string): string {
  if (line.startsWith('#')) return chalk.gray(line);
  return line
    .replace(/^(\$\s*)/g, chalk.green('$1'))
    .replace(/\b(sudo|apt|yum|pip|npm|bun|git|docker|nmap|curl|wget|ssh|cat|grep|find|ls|cd|rm|cp|mv|echo|export)\b/g, chalk.cyan('$1'))
    .replace(/--[\w-]+/g, (m) => chalk.yellow(m))
    .replace(/-[a-zA-Z]\b/g, (m) => chalk.yellow(m))
    .replace(/"([^"]*)"/g, chalk.green('"$1"'))
    .replace(/'([^']*)'/g, chalk.green("'$1'"))
    .replace(/\|/g, chalk.white('|'))
    .replace(/(https?:\/\/[^\s]+)/g, chalk.underline.blue('$1'));
}

function highlightPython(line: string): string {
  return line
    .replace(/\b(def|class|import|from|return|if|else|elif|for|while|try|except|with|as|in|not|and|or|True|False|None)\b/g, chalk.magenta('$1'))
    .replace(/"([^"]*)"/g, chalk.green('"$1"'))
    .replace(/'([^']*)'/g, chalk.green("'$1'"))
    .replace(/#.*/g, (m) => chalk.gray(m))
    .replace(/\b(\d+\.?\d*)\b/g, chalk.yellow('$1'));
}

function highlightTs(line: string): string {
  return line
    .replace(/\b(const|let|var|function|return|if|else|for|while|import|export|from|class|interface|type|async|await|new|this|true|false|null|undefined)\b/g, chalk.magenta('$1'))
    .replace(/"([^"]*)"/g, chalk.green('"$1"'))
    .replace(/'([^']*)'/g, chalk.green("'$1'"))
    .replace(/`([^`]*)`/g, chalk.green('`$1`'))
    .replace(/\/\/.*/g, (m) => chalk.gray(m))
    .replace(/\b(\d+\.?\d*)\b/g, chalk.yellow('$1'));
}

function highlightGeneric(line: string): string {
  return line
    .replace(/"([^"]*)"/g, chalk.green('"$1"'))
    .replace(/'([^']*)'/g, chalk.green("'$1'"))
    .replace(/\b(true|false|null|none|nil)\b/gi, chalk.yellow('$1'))
    .replace(/\b(\d+\.?\d*)\b/g, chalk.magenta('$1'));
}

function renderMarkdownProse(text: string): string[] {
  const lines = text.split('\n');
  const result: string[] = [];

  for (const line of lines) {
    if (!line.trim()) {
      result.push('');
      continue;
    }
    let rendered = line
      .replace(/^(#{1,3})\s+(.+)$/, (_, _h, title) => chalk.bold.white(title))
      .replace(/\*\*(.+?)\*\*/g, (_, c) => chalk.bold.white(c))
      .replace(/`([^`]+)`/g, (_, c) => chalk.cyan(c))
      .replace(/^- (.+)$/, (_, item) => `${chalk.gray('•')} ${item}`)
      .replace(/^\d+\.\s+(.+)$/, (_, item) => `${chalk.gray('›')} ${item}`)
      .replace(/(https?:\/\/[^\s]+)/g, chalk.underline.blue('$1'));
    result.push(rendered);
  }

  return result;
}

function highlightLine(line: string): string {
  return line
    .replace(/\b(error|Error|ERROR|FAIL|failed|Failed)\b/g, chalk.red('$1'))
    .replace(/\b(success|Success|SUCCESS|PASS|passed|Passed|ok|OK|done|Done)\b/g, chalk.green('$1'))
    .replace(/\b(warning|Warning|WARN)\b/g, chalk.yellow('$1'))
    .replace(/\b(\d+\.\d+\.\d+\.\d+)\b/g, chalk.cyan('$1'))
    .replace(/\b(\d+\/tcp|\d+\/udp)\b/g, chalk.yellow('$1'))
    .replace(/(https?:\/\/[^\s]+)/g, chalk.underline.blue('$1'));
}

function guessLang(path: string): string {
  if (path.endsWith('.json')) return 'json';
  if (path.endsWith('.ts') || path.endsWith('.tsx')) return 'ts';
  if (path.endsWith('.js') || path.endsWith('.jsx')) return 'js';
  if (path.endsWith('.py')) return 'python';
  if (path.endsWith('.sh') || path.endsWith('.bash')) return 'bash';
  if (path.endsWith('.md')) return '';
  return '';
}

export function displayTokenInfo(input: number, output: number, elapsed: number) {
  const total = input + output;
  const fmt = (n: number) => {
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return String(n);
  };
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  console.log(chalk.gray(`\n  ${fmt(total)} tokens │ ${min}:${String(sec).padStart(2, '0')}`));
}

export function displaySlashMenu() {
  console.log('');
  console.log(chalk.bold.white('  可用命令:'));
  console.log(`  ${chalk.cyan('/status')}    显示当前状态（模型、后端、token、skills）`);
  console.log(`  ${chalk.cyan('/env')}       显示执行环境`);
  console.log(`  ${chalk.cyan('/skill')}     管理 skill（list / show）`);
  console.log(`  ${chalk.cyan('/mcp')}       查看 MCP 连接状态`);
  console.log(`  ${chalk.cyan('/report')}    生成渗透测试报告`);
  console.log(`  ${chalk.cyan('/compact')}   压缩对话上下文`);
  console.log(`  ${chalk.cyan('/exit')}      退出（自动生成报告）`);
  console.log('');
}

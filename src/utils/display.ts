import chalk from 'chalk';
import { marked } from 'marked';

const SYMBOLS = {
  tool: '●',
  result: '⎿',
  thinking: '✻',
  spinner: ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
};

// --- Spinner ---

export class Spinner {
  private interval: ReturnType<typeof setInterval> | null = null;
  private frame = 0;
  private startTime = 0;
  private text = '';

  start(text: string) {
    this.text = text;
    this.frame = 0;
    this.startTime = Date.now();
    this.interval = setInterval(() => {
      const symbol = SYMBOLS.spinner[this.frame % SYMBOLS.spinner.length];
      const elapsed = Math.round((Date.now() - this.startTime) / 1000);
      const timeStr = elapsed > 0 ? ` ${elapsed}s` : '';
      process.stdout.write(`\r${chalk.magenta(SYMBOLS.thinking)} ${chalk.italic(this.text)}${chalk.gray(timeStr)}`);
      this.frame++;
    }, 80);
  }

  update(text: string) { this.text = text; }

  stop() {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }
    const elapsed = Math.round((Date.now() - this.startTime) / 1000);
    process.stdout.write('\r\x1b[K');
    if (elapsed >= 2) {
      console.log(`${chalk.magenta(SYMBOLS.thinking)} ${chalk.italic.gray(`Baked for ${elapsed}s`)}`);
    }
  }
}

// --- Tool display ---

export function displayToolStart(name: string, detail: string) {
  console.log(`\n${chalk.cyan(SYMBOLS.tool)} ${chalk.bold(name)}(${detail})`);
}

export function displayToolOutput(output: string, maxLines = 12) {
  if (!output.trim()) return;
  const lines = output.split('\n');
  const shown = lines.slice(0, maxLines);
  for (const line of shown) {
    console.log(`  ${chalk.dim(SYMBOLS.result)}  ${line}`);
  }
  if (lines.length > maxLines) {
    console.log(`  ${chalk.dim(SYMBOLS.result)}  ${chalk.dim(`... ${lines.length - maxLines} more lines`)}`);
  }
}

export function displayToolSuccess(summary: string) {
  console.log(`  ${chalk.dim(SYMBOLS.result)}  ${chalk.green(summary)}`);
}

export function displayToolFail(summary: string) {
  console.log(`  ${chalk.dim(SYMBOLS.result)}  ${chalk.red(summary)}`);
}

export function displayFileWrite(path: string, lineCount: number, preview: string[]) {
  displayToolSuccess(`Wrote ${lineCount} lines to ${path}`);
  for (let i = 0; i < Math.min(preview.length, 8); i++) {
    const num = chalk.dim(String(i + 1).padStart(6));
    console.log(`  ${chalk.dim(SYMBOLS.result)}  ${num} ${preview[i]}`);
  }
  if (lineCount > 8) {
    console.log(`  ${chalk.dim(SYMBOLS.result)}  ${chalk.dim(`       ... ${lineCount - 8} more lines`)}`);
  }
}

// --- Assistant text (markdown rendering via marked + chalk) ---

export function displayAssistantText(text: string) {
  const rendered = renderMarkdown(text);
  console.log(`\n${rendered}`);
}

function renderMarkdown(text: string): string {
  const tokens = marked.lexer(text);
  const lines: string[] = [];
  for (const token of tokens) {
    lines.push(...formatToken(token));
  }
  return lines.join('\n');
}

function formatToken(token: any): string[] {
  switch (token.type) {
    case 'heading':
      return [chalk.bold(inlineFormat(token.text)), ''];
    case 'paragraph':
      return [inlineFormat(token.text), ''];
    case 'code':
      return codeBlock(token.text, token.lang || '');
    case 'list':
      return listBlock(token);
    case 'blockquote': {
      const raw = (token.text || '').split('\n');
      return raw.map((l: string) => chalk.dim('▎ ') + chalk.italic(inlineFormat(l)));
    }
    case 'space':
      return [''];
    case 'hr':
      return [chalk.dim('─'.repeat(40)), ''];
    default:
      if ('text' in token && typeof token.text === 'string') {
        return [inlineFormat(token.text)];
      }
      return [];
  }
}

function codeBlock(code: string, lang: string): string[] {
  const highlighted = highlightCode(code, lang);
  const lines = highlighted.split('\n');
  const result: string[] = [];
  // 第一行带 ● 标记
  result.push(`${chalk.cyan(SYMBOLS.tool)} ${lines[0]}`);
  // 后续行缩进对齐
  for (let i = 1; i < lines.length; i++) {
    result.push(`  ${lines[i]}`);
  }
  result.push('');
  return result;
}

function listBlock(token: any): string[] {
  const lines: string[] = [];
  for (let i = 0; i < token.items.length; i++) {
    const item = token.items[i];
    const bullet = token.ordered ? chalk.dim(`${i + 1}.`) : chalk.dim('-');
    lines.push(`${bullet} ${inlineFormat(item.text)}`);
  }
  lines.push('');
  return lines;
}

// --- Inline formatting ---

function inlineFormat(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, (_, c) => chalk.bold(c))
    .replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, (_, c) => chalk.italic(c))
    .replace(/`([^`]+)`/g, (_, c) => chalk.cyan(c))
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, url) => chalk.underline.blue(label))
    .replace(/~~(.+?)~~/g, (_, c) => chalk.strikethrough(c));
}

// --- Code highlighting (chalk-based, no cli-highlight) ---

function highlightCode(code: string, lang: string): string {
  const lines = code.split('\n');
  return lines.map(line => highlightLine(line, lang)).join('\n');
}

function highlightLine(line: string, lang: string): string {
  if (lang === 'json' || (!lang && looksLikeJson(line))) {
    return highlightJson(line);
  }
  if (lang === 'bash' || lang === 'sh' || lang === 'shell') {
    return highlightBash(line);
  }
  if (lang === 'python' || lang === 'py') {
    return highlightPython(line);
  }
  if (lang === 'typescript' || lang === 'ts' || lang === 'javascript' || lang === 'js') {
    return highlightJs(line);
  }
  return highlightGeneric(line);
}

function looksLikeJson(line: string): boolean {
  const t = line.trim();
  return t.startsWith('{') || t.startsWith('[') || t.startsWith('"');
}

function highlightJson(line: string): string {
  let result = '';
  let i = 0;
  while (i < line.length) {
    if (line[i] === '"') {
      const end = findStringEnd(line, i);
      const str = line.slice(i, end + 1);
      // Check if this is a key (followed by :)
      const afterStr = line.slice(end + 1).trimStart();
      if (afterStr.startsWith(':')) {
        result += chalk.cyan(str);
      } else {
        result += chalk.green(str);
      }
      i = end + 1;
    } else if (/[0-9]/.test(line[i]) || (line[i] === '-' && /[0-9]/.test(line[i + 1] || ''))) {
      let numEnd = i + 1;
      while (numEnd < line.length && /[0-9.eE+-]/.test(line[numEnd])) numEnd++;
      result += chalk.yellow(line.slice(i, numEnd));
      i = numEnd;
    } else if (line.slice(i, i + 4) === 'true' || line.slice(i, i + 5) === 'false') {
      const word = line.slice(i, i + 4) === 'true' ? 'true' : 'false';
      result += chalk.yellow(word);
      i += word.length;
    } else if (line.slice(i, i + 4) === 'null') {
      result += chalk.dim('null');
      i += 4;
    } else if (line[i] === '{' || line[i] === '}' || line[i] === '[' || line[i] === ']') {
      result += chalk.white(line[i]);
      i++;
    } else {
      result += line[i];
      i++;
    }
  }
  return result;
}

function findStringEnd(line: string, start: number): number {
  let i = start + 1;
  while (i < line.length) {
    if (line[i] === '\\') { i += 2; continue; }
    if (line[i] === '"') return i;
    i++;
  }
  return line.length - 1;
}

function highlightBash(line: string): string {
  if (line.trimStart().startsWith('#')) return chalk.dim(line);
  return line
    .replace(/^(\s*\$\s*)/g, (m) => chalk.green(m))
    .replace(/\b(sudo|apt|yum|pip|npm|bun|git|docker|nmap|curl|wget|ssh|cat|grep|find|ls|cd|rm|cp|mv|echo|export|set|source|chmod|chown|kill|ps|top|tar|unzip|make|gcc|python3?|node|go|cargo)\b/g, (m) => chalk.cyan(m))
    .replace(/(--[\w-]+|-[a-zA-Z])\b/g, (m) => chalk.yellow(m))
    .replace(/"([^"]*)"/g, (_, c) => chalk.green(`"${c}"`))
    .replace(/'([^']*)'/g, (_, c) => chalk.green(`'${c}'`));
}

function highlightPython(line: string): string {
  if (line.trimStart().startsWith('#')) return chalk.dim(line);
  return line
    .replace(/\b(def|class|import|from|return|if|else|elif|for|while|try|except|finally|with|as|in|not|and|or|is|lambda|yield|raise|pass|break|continue|True|False|None)\b/g, (m) => chalk.magenta(m))
    .replace(/"([^"]*)"/g, (_, c) => chalk.green(`"${c}"`))
    .replace(/'([^']*)'/g, (_, c) => chalk.green(`'${c}'`))
    .replace(/\b(\d+\.?\d*)\b/g, (m) => chalk.yellow(m));
}

function highlightJs(line: string): string {
  if (line.trimStart().startsWith('//')) return chalk.dim(line);
  return line
    .replace(/\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|import|export|from|default|class|extends|new|this|super|async|await|try|catch|finally|throw|typeof|instanceof|void|delete|in|of|true|false|null|undefined)\b/g, (m) => chalk.magenta(m))
    .replace(/"([^"]*)"/g, (_, c) => chalk.green(`"${c}"`))
    .replace(/'([^']*)'/g, (_, c) => chalk.green(`'${c}'`))
    .replace(/`([^`]*)`/g, (_, c) => chalk.green(`\`${c}\``))
    .replace(/\b(\d+\.?\d*)\b/g, (m) => chalk.yellow(m));
}

function highlightGeneric(line: string): string {
  return line
    .replace(/"([^"]*)"/g, (_, c) => chalk.green(`"${c}"`))
    .replace(/'([^']*)'/g, (_, c) => chalk.green(`'${c}'`))
    .replace(/\b(true|false|null|none|nil|undefined)\b/gi, (m) => chalk.yellow(m))
    .replace(/\b(\d+\.?\d*)\b/g, (m) => chalk.yellow(m));
}

// --- Token info ---

export function displayTokenInfo(input: number, output: number, elapsed: number) {
  const total = input + output;
  const fmt = (n: number) => {
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return String(n);
  };
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  console.log(chalk.dim(`\n  ${fmt(total)} tokens │ ${min}:${String(sec).padStart(2, '0')}`));
}

// --- Slash menu ---

export function displaySlashMenu() {
  console.log('');
  console.log(chalk.bold('  Slash commands:'));
  console.log(`    ${chalk.cyan('/status')}    Show current status`);
  console.log(`    ${chalk.cyan('/env')}       Show execution environment`);
  console.log(`    ${chalk.cyan('/skill')}     Manage skills`);
  console.log(`    ${chalk.cyan('/mcp')}       Show MCP connections`);
  console.log(`    ${chalk.cyan('/report')}    Generate pentest report`);
  console.log(`    ${chalk.cyan('/compact')}   Compress conversation context`);
  console.log(`    ${chalk.cyan('/exit')}      Exit (auto-generates report)`);
  console.log('');
}

import chalk from 'chalk';

// 工具调用显示符号
const SYMBOLS = {
  tool: '●',
  result: '⎿',
  success: '✓',
  fail: '✗',
  spinner: ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
  arrow: '▶',
  indent: '  ',
};

export class Spinner {
  private interval: ReturnType<typeof setInterval> | null = null;
  private frame = 0;
  private text = '';

  start(text: string) {
    this.text = text;
    this.frame = 0;
    this.interval = setInterval(() => {
      const symbol = SYMBOLS.spinner[this.frame % SYMBOLS.spinner.length];
      process.stdout.write(`\r${chalk.cyan(symbol)} ${chalk.gray(this.text)}`);
      this.frame++;
    }, 80);
  }

  update(text: string) {
    this.text = text;
  }

  stop(success = true) {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }
    process.stdout.write('\r\x1b[K');
  }
}

export function displayToolStart(name: string, detail: string) {
  console.log(`\n${chalk.cyan(SYMBOLS.tool)} ${chalk.bold.white(name)}${chalk.gray('(')}${chalk.yellow(detail)}${chalk.gray(')')}`);
}

export function displayToolOutput(output: string, maxLines = 12) {
  if (!output.trim()) return;
  const lines = output.split('\n');
  const shown = lines.slice(0, maxLines);
  for (const line of shown) {
    console.log(`${SYMBOLS.indent}${chalk.gray(SYMBOLS.result)}  ${highlightLine(line)}`);
  }
  if (lines.length > maxLines) {
    console.log(`${SYMBOLS.indent}${chalk.gray(SYMBOLS.result)}  ${chalk.gray(`... ${lines.length - maxLines} more lines`)}`);
  }
}

export function displayToolSuccess(summary: string) {
  console.log(`${SYMBOLS.indent}${chalk.gray(SYMBOLS.result)}  ${chalk.green(SYMBOLS.success)} ${chalk.green(summary)}`);
}

export function displayToolFail(summary: string) {
  console.log(`${SYMBOLS.indent}${chalk.gray(SYMBOLS.result)}  ${chalk.red(SYMBOLS.fail)} ${chalk.red(summary)}`);
}

export function displayFileWrite(path: string, content: string) {
  const lines = content.split('\n');
  const lineCount = lines.length;
  displayToolSuccess(`Wrote ${lineCount} lines to ${path}`);
  const shown = lines.slice(0, 8);
  for (let i = 0; i < shown.length; i++) {
    const num = chalk.gray(String(i + 1).padStart(6));
    console.log(`${SYMBOLS.indent}${chalk.gray(SYMBOLS.result)}  ${num} ${highlightLine(shown[i])}`);
  }
  if (lines.length > 8) {
    console.log(`${SYMBOLS.indent}${chalk.gray(SYMBOLS.result)}  ${chalk.gray(`       ... ${lines.length - 8} more lines`)}`);
  }
}

export function displayAssistantText(text: string) {
  const formatted = highlightMarkdown(text);
  console.log(`\n${formatted}`);
}

function highlightLine(line: string): string {
  line = line
    .replace(/\b(error|Error|ERROR|FAIL|failed|Failed)\b/g, chalk.red('$1'))
    .replace(/\b(success|Success|SUCCESS|PASS|passed|Passed|ok|OK)\b/g, chalk.green('$1'))
    .replace(/\b(warning|Warning|WARN)\b/g, chalk.yellow('$1'))
    .replace(/\b(\d+\.\d+\.\d+\.\d+)\b/g, chalk.cyan('$1'))
    .replace(/\b(\d+\/tcp|(\d+)\/udp)\b/g, chalk.yellow('$1'))
    .replace(/(https?:\/\/[^\s]+)/g, chalk.underline.blue('$1'));
  return line;
}

function highlightMarkdown(text: string): string {
  return text
    .replace(/^(#{1,3})\s+(.+)$/gm, (_, hashes, title) => chalk.bold.white(title))
    .replace(/\*\*(.+?)\*\*/g, (_, content) => chalk.bold.white(content))
    .replace(/`([^`]+)`/g, (_, code) => chalk.cyan(code))
    .replace(/^- (.+)$/gm, (_, item) => `  ${chalk.gray('•')} ${item}`)
    .replace(/^\d+\.\s+(.+)$/gm, (_, item) => `  ${chalk.gray('›')} ${item}`);
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

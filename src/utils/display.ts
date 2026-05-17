import chalk from 'chalk';

const SYMBOLS = {
  tool: '●',
  result: '⎿',
  success: '✓',
  fail: '✗',
  thinking: '✻',
  spinner: ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
};

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

  update(text: string) {
    this.text = text;
  }

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

export function displayToolStart(name: string, detail: string) {
  console.log(`\n${chalk.cyan(SYMBOLS.tool)} ${chalk.bold(name)}(${detail})`);
}

export function displayToolOutput(output: string, maxLines = 12) {
  if (!output.trim()) return;
  const lines = output.split('\n');
  const shown = lines.slice(0, maxLines);
  for (const line of shown) {
    console.log(`  ${chalk.gray(SYMBOLS.result)}  ${line}`);
  }
  if (lines.length > maxLines) {
    console.log(`  ${chalk.gray(SYMBOLS.result)}  ${chalk.gray(`... ${lines.length - maxLines} more lines`)}`);
  }
}

export function displayToolSuccess(summary: string) {
  console.log(`  ${chalk.gray(SYMBOLS.result)}  ${chalk.green(summary)}`);
}

export function displayToolFail(summary: string) {
  console.log(`  ${chalk.gray(SYMBOLS.result)}  ${chalk.red(SYMBOLS.fail)} ${summary}`);
}

export function displayFileWrite(path: string, lineCount: number, preview: string[]) {
  displayToolSuccess(`Wrote ${lineCount} lines to ${path}`);
  for (let i = 0; i < Math.min(preview.length, 8); i++) {
    const num = chalk.gray(String(i + 1).padStart(6));
    console.log(`  ${chalk.gray(SYMBOLS.result)}  ${num} ${preview[i]}`);
  }
  if (lineCount > 8) {
    console.log(`  ${chalk.gray(SYMBOLS.result)}  ${chalk.gray(`       ... ${lineCount - 8} more lines`)}`);
  }
}

// 助手文本直接输出，不做额外处理
export function displayAssistantText(text: string) {
  console.log(`\n${text}`);
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

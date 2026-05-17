import chalk from 'chalk';

export type Phase = 'recon' | 'enum' | 'exploit' | 'post' | 'report' | 'general';

export const PHASE_COLORS: Record<Phase, (text: string) => string> = {
  recon: chalk.blue,
  enum: chalk.cyan,
  exploit: chalk.red,
  post: chalk.magenta,
  report: chalk.green,
  general: chalk.white,
};

export const PHASE_LABELS: Record<Phase, string> = {
  recon: '侦察',
  enum: '枚举',
  exploit: '利用',
  post: '后渗透',
  report: '报告',
  general: '通用',
};

export function detectPhase(text: string): Phase {
  const lower = text.toLowerCase();
  if (/nmap|masscan|subfinder|amass|recon|scan|discover/.test(lower)) return 'recon';
  if (/enum|fuzz|gobuster|ffuf|hydra|spray|brute/.test(lower)) return 'enum';
  if (/exploit|sqlmap|xss|ssti|ssrf|rce|shell|payload/.test(lower)) return 'exploit';
  if (/privesc|lateral|persist|exfil|pivot|mimikatz/.test(lower)) return 'post';
  if (/report|summary|finding/.test(lower)) return 'report';
  return 'general';
}

export function formatTokens(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function tokenColor(used: number, total: number): (text: string) => string {
  const pct = used / total;
  if (pct >= 0.95) return chalk.red;
  if (pct >= 0.80) return chalk.yellow;
  return chalk.gray;
}

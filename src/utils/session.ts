import { mkdirSync, writeFileSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';
import { WeaverConfig } from '../types/config';
import { Conversation, Message, ContentBlock } from '../query/query';

export interface SessionRecord {
  startTime: number;
  endTime: number;
  config: { model: string; backend: string };
  tokenUsage: { input: number; output: number };
  timeline: TimelineEntry[];
}

export interface TimelineEntry {
  timestamp: number;
  type: 'user_input' | 'tool_call' | 'assistant_text';
  content: string;
}

export function buildTimeline(conversation: Conversation): TimelineEntry[] {
  const timeline: TimelineEntry[] = [];

  for (const msg of conversation.messages) {
    if (typeof msg.content === 'string') {
      timeline.push({
        timestamp: Date.now(),
        type: 'user_input',
        content: msg.content,
      });
    } else if (Array.isArray(msg.content)) {
      for (const block of msg.content) {
        if (block.type === 'text') {
          timeline.push({
            timestamp: Date.now(),
            type: 'assistant_text',
            content: block.text.slice(0, 200),
          });
        } else if (block.type === 'tool_use') {
          const input = block.input.command
            ? String(block.input.command)
            : JSON.stringify(block.input).slice(0, 100);
          timeline.push({
            timestamp: Date.now(),
            type: 'tool_call',
            content: `${block.name}: ${input}`,
          });
        }
      }
    }
  }

  return timeline;
}

export function generateReport(conversation: Conversation, config: WeaverConfig): string {
  const now = new Date();
  const start = new Date(conversation.startTime);
  const duration = Math.round((now.getTime() - start.getTime()) / 1000);
  const minutes = Math.floor(duration / 60);
  const seconds = duration % 60;

  const timeline = buildTimeline(conversation);
  const toolCalls = timeline.filter(e => e.type === 'tool_call');
  const userInputs = timeline.filter(e => e.type === 'user_input');

  let report = `# 渗透测试报告\n\n`;
  report += `- 时间: ${start.toLocaleString()} ~ ${now.toLocaleString()}\n`;
  report += `- 时长: ${minutes}分${seconds}秒\n`;
  report += `- 模型: ${config.model}\n`;
  report += `- 后端: ${config.backend.type}\n`;
  report += `- Token: 输入 ${conversation.tokenUsage.input} / 输出 ${conversation.tokenUsage.output}\n\n`;

  report += `## 执行摘要\n\n`;
  report += `- 用户交互: ${userInputs.length} 次\n`;
  report += `- 工具调用: ${toolCalls.length} 次\n\n`;

  report += `## 操作时间线\n\n`;
  report += `| 类型 | 内容 |\n`;
  report += `|------|------|\n`;
  for (const entry of timeline.slice(-50)) {
    const typeLabel = entry.type === 'user_input' ? '输入'
      : entry.type === 'tool_call' ? '执行'
      : '回复';
    const content = entry.content.replace(/\|/g, '\\|').replace(/\n/g, ' ').slice(0, 80);
    report += `| ${typeLabel} | ${content} |\n`;
  }

  return report;
}

export function saveReport(report: string, config: WeaverConfig): string {
  const reportsDir = config.reportsDir.replace('~', homedir());
  mkdirSync(reportsDir, { recursive: true });

  const date = new Date().toISOString().slice(0, 10);
  const filename = `${date}_session.md`;
  const filepath = join(reportsDir, filename);

  writeFileSync(filepath, report, 'utf-8');
  return filepath;
}

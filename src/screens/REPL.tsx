import React, { useState, useCallback, useRef } from 'react';
import { render, Box, Text, useApp, useInput } from 'ink';
import { WeaverConfig } from '../types/config';
import { ToolDefinition } from '../types/tool';
import { Skill } from '../skills/types';
import { McpManager } from '../services/mcp';
import { Conversation } from '../query/query';
import { Phase, detectPhase, PHASE_LABELS, formatTokens } from '../components/theme';
import { MessageEntry } from '../components/MessageList';
import { queryWithCallbacks } from '../query/queryInk';
import { generateReport, saveReport } from '../utils/session';

interface ReplProps {
  config: WeaverConfig;
  tools: ToolDefinition[];
  skills: Skill[];
  mcp: McpManager;
}

function WeaverApp({ config, tools, skills, mcp }: ReplProps) {
  const { exit } = useApp();
  const [messages, setMessages] = useState<MessageEntry[]>([]);
  const [phase, setPhase] = useState<Phase>('general');
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentTask, setCurrentTask] = useState('');
  const [input, setInput] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const conversationRef = useRef<Conversation>({
    messages: [],
    startTime: Date.now(),
    tokenUsage: { input: 0, output: 0 },
  });

  React.useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(Math.round((Date.now() - conversationRef.current.startTime) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const addMessage = useCallback((entry: MessageEntry) => {
    setMessages(prev => [...prev.slice(-50), entry]);
  }, []);

  const handleSubmit = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isProcessing) return;
    setInput('');

    if (trimmed === '/exit' || trimmed === 'exit') {
      const conv = conversationRef.current;
      if (conv.messages.length > 0) {
        addMessage({ role: 'tool', text: '正在生成本次任务报告...' });
        const report = generateReport(conv, config);
        const filepath = saveReport(report, config);
        addMessage({ role: 'tool', text: `报告已保存至: ${filepath}` });
      }
      setTimeout(() => { exit(); process.exit(0); }, 500);
      return;
    }

    if (trimmed === '/status') {
      const conv = conversationRef.current;
      const { input: inp, output: out } = conv.tokenUsage;
      addMessage({ role: 'tool', text: `模型: ${config.model} │ 后端: ${config.backend.type} │ Token: ${formatTokens(inp + out)} │ Skills: ${skills.length}` });
      return;
    }

    if (trimmed === '/skill' || trimmed.startsWith('/skill ')) {
      const parts = trimmed.split(/\s+/);
      const sub = parts[1] || 'list';
      if (sub === 'list') {
        const list = skills.map(s => `  ${s.enabled ? '●' : '○'} ${s.metadata.name} [${s.source}]`).join('\n');
        addMessage({ role: 'tool', text: list || '(无 skill)' });
      }
      return;
    }

    if (trimmed === '/compact') {
      const conv = conversationRef.current;
      if (conv.messages.length <= 4) {
        addMessage({ role: 'tool', text: '对话太短，无需压缩' });
        return;
      }
      const keepRecent = 4;
      const old = conv.messages.slice(0, conv.messages.length - keepRecent);
      const recent = conv.messages.slice(conv.messages.length - keepRecent);
      let summary = '[上下文压缩摘要]\n';
      for (const msg of old) {
        if (typeof msg.content === 'string') summary += `- 用户: ${msg.content.slice(0, 80)}\n`;
      }
      conv.messages = [
        { role: 'user', content: summary },
        { role: 'assistant', content: [{ type: 'text', text: '已了解上下文，继续。' }] },
        ...recent,
      ];
      addMessage({ role: 'tool', text: `已压缩，保留最近 ${keepRecent} 条 + 摘要` });
      return;
    }

    addMessage({ role: 'user', text: trimmed });
    setIsProcessing(true);
    setCurrentTask(trimmed.slice(0, 40));
    setPhase(detectPhase(trimmed));

    try {
      await queryWithCallbacks(trimmed, conversationRef.current, { config, tools, skills }, {
        onText: (text) => {
          addMessage({ role: 'assistant', text });
          setPhase(detectPhase(text));
        },
        onToolStart: (name, input) => {
          const label = input.command ? String(input.command).slice(0, 60) : name;
          addMessage({ role: 'tool', text: `[执行] ${name}: ${label}` });
          setCurrentTask(`${name}: ${label.slice(0, 30)}`);
        },
        onToolEnd: (output) => {
          if (output) {
            const lines = output.split('\n').slice(0, 8).join('\n');
            addMessage({ role: 'tool', text: lines });
          }
        },
      });
    } catch (err: any) {
      addMessage({ role: 'error', text: err.message });
    }

    setIsProcessing(false);
    setCurrentTask('');
  }, [input, isProcessing, config, tools, skills, addMessage, exit]);

  useInput((ch, key) => {
    if (key.return) {
      handleSubmit();
      return;
    }
    if (key.backspace || key.delete) {
      setInput(prev => prev.slice(0, -1));
      return;
    }
    if (key.ctrl && ch === 'c') {
      exit();
      process.exit(0);
    }
    if (ch && !key.ctrl && !key.meta && !key.escape) {
      setInput(prev => prev + ch);
    }
  });

  const conv = conversationRef.current;
  const { input: tokIn, output: tokOut } = conv.tokenUsage;
  const tokTotal = tokIn + tokOut;
  const contextMax = 200000;
  const pct = Math.round((tokTotal / contextMax) * 100);
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  const timeStr = `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;

  const phaseColor = ({ recon: 'blue', enum: 'cyan', exploit: 'red', post: 'magenta', report: 'green', general: 'white' } as const)[phase];

  const visibleMessages = messages.slice(-20);

  return (
    <Box flexDirection="column" width="100%">
      {/* 状态面板 */}
      <Box borderStyle="single" borderColor="gray" paddingX={1} flexDirection="column">
        <Box>
          <Text color="gray">后端: </Text>
          <Text color="white">{formatBackendShort(config)}</Text>
          <Text color="gray">  │  阶段: </Text>
          <Text color={phaseColor}>{PHASE_LABELS[phase]}</Text>
          <Text color="gray">  │  Token: </Text>
          <Text color={pct >= 95 ? 'red' : pct >= 80 ? 'yellow' : 'white'}>{formatTokens(tokTotal)}/{formatTokens(contextMax)} ({pct}%)</Text>
        </Box>
        <Box>
          <Text color="gray">模型: </Text>
          <Text color="white">{config.model}</Text>
          <Text color="gray">  │  Skills: </Text>
          <Text color="white">{skills.length}</Text>
          {mcp.clients.size > 0 && <><Text color="gray">  │  MCP: </Text><Text color="green">{mcp.clients.size}</Text></>}
        </Box>
      </Box>

      {/* 消息流 */}
      <Box flexDirection="column" paddingX={1} marginY={1}>
        {visibleMessages.map((msg, i) => (
          <Box key={i}>
            {msg.role === 'user' && <Text><Text color="green" bold>{'> '}</Text><Text color="green">{msg.text}</Text></Text>}
            {msg.role === 'assistant' && <Text color={phaseColor}>{msg.text}</Text>}
            {msg.role === 'tool' && <Text color="gray">{msg.text}</Text>}
            {msg.role === 'error' && <Text color="red">{msg.text}</Text>}
          </Box>
        ))}
      </Box>

      {/* 状态栏 */}
      <Box borderStyle="single" borderColor="gray" paddingX={1}>
        <Text color={phaseColor} bold>[{PHASE_LABELS[phase]}]</Text>
        <Text color="gray"> </Text>
        {isProcessing ? (
          <><Text color="yellow">▶ </Text><Text color="white">{currentTask}</Text></>
        ) : (
          <Text color="gray">idle</Text>
        )}
        <Text color="gray"> │ {formatTokens(tokTotal)} │ {timeStr}</Text>
      </Box>

      {/* 输入框 */}
      <Box borderStyle="round" borderColor={isProcessing ? 'gray' : phaseColor} paddingX={1}>
        <Text color={phaseColor} bold>weaver{'>'} </Text>
        <Text color="white">{input}</Text>
        {!isProcessing && <Text color={phaseColor}>█</Text>}
        {isProcessing && <Text color="yellow"> 处理中...</Text>}
      </Box>
    </Box>
  );
}

function formatBackendShort(config: WeaverConfig): string {
  const b = config.backend;
  switch (b.type) {
    case 'local': return 'local';
    case 'wsl': return `wsl://${b.distro}`;
    case 'ssh': return `ssh://${b.user}@${b.host}`;
    case 'docker': return `docker://${b.container}`;
  }
}

export function startInkRepl(options: ReplProps) {
  render(<WeaverApp {...options} />);
}

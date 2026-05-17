import React from 'react';
import { Box, Text } from 'ink';
import { WeaverConfig } from '../types/config';
import { Conversation } from '../query/query';
import { Skill } from '../skills/types';
import { McpManager } from '../services/mcp';
import { Phase, PHASE_LABELS, formatTokens } from './theme';

interface StatusPanelProps {
  config: WeaverConfig;
  conversation: Conversation;
  phase: Phase;
  skills: Skill[];
  mcp: McpManager;
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

export function StatusPanel({ config, conversation, phase, skills, mcp }: StatusPanelProps) {
  const { input, output } = conversation.tokenUsage;
  const total = input + output;
  const contextMax = 200000;
  const pct = Math.round((total / contextMax) * 100);

  return (
    <Box flexDirection="column" borderStyle="single" borderColor="gray" paddingX={1}>
      <Box>
        <Text color="gray">后端: </Text>
        <Text color="white">{formatBackend(config)}</Text>
        <Text color="gray">  │  </Text>
        <Text color="gray">阶段: </Text>
        <Text color={phaseToInkColor(phase)}>{PHASE_LABELS[phase]}</Text>
        <Text color="gray">  │  </Text>
        <Text color="gray">Token: </Text>
        <Text color={pct >= 95 ? 'red' : pct >= 80 ? 'yellow' : 'white'}>
          {formatTokens(total)} / {formatTokens(contextMax)} ({pct}%)
        </Text>
      </Box>
      <Box>
        <Text color="gray">模型: </Text>
        <Text color="white">{config.model}</Text>
        <Text color="gray">  │  </Text>
        <Text color="gray">Skills: </Text>
        <Text color="white">{skills.filter(s => s.enabled).length}</Text>
        {mcp.clients.size > 0 && (
          <>
            <Text color="gray">  │  </Text>
            <Text color="gray">MCP: </Text>
            <Text color="green">{mcp.clients.size}</Text>
          </>
        )}
      </Box>
    </Box>
  );
}

function phaseToInkColor(phase: Phase): string {
  const map: Record<Phase, string> = {
    recon: 'blue',
    enum: 'cyan',
    exploit: 'red',
    post: 'magenta',
    report: 'green',
    general: 'white',
  };
  return map[phase];
}

import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import { Conversation } from '../query/query';
import { Phase, PHASE_LABELS, formatTokens } from './theme';

interface StatusBarProps {
  phase: Phase;
  conversation: Conversation;
  isProcessing: boolean;
  currentTask: string;
}

function phaseColor(phase: Phase): string {
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

export function StatusBar({ phase, conversation, isProcessing, currentTask }: StatusBarProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(Math.round((Date.now() - conversation.startTime) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [conversation.startTime]);

  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  const timeStr = `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;

  const { input, output } = conversation.tokenUsage;
  const total = input + output;

  return (
    <Box borderStyle="single" borderColor="gray" paddingX={1}>
      <Text color={phaseColor(phase)} bold>[{PHASE_LABELS[phase]}]</Text>
      <Text color="gray"> </Text>
      {isProcessing ? (
        <>
          <Text color="yellow">▶ </Text>
          <Text color="white">{currentTask}</Text>
        </>
      ) : (
        <Text color="gray">idle</Text>
      )}
      <Text color="gray"> │ </Text>
      <Text color="gray">{formatTokens(total)} tokens</Text>
      <Text color="gray"> │ </Text>
      <Text color="gray">{timeStr}</Text>
    </Box>
  );
}

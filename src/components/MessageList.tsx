import React from 'react';
import { Box, Text } from 'ink';
import { Phase } from './theme';

export interface MessageEntry {
  role: 'user' | 'assistant' | 'tool' | 'error';
  text: string;
}

interface MessageListProps {
  messages: MessageEntry[];
  phase: Phase;
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

export function MessageList({ messages, phase }: MessageListProps) {
  const visible = messages.slice(-30);

  return (
    <Box flexDirection="column">
      {visible.map((msg, i) => (
        <Box key={i} marginBottom={0}>
          {msg.role === 'user' && (
            <Text>
              <Text color="green" bold>{'> '}</Text>
              <Text color="green">{msg.text}</Text>
            </Text>
          )}
          {msg.role === 'assistant' && (
            <Text color={phaseColor(phase)}>{msg.text}</Text>
          )}
          {msg.role === 'tool' && (
            <Text color="gray">{msg.text}</Text>
          )}
          {msg.role === 'error' && (
            <Text color="red">{msg.text}</Text>
          )}
        </Box>
      ))}
    </Box>
  );
}

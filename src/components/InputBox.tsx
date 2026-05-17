import React, { useState } from 'react';
import { Box, Text, useInput } from 'ink';
import { Phase } from './theme';

interface InputBoxProps {
  phase: Phase;
  isProcessing: boolean;
  onSubmit: (input: string) => void;
}

function phaseColor(phase: Phase): string {
  const map: Record<Phase, string> = {
    recon: 'blue',
    enum: 'cyan',
    exploit: 'red',
    post: 'magenta',
    report: 'green',
    general: 'green',
  };
  return map[phase];
}

export function InputBox({ phase, isProcessing, onSubmit }: InputBoxProps) {
  const [input, setInput] = useState('');

  useInput((ch, key) => {
    if (isProcessing) return;

    if (key.return) {
      if (input.trim()) {
        onSubmit(input);
        setInput('');
      }
      return;
    }

    if (key.backspace || key.delete) {
      setInput(prev => prev.slice(0, -1));
      return;
    }

    if (key.ctrl && ch === 'c') {
      process.exit(0);
    }

    if (ch && !key.ctrl && !key.meta) {
      setInput(prev => prev + ch);
    }
  });

  const color = phaseColor(phase);

  return (
    <Box borderStyle="round" borderColor={isProcessing ? 'gray' : color} paddingX={1}>
      <Text color={color} bold>weaver{'>'} </Text>
      <Text color="white">{input}</Text>
      {!isProcessing && <Text color={color}>█</Text>}
      {isProcessing && <Text color="yellow"> 处理中...</Text>}
    </Box>
  );
}

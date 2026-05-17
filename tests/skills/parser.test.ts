import { describe, test, expect } from 'bun:test';
import { parseSkillFile } from '../../src/skills/parser';

describe('parseSkillFile', () => {
  test('解析完整 frontmatter', () => {
    const raw = `---
name: test-skill
description: 测试 skill
when_to_use: 测试时使用
allowed-tools: [Bash, Read, Write]
argument-hint: "<target>"
user-invocable: true
context: inline
---

## 内容

这是 skill 内容。`;

    const { metadata, content } = parseSkillFile(raw);
    expect(metadata.name).toBe('test-skill');
    expect(metadata.description).toBe('测试 skill');
    expect(metadata.whenToUse).toBe('测试时使用');
    expect(metadata.allowedTools).toEqual(['Bash', 'Read', 'Write']);
    expect(metadata.userInvocable).toBe(true);
    expect(metadata.context).toBe('inline');
    expect(content).toContain('## 内容');
  });

  test('缺少 name 字段时抛出错误', () => {
    const raw = `---
description: no name
---

content`;

    expect(() => parseSkillFile(raw)).toThrow('missing required field: name');
  });

  test('缺少 frontmatter 时抛出错误', () => {
    expect(() => parseSkillFile('no frontmatter')).toThrow('missing frontmatter');
  });

  test('$ARGUMENTS 替换', () => {
    const raw = `---
name: args-test
description: test args
arguments: [target]
---

Run: nmap $ARGUMENTS`;

    const { content } = parseSkillFile(raw);
    expect(content).toContain('$ARGUMENTS');
  });
});

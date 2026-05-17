import { SkillMetadata } from './types';

// 解析 markdown frontmatter，提取 skill 元数据和内容
export function parseSkillFile(raw: string): { metadata: SkillMetadata; content: string } {
  const frontmatterMatch = raw.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);

  if (!frontmatterMatch) {
    throw new Error('Invalid skill file: missing frontmatter');
  }

  const [, yamlBlock, content] = frontmatterMatch;
  const metadata = parseYamlBlock(yamlBlock);

  return { metadata, content: content.trim() };
}

function parseYamlBlock(yaml: string): SkillMetadata {
  const lines = yaml.split('\n');
  const result: Record<string, any> = {};

  for (const line of lines) {
    const match = line.match(/^(\w[\w-]*):\s*(.*)$/);
    if (!match) continue;

    const [, key, value] = match;
    const normalizedKey = camelCase(key);

    if (value.startsWith('[') || value.startsWith('"[')) {
      result[normalizedKey] = parseInlineArray(value);
    } else if (value === 'true') {
      result[normalizedKey] = true;
    } else if (value === 'false') {
      result[normalizedKey] = false;
    } else {
      result[normalizedKey] = value.replace(/^["']|["']$/g, '');
    }
  }

  if (!result.name) throw new Error('Skill missing required field: name');
  if (!result.description) throw new Error('Skill missing required field: description');

  return result as SkillMetadata;
}

function parseInlineArray(value: string): string[] {
  const cleaned = value.replace(/^\[|\]$/g, '').trim();
  if (!cleaned) return [];
  return cleaned.split(',').map(s => s.trim().replace(/^["']|["']$/g, ''));
}

function camelCase(str: string): string {
  return str.replace(/[-_]([a-z])/g, (_, c) => c.toUpperCase());
}

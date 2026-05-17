// Skill 元数据（从 frontmatter 解析）
export interface SkillMetadata {
  name: string;
  description: string;
  whenToUse?: string;
  allowedTools?: string[];
  argumentHint?: string;
  arguments?: string[];
  userInvocable?: boolean;
  context?: 'inline' | 'fork';
  model?: string;
  paths?: string[];
}

// 完整 Skill 定义
export interface Skill {
  metadata: SkillMetadata;
  content: string;
  filePath: string;
  source: 'bundled' | 'user' | 'project';
  enabled: boolean;
}

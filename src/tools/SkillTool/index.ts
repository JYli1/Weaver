import chalk from 'chalk';
import { ToolDefinition, ToolResult } from '../../types/tool';
import { Skill } from '../../skills/types';
import { findSkill } from '../../skills/loader';

export function createSkillTool(skills: Skill[]): ToolDefinition {
  return {
    name: 'Skill',
    description: '调用已加载的 skill。Skill 提供渗透测试方法论、工具使用指南和决策树。',
    inputSchema: {
      type: 'object',
      properties: {
        skill: { type: 'string', description: 'skill 名称' },
        args: { type: 'string', description: '传递给 skill 的参数（可选）' },
      },
      required: ['skill'],
    },
    async execute(input): Promise<ToolResult> {
      const name = input.skill as string;
      const args = (input.args as string) || '';

      const skill = findSkill(skills, name);
      if (!skill) {
        const available = skills.filter(s => s.enabled).map(s => s.metadata.name);
        return {
          output: `Skill "${name}" not found. Available: ${available.join(', ') || '(none)'}`,
          exitCode: 1,
        };
      }

      console.log(chalk.magenta(`  [Skill] ${name}`));

      let content = skill.content;
      if (args) {
        content = content.replace(/\$ARGUMENTS/g, args);
      }

      return { output: content, exitCode: 0 };
    },
  };
}

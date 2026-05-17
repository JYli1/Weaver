import chalk from 'chalk';
import { ToolDefinition, ToolResult } from '../../types/tool';
import { Skill } from '../../skills/types';
import { findSkill } from '../../skills/loader';

export function createSkillTool(skills: Skill[]): ToolDefinition {
  return {
    name: 'Skill',
    description: `Execute a skill within the main conversation

When users ask you to perform tasks, check if any of the available skills match. Skills provide specialized capabilities and domain knowledge.

When users reference a "slash command" or "/<something>", they are referring to a skill. Use this tool to invoke it.

How to invoke:
- Set \`skill\` to the exact name of an available skill (no leading slash).
- Set \`args\` to pass optional arguments.

Important:
- Available skills are listed in system-reminder messages in the conversation
- Only invoke a skill that appears in that list
- When a skill matches the user's request, this is a BLOCKING REQUIREMENT: invoke the relevant Skill tool BEFORE generating any other response about the task
- NEVER mention a skill without actually calling this tool
- Do not invoke a skill that is already running`,
    inputSchema: {
      type: 'object',
      properties: {
        skill: { type: 'string', description: 'The name of a skill from the available-skills list. Do not guess names.' },
        args: { type: 'string', description: 'Optional arguments for the skill' },
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

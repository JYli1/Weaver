import { readdirSync, readFileSync, existsSync, statSync } from 'fs';
import { join, resolve } from 'path';
import { homedir } from 'os';
import { Skill } from './types';
import { parseSkillFile } from './parser';

// 三层加载源（优先级：项目级 > 用户全局 > 内置）
function getSkillDirs(): { path: string; source: Skill['source'] }[] {
  return [
    { path: resolve(__dirname, '../skills/bundled'), source: 'bundled' },
    { path: join(homedir(), '.weaver', 'skills'), source: 'user' },
    { path: join(process.cwd(), '.weaver', 'skills'), source: 'project' },
  ];
}

export function loadAllSkills(): Skill[] {
  const dirs = getSkillDirs();
  const skillMap = new Map<string, Skill>();

  for (const { path: dir, source } of dirs) {
    if (!existsSync(dir)) continue;
    const skills = loadSkillsFromDir(dir, source);
    for (const skill of skills) {
      skillMap.set(skill.metadata.name, skill);
    }
  }

  return Array.from(skillMap.values());
}

function loadSkillsFromDir(dir: string, source: Skill['source']): Skill[] {
  const skills: Skill[] = [];
  const entries = readdirSync(dir);

  for (const entry of entries) {
    const fullPath = join(dir, entry);
    const stat = statSync(fullPath);

    if (stat.isFile() && entry.endsWith('.md')) {
      const skill = loadSingleFileSkill(fullPath, source);
      if (skill) skills.push(skill);
    } else if (stat.isDirectory()) {
      const skillMd = join(fullPath, 'SKILL.md');
      if (existsSync(skillMd)) {
        const skill = loadSingleFileSkill(skillMd, source);
        if (skill) skills.push(skill);
      } else {
        skills.push(...loadSkillsFromDir(fullPath, source));
      }
    }
  }

  return skills;
}

function loadSingleFileSkill(filePath: string, source: Skill['source']): Skill | null {
  try {
    const raw = readFileSync(filePath, 'utf-8');
    const { metadata, content } = parseSkillFile(raw);
    return { metadata, content, filePath, source, enabled: true };
  } catch {
    return null;
  }
}

export function findSkill(skills: Skill[], name: string): Skill | undefined {
  return skills.find(s => s.metadata.name === name && s.enabled);
}

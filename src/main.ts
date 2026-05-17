import chalk from 'chalk';
import { loadConfig } from './utils/config';
import { createBashTool } from './tools/BashTool';
import { createFileReadTool } from './tools/FileReadTool';
import { createFileWriteTool } from './tools/FileWriteTool';
import { createFileEditTool } from './tools/FileEditTool';
import { createGlobTool } from './tools/GlobTool';
import { createGrepTool } from './tools/GrepTool';
import { createAgentTool } from './tools/AgentTool';
import { createSkillTool } from './tools/SkillTool';
import { loadAllSkills } from './skills/loader';
import { initMcpClients } from './services/mcp';
import { startRepl } from './repl';
import { startInkRepl } from './screens/REPL';

const BANNER = `
${chalk.green('██╗    ██╗███████╗ █████╗ ██╗   ██╗███████╗██████╗')}
${chalk.green('██║    ██║██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗')}
${chalk.green('██║ █╗ ██║█████╗  ███████║██║   ██║█████╗  ██████╔╝')}
${chalk.green('██║███╗██║██╔══╝  ██╔══██║╚██╗ ██╔╝██╔══╝  ██╔══██╗')}
${chalk.green('╚███╔███╔╝███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║')}
${chalk.green(' ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝')}

${chalk.gray('渗透测试 Agent 框架')}                         ${chalk.gray('v0.1.0')}
`;

export async function main(args: string[]) {
  console.log(BANNER);

  const config = loadConfig();

  // 显示后端信息
  const backendLabel = formatBackend(config.backend);
  console.log(chalk.gray(`后端: ${backendLabel}`));
  console.log(chalk.gray(`模型: ${config.model}`));
  console.log();

  const skills = loadAllSkills();
  console.log(chalk.gray(`Skills: ${skills.length} 已加载`));

  const mcp = await initMcpClients(config.mcpServers);

  const baseTools = [
    createBashTool(config.backend),
    createFileReadTool(),
    createFileWriteTool(),
    createFileEditTool(),
    createGlobTool(),
    createGrepTool(),
    createSkillTool(skills),
    ...mcp.tools,
  ];

  const tools = [...baseTools, createAgentTool(config, baseTools)];

  const useClassic = args.includes('--classic') || !process.stdin.isTTY;
  if (useClassic) {
    await startRepl({ config, tools, skills, mcp });
  } else {
    startInkRepl({ config, tools, skills, mcp });
  }
}

function formatBackend(backend: import('./types/config').ExecBackend): string {
  switch (backend.type) {
    case 'local':
      return 'local';
    case 'wsl':
      return `wsl://${backend.distro}`;
    case 'ssh':
      return `ssh://${backend.user}@${backend.host}:${backend.port}`;
    case 'docker':
      return `docker://${backend.container}`;
  }
}

import chalk from 'chalk';
import { McpServerConfig } from '../../types/config';
import { ToolDefinition } from '../../types/tool';
import { McpClient, mcpToolsToWeaver } from './client';

export interface McpManager {
  clients: Map<string, McpClient>;
  tools: ToolDefinition[];
}

export async function initMcpClients(
  servers: Record<string, McpServerConfig>
): Promise<McpManager> {
  const clients = new Map<string, McpClient>();
  const tools: ToolDefinition[] = [];

  for (const [name, config] of Object.entries(servers)) {
    const client = new McpClient(name, config);
    try {
      await client.connect();
      const mcpTools = await client.listTools();
      const weaverTools = mcpToolsToWeaver(client, mcpTools);
      tools.push(...weaverTools);
      clients.set(name, client);
      console.log(chalk.gray(`  MCP: ${name} 已连接 (${mcpTools.length} 工具)`));
    } catch (err: any) {
      console.log(chalk.yellow(`  MCP: ${name} 连接失败 - ${err.message}`));
    }
  }

  return { clients, tools };
}

export async function disconnectAll(manager: McpManager): Promise<void> {
  for (const [, client] of manager.clients) {
    await client.disconnect();
  }
}

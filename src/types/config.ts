// 执行后端配置
export type ExecBackend =
  | { type: 'local' }
  | { type: 'wsl'; distro: string }
  | {
      type: 'ssh';
      host: string;
      port: number;
      user: string;
      authMethod: 'password' | 'key' | 'agent';
      password?: string;
      passwordHelper?: string;
      keyFile?: string;
    }
  | { type: 'docker'; container: string };

// 完整配置
export interface WeaverConfig {
  apiKey?: string;
  apiKeyHelper?: string;
  model: string;
  baseUrl?: string;
  customHeaders?: string;
  timeout: number;
  backend: ExecBackend;
  reportsDir: string;
  mcpServers: Record<string, McpServerConfig>;
}

export interface McpServerConfig {
  command: string;
  args?: string[];
  env?: Record<string, string>;
}

export const DEFAULT_CONFIG: WeaverConfig = {
  model: 'claude-sonnet-4-6',
  timeout: 600000,
  backend: { type: 'local' },
  reportsDir: '~/.weaver/reports/',
  mcpServers: {},
};

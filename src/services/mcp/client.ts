import { spawn, ChildProcess } from 'child_process';
import { McpServerConfig } from '../../types/config';
import { ToolDefinition, ToolResult } from '../../types/tool';

interface JsonRpcRequest {
  jsonrpc: '2.0';
  id: number;
  method: string;
  params?: Record<string, unknown>;
}

interface JsonRpcResponse {
  jsonrpc: '2.0';
  id: number;
  result?: any;
  error?: { code: number; message: string };
}

interface McpToolSchema {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
}

export class McpClient {
  private process: ChildProcess | null = null;
  private requestId = 0;
  private pending = new Map<number, { resolve: (v: any) => void; reject: (e: Error) => void }>();
  private buffer = '';
  private connected = false;

  constructor(
    public readonly name: string,
    private config: McpServerConfig
  ) {}

  async connect(): Promise<void> {
    const { command, args = [], env } = this.config;

    this.process = spawn(command, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, ...env },
      shell: true,
    });

    this.process.stdout?.on('data', (data: Buffer) => {
      this.buffer += data.toString();
      this.processBuffer();
    });

    this.process.stderr?.on('data', (data: Buffer) => {
      // MCP servers may log to stderr, ignore
    });

    this.process.on('close', () => {
      this.connected = false;
      for (const [, { reject }] of this.pending) {
        reject(new Error(`MCP server "${this.name}" disconnected`));
      }
      this.pending.clear();
    });

    await this.sendRequest('initialize', {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: 'weaver', version: '0.1.0' },
    });

    await this.sendNotification('notifications/initialized', {});
    this.connected = true;
  }

  async listTools(): Promise<McpToolSchema[]> {
    const result = await this.sendRequest('tools/list', {});
    return result.tools || [];
  }

  async callTool(name: string, args: Record<string, unknown>): Promise<string> {
    const result = await this.sendRequest('tools/call', { name, arguments: args });
    if (result.content && Array.isArray(result.content)) {
      return result.content
        .map((c: any) => (c.type === 'text' ? c.text : JSON.stringify(c)))
        .join('\n');
    }
    return JSON.stringify(result);
  }

  async disconnect(): Promise<void> {
    if (this.process) {
      this.process.kill();
      this.process = null;
    }
    this.connected = false;
  }

  isConnected(): boolean {
    return this.connected;
  }

  private async sendRequest(method: string, params: Record<string, unknown>): Promise<any> {
    const id = ++this.requestId;
    const request: JsonRpcRequest = { jsonrpc: '2.0', id, method, params };

    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      const msg = JSON.stringify(request) + '\n';
      this.process?.stdin?.write(msg);

      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`MCP request timeout: ${method}`));
        }
      }, 30000);
    });
  }

  private async sendNotification(method: string, params: Record<string, unknown>): Promise<void> {
    const msg = JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n';
    this.process?.stdin?.write(msg);
  }

  private processBuffer(): void {
    const lines = this.buffer.split('\n');
    this.buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const msg = JSON.parse(line) as JsonRpcResponse;
        if (msg.id && this.pending.has(msg.id)) {
          const { resolve, reject } = this.pending.get(msg.id)!;
          this.pending.delete(msg.id);
          if (msg.error) {
            reject(new Error(`MCP error: ${msg.error.message}`));
          } else {
            resolve(msg.result);
          }
        }
      } catch {
        // ignore malformed lines
      }
    }
  }
}

export function mcpToolsToWeaver(client: McpClient, mcpTools: McpToolSchema[]): ToolDefinition[] {
  return mcpTools.map((t) => ({
    name: `mcp_${client.name}_${t.name}`,
    description: `[MCP:${client.name}] ${t.description || t.name}`,
    inputSchema: t.inputSchema || { type: 'object', properties: {} },
    async execute(input: Record<string, unknown>): Promise<ToolResult> {
      try {
        const output = await client.callTool(t.name, input);
        return { output, exitCode: 0 };
      } catch (err: any) {
        return { output: `MCP error: ${err.message}`, exitCode: 1 };
      }
    },
  }));
}
